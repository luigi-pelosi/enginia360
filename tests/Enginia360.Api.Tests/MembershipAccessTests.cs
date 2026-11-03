using Microsoft.AspNetCore.Hosting;
using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Npgsql;
using Xunit;

public sealed class MembershipAccessTests
{
    private static async Task<int> WaitForWaiter(NpgsqlDataSource admin, int blocker)
    {
        var until = DateTime.UtcNow.AddSeconds(4);
        while (DateTime.UtcNow < until)
        {
            await using var inspect = admin.CreateCommand("SELECT pid FROM pg_stat_activity WHERE @blocker=ANY(pg_blocking_pids(pid)) LIMIT 1");
            inspect.Parameters.AddWithValue("blocker",blocker);
            if (await inspect.ExecuteScalarAsync() is int pid) return pid;
            await Task.Delay(25);
        }
        throw new TimeoutException("Expected physical database lock waiter not observed.");
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Signed_bearer_existing_member_state_command_is_atomic_current_and_replay_safe(int poolSize)
    {
        var owner = Guid.NewGuid(); var memberIdentity = Guid.NewGuid();
        var tenant = Guid.NewGuid(); var member = Guid.NewGuid(); var company = Guid.NewGuid();
        var site = Guid.NewGuid(); var warehouse = Guid.NewGuid();
        var subject = "access-owner-" + owner;
        await using var admin = NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        await using (var seed = admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES (@owner,@issuer,@subject),(@identity,@issuer,@memberSubject);
            INSERT INTO organization_access.platform_authority VALUES(true,@owner,@issuer,@subject,true,1);
            INSERT INTO organization_access.tenants("Id","Name") VALUES (@tenant,'Synthetic access tenant');
            INSERT INTO organization_access.memberships VALUES (@member,@tenant,@identity::text);
            INSERT INTO organization_access.legal_entities("Id","TenantId","Name") VALUES (@company,@tenant,'Synthetic company');
            INSERT INTO organization_access.company_permissions VALUES (gen_random_uuid(),@member,@tenant,@company,'counterparties.read',NULL,NULL);
            INSERT INTO organization_access.sites("Id","TenantId","LegalEntityId","Name") VALUES (@site,@tenant,@company,'Synthetic site');
            INSERT INTO organization_access.warehouses("Id","TenantId","LegalEntityId","SiteId","Name") VALUES (@warehouse,@tenant,@company,@site,'Synthetic warehouse');
            INSERT INTO organization_access.capability_activations VALUES (@company,'organization-context',true);
            INSERT INTO organization_access.membership_scopes VALUES (gen_random_uuid(),@member,@tenant,@company,@site,@warehouse,'organization-context.read'),(gen_random_uuid(),@member,@tenant,@company,@site,@warehouse,'organization-context.write');
            """))
        {
            seed.Parameters.AddWithValue("owner", owner); seed.Parameters.AddWithValue("issuer", BindingApiFactory.Issuer);
            seed.Parameters.AddWithValue("subject", subject); seed.Parameters.AddWithValue("memberSubject", "Access member-" + memberIdentity); seed.Parameters.AddWithValue("identity", memberIdentity);
            seed.Parameters.AddWithValue("tenant", tenant); seed.Parameters.AddWithValue("member", member); seed.Parameters.AddWithValue("company", company);
            seed.Parameters.AddWithValue("site", site); seed.Parameters.AddWithValue("warehouse", warehouse);
            await seed.ExecuteNonQueryAsync();
        }
        try
        {
            using var factory = new BindingApiFactory(poolSize);
            using var application = factory.WithWebHostBuilder(b => b.UseSetting("Counterparties:Enabled", "true"));
            using var client = application.CreateClient(new() { AllowAutoRedirect = false });
            using var memberClient = application.CreateClient(new() { AllowAutoRedirect = false });
            memberClient.DefaultRequestHeaders.Authorization = new("Bearer", factory.Token("Access member-" + memberIdentity, Guid.NewGuid()));
            var companies = await memberClient.GetFromJsonAsync<JsonElement>("/api/v1/counterparties/companies");
            Assert.Equal(1, companies.GetArrayLength());
            Assert.Equal(company, companies[0].GetProperty("legalEntityId").GetGuid());
            var route = "/api/v1/platform/tenant-roles/" + tenant + "/membership-access";
            Assert.Equal(HttpStatusCode.Unauthorized, (await client.PostAsJsonAsync(route, new { })).StatusCode);
            client.DefaultRequestHeaders.Authorization = new("Bearer", factory.Token(subject, Guid.NewGuid()));
            var selector = await client.GetFromJsonAsync<JsonElement>("/api/v1/platform/tenant-roles/" + tenant);
            var selected = selector.GetProperty("memberships")[0];
            var command = new { commandId = Guid.NewGuid().ToString("D"), membershipId = member.ToString("D"),
                internalIdentityId = memberIdentity.ToString("D"), bindingHash = selected.GetProperty("bindingHash").GetString(),
                expectedRevision = 0, enabled = false };
            var responses = await Task.WhenAll(Enumerable.Range(0, 4).Select(_ => client.PostAsJsonAsync(route, command)));
            var values = new List<JsonElement>();
            foreach (var response in responses)
            {
                Assert.Equal(HttpStatusCode.OK, response.StatusCode);
                Assert.True(response.Headers.CacheControl?.NoStore);
                values.Add(await response.Content.ReadFromJsonAsync<JsonElement>());
            }
            Assert.Single(values, v => v.GetProperty("state").GetString() == "applied");
            Assert.Equal(3, values.Count(v => v.GetProperty("state").GetString() == "replayed"));
            Assert.All(values, v => Assert.Equal(values[0].GetProperty("snapshot").ToString(), v.GetProperty("snapshot").ToString()));
            var raw = JsonSerializer.Serialize(command);
            Assert.Equal(HttpStatusCode.Conflict, (await client.PostAsync(route, new StringContent(raw.Replace("false", "true"), Encoding.UTF8, "application/json"))).StatusCode);
            foreach (var bad in new[] { "{", "null", "{\"enabled\":true,\"enabled\":false}", raw.Replace("\"expectedRevision\":0", "\"expectedRevision\":1e999999999"), raw.Replace("\"enabled\":false", "\"enabled\":\"\\u0000\""), raw.Replace("\"enabled\":false", "\"enabled\":\"\\ud800\""), new string(' ', 16385) + "{}" })
                Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsync(route, new StringContent(bad, Encoding.UTF8, "application/json"))).StatusCode);
            selector = await client.GetFromJsonAsync<JsonElement>("/api/v1/platform/tenant-roles/" + tenant);
            Assert.False(selector.GetProperty("memberships")[0].GetProperty("accessEnabled").GetBoolean());
            Assert.Equal(1, selector.GetProperty("memberships")[0].GetProperty("accessRevision").GetInt32());
            Assert.Equal(0, (await memberClient.GetFromJsonAsync<JsonElement>("/api/v1/counterparties/companies")).GetArrayLength());
            var enable = new { commandId = Guid.NewGuid().ToString("D"), command.membershipId, command.internalIdentityId, command.bindingHash, expectedRevision = 1, enabled = true };
            Assert.Equal(HttpStatusCode.OK, (await client.PostAsJsonAsync(route, enable)).StatusCode);
            Assert.Equal(1, (await memberClient.GetFromJsonAsync<JsonElement>("/api/v1/counterparties/companies")).GetArrayLength());
            Assert.Equal(HttpStatusCode.OK, (await client.PostAsJsonAsync(route, command)).StatusCode);
            Assert.Equal(1, (await memberClient.GetFromJsonAsync<JsonElement>("/api/v1/counterparties/companies")).GetArrayLength());
            // Actual OrganizationContextService owning transaction, not an
            // authorization-adapter transaction. Fixture-only physical barriers.
            var note = new { tenantId = tenant, legalEntityId = company, siteId = site, warehouseId = warehouse, message = "Synthetic access effect" };
            const string notes = "/api/v1/organization/context-notes";
            Assert.Equal(HttpStatusCode.Created, (await memberClient.PostAsJsonAsync(notes, note)).StatusCode);
            var disableFirst = new { commandId = Guid.NewGuid().ToString("D"), command.membershipId, command.internalIdentityId, command.bindingHash, expectedRevision = 2, enabled = false };
            await using (var holder = await admin.OpenConnectionAsync())
            await using (var tx = await holder.BeginTransactionAsync())
            {
                await using var mutate = new NpgsqlCommand("""
                    SELECT set_config('app.identity_subject',@actor,true),set_config('app.identity_issuer',@issuer,true),set_config('app.external_subject',@subject,true);
                    SET LOCAL ROLE runtime_app;
                    SELECT organization_access.command_membership_access(@tenant,@request::jsonb)::text;
                    """, holder, tx);
                mutate.Parameters.AddWithValue("actor", owner.ToString("D")); mutate.Parameters.AddWithValue("issuer", BindingApiFactory.Issuer);
                mutate.Parameters.AddWithValue("subject", subject); mutate.Parameters.AddWithValue("tenant", tenant); mutate.Parameters.AddWithValue("request", JsonSerializer.Serialize(disableFirst));
                await using (var reader = await mutate.ExecuteReaderAsync()) { while (await reader.NextResultAsync()) { } }
                var blocked = memberClient.PostAsJsonAsync(notes, note);
                await WaitForWaiter(admin, holder.ProcessID);
                Assert.False(blocked.IsCompleted);
                await tx.CommitAsync();
                Assert.Equal(HttpStatusCode.Forbidden, (await blocked).StatusCode);
            }
            Assert.Equal(HttpStatusCode.OK, (await client.PostAsJsonAsync(route, new { commandId = Guid.NewGuid().ToString("D"), command.membershipId, command.internalIdentityId, command.bindingHash, expectedRevision = 3, enabled = true })).StatusCode);
            await using (var fixture = admin.CreateCommand("""
                CREATE OR REPLACE FUNCTION organization_access.fixture_access_effect_barrier() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_advisory_xact_lock(777140); RETURN NEW; END $$;
                CREATE TRIGGER fixture_access_effect_barrier BEFORE INSERT ON organization_access.context_notes FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_access_effect_barrier();
                """)) { await fixture.ExecuteNonQueryAsync(); }
            try
            {
                await using var holder = await admin.OpenConnectionAsync();
                await using var tx = await holder.BeginTransactionAsync();
                await using (var guard = new NpgsqlCommand("SELECT pg_advisory_xact_lock(777140)",holder,tx)) { await guard.ExecuteNonQueryAsync(); }
                var effect = memberClient.PostAsJsonAsync(notes, note);
                var effectPid = await WaitForWaiter(admin, holder.ProcessID);
                var disable = client.PostAsJsonAsync(route, new { commandId = Guid.NewGuid().ToString("D"), command.membershipId, command.internalIdentityId, command.bindingHash, expectedRevision = 4, enabled = false });
                if (poolSize > 1) await WaitForWaiter(admin, effectPid);
                // Pool1 completes without nested-pool deadlock; pool4 additionally
                // proves the second physical SQL connection waits on the effect.
                Assert.False(disable.IsCompleted);
                await tx.CommitAsync();
                Assert.Equal(HttpStatusCode.Created, (await effect).StatusCode);
                Assert.Equal(HttpStatusCode.OK, (await disable).StatusCode);
            }
            finally
            {
                await using var drop = admin.CreateCommand("DROP TRIGGER fixture_access_effect_barrier ON organization_access.context_notes; DROP FUNCTION organization_access.fixture_access_effect_barrier();");
                await drop.ExecuteNonQueryAsync();
            }
            Assert.Equal(HttpStatusCode.Forbidden, (await memberClient.PostAsJsonAsync(notes, note)).StatusCode);
            await using (var effects = admin.CreateCommand("SELECT count(*) FROM organization_access.context_notes WHERE \"TenantId\"=@tenant"))
            { effects.Parameters.AddWithValue("tenant",tenant); Assert.Equal(2L,await effects.ExecuteScalarAsync()); }
            await using (var verify = admin.CreateCommand("SELECT count(*) FROM organization_access.membership_access_audit WHERE \"CommandId\"=@id AND \"Outcome\"='applied'"))
            {
                verify.Parameters.AddWithValue("id", Guid.Parse(command.commandId)); Assert.Equal(1L, await verify.ExecuteScalarAsync());
            }
            // The API commits before returning success: immediate and deferred
            // audit failures must surface 503 and roll back access and replay.
            await using (var fixture = admin.CreateCommand("CREATE FUNCTION organization_access.fixture_access_http_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic HTTP access audit refusal'; END $$"))
            { await fixture.ExecuteNonQueryAsync(); }
            foreach (var deferred in new[] { false, true })
            {
                var trigger = deferred
                    ? "CREATE CONSTRAINT TRIGGER fixture_access_http_fail AFTER INSERT ON organization_access.membership_access_audit DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_access_http_fail()"
                    : "CREATE TRIGGER fixture_access_http_fail BEFORE INSERT ON organization_access.membership_access_audit FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_access_http_fail()";
                await using (var install = admin.CreateCommand(trigger)) { await install.ExecuteNonQueryAsync(); }
                try
                {
                    var rejected = new { commandId = Guid.NewGuid().ToString("D"), command.membershipId, command.internalIdentityId, command.bindingHash, expectedRevision = 5, enabled = true };
                    Assert.Equal(HttpStatusCode.ServiceUnavailable, (await client.PostAsJsonAsync(route, rejected)).StatusCode);
                    await using var verify = admin.CreateCommand("SELECT (SELECT count(*) FROM organization_access.membership_access_state WHERE \"MembershipId\"=@member AND NOT \"Enabled\" AND \"Revision\"=5)=1 AND NOT EXISTS(SELECT 1 FROM organization_access.membership_access_audit WHERE \"CommandId\"=@id)");
                    verify.Parameters.AddWithValue("member",member); verify.Parameters.AddWithValue("id",Guid.Parse(rejected.commandId));
                    Assert.Equal(true,await verify.ExecuteScalarAsync());
                }
                finally
                { await using var drop = admin.CreateCommand("DROP TRIGGER fixture_access_http_fail ON organization_access.membership_access_audit"); await drop.ExecuteNonQueryAsync(); }
            }
            await using (var drop = admin.CreateCommand("DROP FUNCTION organization_access.fixture_access_http_fail()")) { await drop.ExecuteNonQueryAsync(); }
            await using (var revoke = admin.CreateCommand("UPDATE organization_access.platform_authority SET \"Active\"=false WHERE \"InternalIdentityId\"=@id"))
            {
                revoke.Parameters.AddWithValue("id", owner); await revoke.ExecuteNonQueryAsync();
            }
            Assert.Equal(HttpStatusCode.Forbidden, (await client.PostAsJsonAsync(route, command)).StatusCode);
        }
        finally
        {
            await using var cleanup = admin.CreateCommand("DELETE FROM organization_access.platform_authority WHERE \"InternalIdentityId\"=@id");
            cleanup.Parameters.AddWithValue("id", owner); await cleanup.ExecuteNonQueryAsync();
        }
    }
}
