using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Enginia360.Api.BrowserAuthentication;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;
using Npgsql;
using Xunit;

public sealed class FederatedOnboardingTests
{
    [Theory]
    [InlineData("signature", HttpStatusCode.BadRequest)]
    [InlineData("issuer", HttpStatusCode.BadRequest)]
    [InlineData("audience", HttpStatusCode.BadRequest)]
    [InlineData("nonce", HttpStatusCode.BadRequest)]
    [InlineData("expired", HttpStatusCode.BadRequest)]
    [InlineData("future", HttpStatusCode.BadRequest)]
    [InlineData("valid", HttpStatusCode.ServiceUnavailable)]
    public async Task Invitation_state_never_replaces_real_oidc_validation_or_store_availability(string kind, HttpStatusCode expected)
    {
        await using var factory=new BrowserSessionTests.BrowserFactory { TokenKind=kind };
        using var client=factory.CreateClient(new() { BaseAddress=new("https://localhost"),AllowAutoRedirect=false });
        var csrf=(await client.GetFromJsonAsync<JsonElement>("/auth/csrf")).GetProperty("requestToken").GetString()!;
        var challenge=await client.PostAsync("/auth/onboarding/login/"+Guid.NewGuid(),new FormUrlEncodedContent(new Dictionary<string,string> { ["__RequestVerificationToken"]=csrf }));
        Assert.Equal(HttpStatusCode.Redirect,challenge.StatusCode);
        var query=Microsoft.AspNetCore.WebUtilities.QueryHelpers.ParseQuery(challenge.Headers.Location!.Query);
        factory.Nonce=query["nonce"];
        var callback="/signin-oidc?code=synthetic-code&state="+Uri.EscapeDataString(query["state"]!);
        var result=await client.GetAsync(callback);
        Assert.Equal(expected,result.StatusCode);
        Assert.DoesNotContain(result.Headers.TryGetValues("Set-Cookie",out var cookies)?cookies:[],c=>c.StartsWith("__Host-enginia360-pending=")||c.StartsWith("__Host-enginia360-session="));
        Assert.Equal(HttpStatusCode.BadRequest,(await client.GetAsync(callback)).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized,(await client.GetAsync("/auth/onboarding/status")).StatusCode);
    }

    [Fact]
    public async Task Pending_ticket_is_never_selected_for_default_api_session_or_forged_bearer()
    {
        await using var factory = new BrowserSessionTests.BrowserFactory();
        using var client = factory.CreateClient(new() { BaseAddress = new("https://localhost"), HandleCookies = false, AllowAutoRedirect = false });
        var id = Guid.NewGuid().ToString("D");
        var principal = new System.Security.Claims.ClaimsPrincipal(new System.Security.Claims.ClaimsIdentity([
            new("sub",id),new(PendingOnboarding.RequestClaim,id),new(PendingOnboarding.TenantClaim,Guid.NewGuid().ToString("D")),
            new(ExternalIdentityResolver.IssuerClaim,"https://issuer.test/realms/runtime"),new(ExternalIdentityResolver.SubjectClaim,"opaque-external-subject")],PendingOnboarding.Scheme));
        var store = factory.Services.GetRequiredService<ITicketStore>();
        var key = await store.StoreAsync(new(principal,new() { ExpiresUtc=DateTimeOffset.UtcNow.AddMinutes(5) },PendingOnboarding.Scheme));
        var reference = new AuthenticationTicket(new(new System.Security.Claims.ClaimsIdentity([
            new("Microsoft.AspNetCore.Authentication.Cookies-SessionId",key)],PendingOnboarding.Scheme)),PendingOnboarding.Scheme);
        var options = factory.Services.GetRequiredService<IOptionsMonitor<CookieAuthenticationOptions>>().Get(PendingOnboarding.Scheme);
        client.DefaultRequestHeaders.Add("Cookie","__Host-enginia360-pending="+options.TicketDataFormat.Protect(reference));
        Assert.False((await client.GetFromJsonAsync<JsonElement>("/auth/session")).GetProperty("authenticated").GetBoolean());
        foreach (var route in new[] { "/api/v1/organization/contexts", "/api/v1/platform/tenant-roles/workspace", "/api/v1/platform/tenant-roles/onboarding/workspace" })
            Assert.Equal(HttpStatusCode.Unauthorized,(await client.GetAsync(route)).StatusCode);
        Assert.Equal(HttpStatusCode.OK,(await client.GetAsync("/auth/onboarding/csrf")).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest,(await client.PostAsync("/auth/onboarding/logout",new FormUrlEncodedContent([]))).StatusCode);
        client.DefaultRequestHeaders.Authorization=new("Bearer","forged");
        Assert.Equal(HttpStatusCode.Unauthorized,(await client.GetAsync("/auth/onboarding/status")).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized,(await client.GetAsync("/api/v1/organization/contexts")).StatusCode);
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Real_oidc_pending_cookie_approval_then_new_normal_login_and_existing_signed_bearer(int poolSize)
    {
        var owner=Guid.NewGuid();var tenant=Guid.NewGuid();var ownerSubject="onboarding-owner-"+owner;
        await using var admin=NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        await using (var seed=admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES(@owner,@issuer,@subject);
            INSERT INTO organization_access.platform_authority VALUES(true,@owner,@issuer,@subject,true,1);
            INSERT INTO organization_access.tenants("Id","Name") VALUES(@tenant,'Synthetic onboarding');
            """))
        {
            seed.Parameters.AddWithValue("owner",owner);seed.Parameters.AddWithValue("issuer",BindingApiFactory.Issuer);
            seed.Parameters.AddWithValue("subject",ownerSubject);seed.Parameters.AddWithValue("tenant",tenant);await seed.ExecuteNonQueryAsync();
        }
        try
        {
            using var bearerFactory=new BindingApiFactory(poolSize);
            using var ownerClient=bearerFactory.CreateClient(new() { AllowAutoRedirect=false });
            ownerClient.DefaultRequestHeaders.Authorization=new("Bearer",bearerFactory.Token(ownerSubject,Guid.NewGuid()));
            var route="/api/v1/platform/tenant-roles/"+tenant+"/onboarding";
            var inviteResponse=await ownerClient.PostAsJsonAsync(route,new { commandId=Guid.NewGuid(),operation="invite",resourceId=(string?)null,expectedRevision=0 });
            Assert.Equal(HttpStatusCode.OK,inviteResponse.StatusCode);
            var invitation=(await inviteResponse.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("snapshot").GetProperty("invitationId").GetGuid();
            await using var browserFactory=new BrowserSessionTests.BrowserFactory(new() {
                ["ConnectionStrings:OrganizationAccess"]=new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!) { MaxPoolSize=poolSize }.ConnectionString });
            using var pending=browserFactory.CreateClient(new() { BaseAddress=new("https://localhost"),AllowAutoRedirect=false });
            async Task<HttpResponseMessage> Login(string path)
            {
                var csrf=(await pending.GetFromJsonAsync<JsonElement>("/auth/csrf")).GetProperty("requestToken").GetString()!;
                var challenge=await pending.PostAsync(path,new FormUrlEncodedContent(new Dictionary<string,string> { ["__RequestVerificationToken"]=csrf }));
                Assert.Equal(HttpStatusCode.Redirect,challenge.StatusCode);
                var query=Microsoft.AspNetCore.WebUtilities.QueryHelpers.ParseQuery(challenge.Headers.Location!.Query);
                browserFactory.Nonce=query["nonce"];
                return await pending.GetAsync("/signin-oidc?code=synthetic-code&state="+Uri.EscapeDataString(query["state"]!));
            }
            var callback=await Login("/auth/onboarding/login/"+invitation);
            Assert.Equal(HttpStatusCode.Redirect,callback.StatusCode);Assert.Equal("/onboarding",callback.Headers.Location!.ToString());
            Assert.Contains(callback.Headers.GetValues("Set-Cookie"),c=>c.StartsWith("__Host-enginia360-pending=")&&c.Contains("secure")&&c.Contains("httponly"));
            Assert.False((await pending.GetFromJsonAsync<JsonElement>("/auth/session")).GetProperty("authenticated").GetBoolean());
            var state=await pending.GetFromJsonAsync<JsonElement>("/auth/onboarding/status");
            Assert.False(state.GetProperty("approved").GetBoolean());Assert.Equal(tenant,state.GetProperty("tenantId").GetGuid());
            Assert.Equal(HttpStatusCode.Unauthorized,(await pending.GetAsync(route)).StatusCode);
            Assert.Equal(HttpStatusCode.Unauthorized,(await pending.GetAsync("/api/v1/organization/contexts")).StatusCode);
            var approval=new { commandId=Guid.NewGuid(),operation="approve",resourceId=state.GetProperty("requestId").GetGuid(),expectedRevision=1 };
            await using (var install=admin.CreateCommand("CREATE FUNCTION organization_access.fixture_onboarding_http_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.\"Request\"->>'operation'='approve' THEN RAISE EXCEPTION 'synthetic onboarding HTTP audit refusal'; END IF; RETURN NEW; END $$"))
                await install.ExecuteNonQueryAsync();
            try
            {
                foreach(var deferred in new[] { false,true })
                {
                    var trigger=deferred
                        ? "CREATE CONSTRAINT TRIGGER fixture_onboarding_http_fail AFTER INSERT ON organization_access.onboarding_audit DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_onboarding_http_fail()"
                        : "CREATE TRIGGER fixture_onboarding_http_fail BEFORE INSERT ON organization_access.onboarding_audit FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_onboarding_http_fail()";
                    await using(var install=admin.CreateCommand(trigger)) await install.ExecuteNonQueryAsync();
                    try
                    {
                        Assert.Equal(HttpStatusCode.ServiceUnavailable,(await ownerClient.PostAsJsonAsync(route,approval)).StatusCode);
                        Assert.False((await pending.GetFromJsonAsync<JsonElement>("/auth/onboarding/status")).GetProperty("approved").GetBoolean());
                        await using var noPartial=admin.CreateCommand("SELECT count(*) FROM organization_access.memberships WHERE \"TenantId\"=@tenant");
                        noPartial.Parameters.AddWithValue("tenant",tenant);Assert.Equal(0L,await noPartial.ExecuteScalarAsync());
                    }
                    finally { await using var drop=admin.CreateCommand("DROP TRIGGER fixture_onboarding_http_fail ON organization_access.onboarding_audit");await drop.ExecuteNonQueryAsync(); }
                }
            }
            finally { await using var drop=admin.CreateCommand("DROP FUNCTION organization_access.fixture_onboarding_http_fail()");await drop.ExecuteNonQueryAsync(); }
            var responses=await Task.WhenAll(Enumerable.Range(0,3).Select(_=>ownerClient.PostAsJsonAsync(route,approval)));
            var states=new List<string>();
            foreach(var response in responses) { Assert.Equal(HttpStatusCode.OK,response.StatusCode);Assert.True(response.Headers.CacheControl!.NoStore);states.Add((await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("state").GetString()!); }
            Assert.Equal(1,states.Count(s=>s=="applied"));Assert.Equal(2,states.Count(s=>s=="replayed"));
            Assert.True((await pending.GetFromJsonAsync<JsonElement>("/auth/onboarding/status")).GetProperty("approved").GetBoolean());
            Assert.False((await pending.GetFromJsonAsync<JsonElement>("/auth/session")).GetProperty("authenticated").GetBoolean());
            Assert.Equal(HttpStatusCode.Redirect,(await Login("/auth/login")).StatusCode);
            Assert.True((await pending.GetFromJsonAsync<JsonElement>("/auth/session")).GetProperty("authenticated").GetBoolean());
            Assert.Equal(HttpStatusCode.Unauthorized,(await pending.GetAsync("/auth/onboarding/status")).StatusCode);
            Assert.Equal(0,(await pending.GetFromJsonAsync<JsonElement>("/api/v1/organization/contexts")).GetArrayLength());
            var selected=await ownerClient.GetFromJsonAsync<JsonElement>("/api/v1/platform/tenant-roles/"+tenant);
            var member=Assert.Single(selected.GetProperty("memberships").EnumerateArray());
            Assert.False(member.GetProperty("accessEnabled").GetBoolean());Assert.False(member.GetProperty("active").GetBoolean());
            Assert.Equal(HttpStatusCode.OK,(await ownerClient.PostAsJsonAsync(route,approval)).StatusCode);
            foreach(var invalid in new[] { "{", "{\"operation\":\"invite\",\"operation\":\"approve\"}", "{\"expectedRevision\":1e999999999}", "{\"x\":\"\\u0000\"}" })
                Assert.Equal(HttpStatusCode.BadRequest,(await ownerClient.PostAsync(route,new StringContent(invalid,System.Text.Encoding.UTF8,"application/json"))).StatusCode);
            await using var verify=admin.CreateCommand("SELECT count(*) FROM organization_access.onboarding_audit WHERE \"TenantId\"=@tenant AND \"Outcome\"='applied'");
            verify.Parameters.AddWithValue("tenant",tenant);Assert.Equal(2L,await verify.ExecuteScalarAsync());
        }
        finally
        {
            await using var cleanup=admin.CreateCommand("""
                DELETE FROM organization_access.membership_access_state WHERE "TenantId"=@tenant;
                DELETE FROM organization_access.memberships WHERE "TenantId"=@tenant;
                DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId" IN (SELECT "InternalIdentityId" FROM organization_access.onboarding_requests WHERE "TenantId"=@tenant);
                DELETE FROM organization_access.onboarding_requests WHERE "TenantId"=@tenant;
                DELETE FROM organization_access.onboarding_invitations WHERE "TenantId"=@tenant;
                DELETE FROM organization_access.tenants WHERE "Id"=@tenant;
                DELETE FROM organization_access.platform_authority WHERE "InternalIdentityId"=@owner;
                DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"=@owner;
                """);
            cleanup.Parameters.AddWithValue("tenant",tenant);cleanup.Parameters.AddWithValue("owner",owner);await cleanup.ExecuteNonQueryAsync();
        }
    }
}
