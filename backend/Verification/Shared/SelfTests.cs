using Enginia360.Api.Resources;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.AccessControl;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Enginia360.Verification.AccessControl;
using Enginia360.Verification.Identity;
using Enginia360.Verification.Organizations;
using ResourceCatalog = global::Enginia360.Api.Resources.Resources;
using System.Text.Json;

namespace Enginia360.Verification.Shared;
public static class SelfTests
{
    public static void Run(IServiceProvider services)
    {
        var count=0; var failed=0;
        void Test(string name,Action run) { try { run(); count++; Console.WriteLine("PASS " + name); } catch(Exception e) { failed++; Console.WriteLine("FAIL " + name + ": " + e.Message); } }
        void Reject(Action run,int status=400) {try {run();} catch(ApiException e) when(e.Status==status) {return;} throw new InvalidOperationException("Expected refusal.");}
        Test("currency catalog validates nullable ISO minor units",() => {
            var currency=ResourceCatalog.Get("currencies");
            var valid=ResourceCatalog.Validate(currency,JsonSerializer.SerializeToElement(new {code="XTS",numeric_code="963",name="Test",minor_units=(int?)null}),true);
            if(valid["minor_units"] != null) throw new Exception("N.A. must remain null");
            var units=ResourceCatalog.Validate(currency,JsonSerializer.SerializeToElement(new {minor_units=3}),false);
            if(!Equals(units["minor_units"],3)) throw new Exception("Minor units not numeric");
            Reject(()=>ResourceCatalog.Validate(currency,JsonSerializer.SerializeToElement(new {code="bad"}),false));
        });
        Test("payment permissions are explicit and finite",() => {
            foreach(var code in new[]{"payment-methods.read","payment-methods.create","payment-methods.update","payment-terms.read","payment-terms.create","payment-terms.update","payment-settings.read","payment-settings.update","payment-partner-defaults.read","payment-partner-defaults.update","payment-schedule.preview","payment-resolution.read"})
                if(!PermissionCatalog.Contains(code)) throw new Exception("Missing payment permission: "+code);
            if(PermissionCatalog.Contains("payment-methods.delete") || PermissionCatalog.Contains("payment-terms.delete")) throw new Exception("Physical deletion must not be exposed.");
        });
        Test("business partners finite catalog without delete",() => {
            if(!ResourceCatalog.All.ContainsKey("business-partners")) throw new Exception("Business partner resource missing.");
            foreach(var code in new[]{"business-partners.read","business-partners.create","business-partners.update","business-partner-numbering.read","business-partner-numbering.update"})
                if(!PermissionCatalog.Contains(code)) throw new Exception("Missing permission: "+code);
            if(PermissionCatalog.Contains("business-partners.delete")) throw new Exception("Delete is forbidden.");
        });
        if(Environment.GetEnvironmentVariable("BP_DB_TESTS")=="true") BusinessPartnerTests.Run(services.GetRequiredService<IConfiguration>().GetConnectionString("Database")!,Test);
        Enginia360.Verification.Payments.PaymentScheduleTests.Run(Test);
        LoginPreselectionSelfTests.Run(services,Test);
        ProfileSelfTests.Run(Test);
        bool Allowed(string code, string[] grants, bool global=false)
        {
            using var scope=services.CreateScope();
            var ctx=new DefaultHttpContext { RequestServices=scope.ServiceProvider };
            ctx.Items["identity"]=new IdentityState(new User {TenantId=global ? null : Guid.NewGuid(),IsSuperAdmin=global},"a","A",grants);
            var auth=scope.ServiceProvider.GetRequiredService<Microsoft.AspNetCore.Authorization.IAuthorizationService>();
            try { return auth.AuthorizeAsync(ctx.User,ctx,code).GetAwaiter().GetResult().Succeeded; }
            catch(InvalidOperationException e) when(e.Message.Contains("policy",StringComparison.OrdinalIgnoreCase)) { return false; }
        }
        Test("native policy grants companies.create only",() => {
            if(!Allowed("companies.create",["companies.create"])) throw new Exception("companies.create policy must grant exact create.");
            if(Allowed("companies.update",["companies.create"])) throw new Exception("create must not grant update.");
            if(Allowed("unknown.action",[],true)) throw new Exception("Global must reject unknown code.");
        });
        Test("removed generic settings resource is not found",() => Reject(() => ResourceCatalog.Get("settings"),404));
        foreach(var action in new[]{"read","create","update","delete"})
            Test("removed settings authority denied: "+action,() => {
                var code="settings."+action;
                if(PermissionCatalog.Contains(code) || Allowed(code,[code]) || Allowed(code,[],true))
                    throw new Exception("Removed settings authority granted: "+code);
                foreach(var global in new[]{false,true}) {
                    var state=new IdentityState(new User {TenantId=global ? null : Guid.NewGuid(),IsSuperAdmin=global},"fixture","Fixture",[code]);
                    if(PermissionCatalog.Grants(state,code)) throw new Exception("Legacy settings grant accepted.");
                    Reject(() => state.Authorize("settings",action),403);
                }
            });
        foreach(var resource in new[]{"countries","cities","currencies"}) {
            Test("system catalog exact read grant required: "+resource,() => {
                using var scope=services.CreateScope();
                var ctx=new DefaultHttpContext {RequestServices=scope.ServiceProvider};
                foreach(var grants in new[]{Array.Empty<string>(),new[]{"companies.read"},new[]{"catalog-units.read"}}
                    .Concat(new[]{"countries","cities","currencies"}.Where(r=>r!=resource).Select(r=>new[]{r+".read"}))) {
                    var state=new IdentityState(new User {TenantId=Guid.NewGuid()},"fixture","Fixture",grants);
                    ctx.Items["identity"]=state;
                    Reject(() => Security.AuthorizeResource(ctx,ResourceCatalog.Get(resource),"read").GetAwaiter().GetResult(),403);
                    Reject(() => state.Authorize(resource,"read"),403);
                }
                var granted=new IdentityState(new User {TenantId=Guid.NewGuid()},"fixture","Fixture",[resource+".read"]);
                ctx.Items["identity"]=granted;
                Security.AuthorizeResource(ctx,ResourceCatalog.Get(resource),"read").GetAwaiter().GetResult();
                granted.Authorize(resource,"read");
                foreach(var action in new[]{"create","update","delete"}) {
                    Reject(() => Security.AuthorizeResource(ctx,ResourceCatalog.Get(resource),action).GetAwaiter().GetResult(),403);
                    Reject(() => granted.Authorize(resource,action),403);
                    if(PermissionCatalog.Contains(resource+"."+action)) throw new Exception("Unexpected catalog write permission.");
                }
            });
            Test("system catalog fresh identity revokes read despite cookie: "+resource,() => {
                using var scope=services.CreateScope();
                var ctx=new DefaultHttpContext {RequestServices=scope.ServiceProvider};
                ctx.User=new System.Security.Claims.ClaimsPrincipal(new System.Security.Claims.ClaimsIdentity(new[]{new System.Security.Claims.Claim("permission",resource+".read")},"fixture"));
                var user=new User {TenantId=Guid.NewGuid()};
                ctx.Items["identity"]=new IdentityState(user,"fixture","Fixture",[resource+".read"]);
                Security.AuthorizeResource(ctx,ResourceCatalog.Get(resource),"read").GetAwaiter().GetResult();
                ctx.Items["identity"]=new IdentityState(user,"fixture","Fixture",[]);
                Reject(() => Security.AuthorizeResource(ctx,ResourceCatalog.Get(resource),"read").GetAwaiter().GetResult(),403);
                ctx.Items["identity"]=new IdentityState(new User {IsSuperAdmin=true},"fixture","Fixture",[]);
                foreach(var action in new[]{"read","create","update","delete"}) {
                    Security.AuthorizeResource(ctx,ResourceCatalog.Get(resource),action).GetAwaiter().GetResult();
                    Security.State(ctx).Authorize(resource,action);
                }
            });
        }
        Test("catalog units native permission gates remain exact",() => {
            foreach(var action in new[]{"read","create","update"}) {
                var code="catalog-units."+action;
                if(!Allowed(code,[code]) || Allowed(code,[]) || Allowed(code,["companies.read"])) throw new Exception("Catalog unit gate mismatch.");
                foreach(var other in new[]{"read","create","update"}.Where(a=>a!=action))
                    if(Allowed(code,["catalog-units."+other])) throw new Exception("Catalog unit operation conflated.");
            }
        });
        Test("native password reset is separate from users.update",() => {
            if(!Allowed("users.reset_password",["users.reset_password"])) throw new Exception("reset authority missing.");
            if(Allowed("users.reset_password",["users.update"]) || Allowed("users.update",["users.reset_password"]) || Allowed("users.reset_password",["users.write"])) throw new Exception("Reset/update/write authority conflated.");
        });
        Test("native relation inspection and assignment separated",() => {
            var expected=new Dictionary<string,string> { ["user-roles"]="roles.assign",["group-roles"]="roles.assign",["group-users"]="groups.assign_users",["role-permissions"]="roles.assign_permissions" };
            foreach(var (name,code) in expected) {
                if(!Allowed(code,[code])) throw new Exception("Missing relation authority: "+code);
                var link=ResourceCatalog.Links[name];
                if(Allowed(code,[link.OwnerResource+".update"]) || Allowed(code,[link.OwnerResource+".read"])) throw new Exception("Owner action grants assignment.");
                var metadata=JsonSerializer.SerializeToElement(link);
                if(!metadata.TryGetProperty("Permission",out var actual) || actual.GetString()!=code) throw new Exception("Relation mapping missing: "+name);
                if(!Allowed(link.OwnerResource+".read",[link.OwnerResource+".read"])) throw new Exception("Inspection read denied.");
            }
        });
        Test("catalog readonly rejects mutation before validation",() => {
            foreach(var create in new[] {true,false}) Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("permissions"),JsonSerializer.SerializeToElement(new {code="x",name="x"}),create),403);
            var metadata=JsonSerializer.SerializeToElement(ResourceCatalog.Get("permissions"));
            if(!metadata.TryGetProperty("ReadOnly",out var readOnly) || !readOnly.GetBoolean()) throw new Exception("ReadOnly metadata missing.");
            if(!ResourceCatalog.Scope(ResourceCatalog.Get("permissions")).Contains("is_system")) throw new Exception("Legacy permission visibility widened.");
        });
        Test("native finite actions deny legacy and global tenant impostor",() => {
            foreach(var resource in ResourceCatalog.All.Keys.Where(r => r != "tenants" && !ResourceCatalog.IsGlobalMaster(r))) {
                var actions=resource=="permissions" ? new[]{"read"} : resource=="business-partners" ? new[]{"read","create","update"} : new[]{"read","create","update","delete"};
                foreach(var action in actions) if(!Allowed(resource+"."+action,[resource+"."+action])) throw new Exception("Action missing.");
                if(Allowed(resource+".write",[resource+".write"],true)) throw new Exception("Legacy write granted.");
            }
            var ctx=new DefaultHttpContext {RequestServices=services};
            ctx.Items["identity"]=new IdentityState(new User {IsSuperAdmin=true,TenantId=Guid.NewGuid()},"a","A",[]);
            Reject(() => Security.Authorize(ctx,PermissionCatalog.GlobalPolicy).GetAwaiter().GetResult(),403);
        });
        Test("native handler denies unknown and cookie grants without fresh identity",() => {
            using var scope=services.CreateScope();
            var auth=scope.ServiceProvider.GetRequiredService<Microsoft.AspNetCore.Authorization.IAuthorizationService>();
            var ctx=new DefaultHttpContext {RequestServices=scope.ServiceProvider};
            ctx.User=new System.Security.Claims.ClaimsPrincipal(new System.Security.Claims.ClaimsIdentity(new[]{new System.Security.Claims.Claim("permission","companies.create")},"fixture"));
            if(auth.AuthorizeAsync(ctx.User,ctx,"companies.create").GetAwaiter().GetResult().Succeeded) throw new Exception("Cookie granted authority.");
            ctx.Items["identity"]=new IdentityState(new User {IsSuperAdmin=true},"a","A",[]);
            if(auth.AuthorizeAsync(ctx.User,ctx,new[]{new PermissionRequirement("unknown.action")}).GetAwaiter().GetResult().Succeeded) throw new Exception("Unknown requirement granted to global.");
            ctx.Items["identity"]=new IdentityState(new User {IsSuperAdmin=true,TenantId=Guid.NewGuid()},"a","A",["companies.create"]);
            if(auth.AuthorizeAsync(ctx.User,ctx,"companies.create").GetAwaiter().GetResult().Succeeded) throw new Exception("Tenant impostor granted global authority.");
        });
        Test("global resource gate rejects legacy or unknown tenant actions",() => {
            using var scope=services.CreateScope();
            var ctx=new DefaultHttpContext {RequestServices=scope.ServiceProvider};
            ctx.Items["identity"]=new IdentityState(new User {IsSuperAdmin=true},"a","A",[]);
            foreach(var action in new[]{"write","reset_password","unknown"})
                Reject(() => Security.AuthorizeResource(ctx,ResourceCatalog.Get("tenants"),action).GetAwaiter().GetResult(),403);
        });
        JsonElement Json(string s) => JsonSerializer.Deserialize<JsonElement>(s);
        Test("users require email",() => Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("users"),Json("""{"username":"sample","first_name":"First","last_name":"Last"}"""),true)));
        Test("profile normalization and Unicode names",() => {
            var values=ResourceCatalog.Validate(ResourceCatalog.Get("users"),Json("""{"username":"sample","first_name":"  李  Élodie  ","last_name":"  O’Neil  ","email":"  sample@example.test  "}"""),true);
            if(!Equals(values["first_name"],"李 Élodie") || !Equals(values["last_name"],"O’Neil") || !Equals(values["email"],"sample@example.test")) throw new Exception("Whitespace not normalized.");
        });
        Test("required personal fields reject omission null blanks and limits",() => {
            foreach(var field in new[] {"first_name","last_name","email"}) {
                var profile=new Dictionary<string,object?> { ["username"]="sample",["first_name"]="First",["last_name"]="Last",["email"]="sample@example.test" };
                profile.Remove(field); Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("users"),JsonSerializer.SerializeToElement(profile),true));
                foreach(var invalid in new string?[] {null,"", " \t\n ",new string('x',field=="email" ? 255 : 201)}) {
                    profile[field]=invalid; Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("users"),JsonSerializer.SerializeToElement(profile),true));
                }
            }
        });
        Test("plain email only",() => {
            foreach(var value in new[] {"not-email","Name <sample@example.test>","a b@example.test","a@@example.test","a@example","a@example..test",".a@example.test","a..b@example.test","a.@example.test"})
                Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("users"),JsonSerializer.SerializeToElement(new {email=value}),false));
        });
        Test("DOB strict calendar date optional and not future",() => {
            foreach(var value in new string?[] {null,"2000-02-29"}) {
                var values=ResourceCatalog.Validate(ResourceCatalog.Get("users"),JsonSerializer.SerializeToElement(new {date_of_birth=value}),false);
                if(value != null && !Equals(values["date_of_birth"],new DateOnly(2000,2,29))) throw new Exception("Not a DateOnly.");
            }
            foreach(var value in new[] {"2001-02-29","2000-2-29","29/02/2000","2000-02-29T00:00:00Z","",DateOnly.FromDateTime(DateTime.UtcNow).AddDays(1).ToString("yyyy-MM-dd")})
                Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("users"),JsonSerializer.SerializeToElement(new {date_of_birth=value}),false));
        });
        Test("telephone optional flexible and bounded",() => {
            foreach(var value in new string?[] {null,"", "+39 (02) 123-45 ext. 9",new string('1',50)})
                ResourceCatalog.Validate(ResourceCatalog.Get("users"),JsonSerializer.SerializeToElement(new {phone_number=value}),false);
            Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("users"),JsonSerializer.SerializeToElement(new {phone_number=new string('1',51)}),false));
        });
        Test("locale exactly it or en",() => {
            foreach(var value in new[] {"it","en"}) ResourceCatalog.Validate(ResourceCatalog.Get("users"),JsonSerializer.SerializeToElement(new {preferred_language=value}),false);
            foreach(var value in new string?[] {null,"","IT"," it ","fr"}) Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("users"),JsonSerializer.SerializeToElement(new {preferred_language=value}),false));
        });
        Test("profile mapping derived name and session locale",() => {
            var options=new Microsoft.EntityFrameworkCore.DbContextOptionsBuilder<AppDb>();
            Microsoft.EntityFrameworkCore.NpgsqlDbContextOptionsBuilderExtensions.UseNpgsql(options,"Host=unused;Database=unused;Username=unused");
            using var db=new AppDb(options.Options); var entity=db.Model.FindEntityType(typeof(User))!;
            foreach(var name in new[] {"FirstName","LastName","DateOfBirth","PhoneNumber","PreferredLanguage"})
                if(entity.FindProperty(name)==null) throw new Exception("Missing profile mapping: "+name);
            if(entity.FindProperty("DisplayName") != null || entity.FindProperty("FullName") != null) throw new Exception("Derived name persisted.");
            var user=JsonSerializer.Deserialize<User>("""{"FirstName":"First","LastName":"Last","PreferredLanguage":"en"}""")!;
            var session=JsonSerializer.SerializeToElement(new IdentityState(user,"sample","ignored",[]).Session);
            if(session.GetProperty("displayName").GetString() != "First Last" || session.GetProperty("preferredLanguage").GetString() != "en") throw new Exception("Incorrect session profile.");
        });
        Test("sixteen resources without generic settings",() => {if(ResourceCatalog.All.Count != 16) throw new Exception();});
        Test("unknown resource rejected",() => Reject(() => ResourceCatalog.Get("user"),404));
        Test("privilege injection rejected",() => Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("users"),Json("{\"username\":\"alice\",\"display_name\":\"Alice\",\"is_super_admin\":true}"),true)));
        Test("tenant injection rejected",() => Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("companies"),Json("{\"tenant_id\":\"00000000-0000-0000-0000-000000000001\"}"),false)));
        Test("duplicate keys rejected",() => Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("users"),Json("{\"username\":\"a\",\"username\":\"b\"}"),false)));
        Test("required fields enforced",() => Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("companies"),Json("{\"code\":\"A\"}"),true)));
        Test("boolean type enforced",() => Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("companies"),Json("{\"is_enabled\":\"true\"}"),false)));
        Test("reference uuid enforced",() => Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("sites"),Json("{\"company_id\":\"bad\"}"),false)));
        Test("NUL refused",() => Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("companies"),Json("{\"name\":\"a\\u0000b\"}"),false)));
        Test("isolated UTF16 surrogate refused as validation error",() => Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("groups"),Json("{\"name\":\"bad\\ud800value\"}"),false)));
        Test("valid record accepted",() => {if(ResourceCatalog.Validate(ResourceCatalog.Get("companies"),Json("{\"name\":\"A\",\"code\":\"A\"}"),true).Count != 2) throw new Exception();});
        Test("short passwords refused",() => Reject(() => Check.Password("short")));
        Test("password hash verified",() => { var a=new User(); var h=Security.Hasher.HashPassword(a,"long-test-password"); if(Security.Hasher.VerifyHashedPassword(a,h,"long-test-password")==Microsoft.AspNetCore.Identity.PasswordVerificationResult.Failed) throw new Exception(); });
        Test("tenant permissions not platform admin",() => Reject(() => new IdentityState(new User {TenantId=Guid.NewGuid()},"a","A",["tenants.read"]).Authorize("tenants","read"),403));
        Test("exact permission required",() => Reject(() => new IdentityState(new User(),"a","A",["users.read"]).Authorize("users","write"),403));
        Test("superadmin explicit",() => new IdentityState(new User {IsSuperAdmin=true},"a","A",[]).Authorize("tenants","create"));
        Test("cross tenant query refused",() => {
            var ctx=new DefaultHttpContext(); ctx.Request.QueryString=new QueryString("?tenantId="+Guid.NewGuid());
            Reject(() => new IdentityState(new User {TenantId=Guid.NewGuid()},"a","A",[]).Tenant(ctx,"companies"),403);
        });
        Test("superadmin requires tenant",() => Reject(() => new IdentityState(new User {IsSuperAdmin=true},"a","A",[]).Tenant(new DefaultHttpContext(),"companies")));
        Test("tenant defaults to own scope",() => {
            var id=Guid.NewGuid(); var state=new IdentityState(new User {TenantId=id},"a","A",[]);
            if(state.Tenant(new DefaultHttpContext(),"companies") != id) throw new Exception();
        });
        Test("EF user mapping",() => {
            var options=new Microsoft.EntityFrameworkCore.DbContextOptionsBuilder<AppDb>();
            Microsoft.EntityFrameworkCore.NpgsqlDbContextOptionsBuilderExtensions.UseNpgsql(options,"Host=unused;Database=unused;Username=unused");
            using var db=new AppDb(options.Options);
            var entity=db.Model.FindEntityType(typeof(User))!;
            if(Microsoft.EntityFrameworkCore.RelationalEntityTypeExtensions.GetTableName(entity) != "user" || Microsoft.EntityFrameworkCore.RelationalEntityTypeExtensions.GetSchema(entity) != "foundation") throw new Exception();
            var stamp=entity.FindProperty(nameof(User.SecurityStamp))!;
            if(Microsoft.EntityFrameworkCore.RelationalPropertyExtensions.GetColumnName(stamp) != "security_stamp") throw new Exception();
        });
        Test("canonical user model supports pending credentials",() => {
            if(typeof(User).GetProperty("UserId") != null || typeof(User).GetProperty("Email") == null || new User().PasswordHash != null)
                throw new Exception("User must be the sole identity, with email and nullable pending hash.");
        });
        Test("users map to canonical user",() => { if(ResourceCatalog.Get("users").Table != "user") throw new Exception(); });
        Test("users public projection exact whitelist",() => {
            var expected="json_build_object('id',t.id,'tenant_id',t.tenant_id,'username',t.username,'first_name',t.first_name,'last_name',t.last_name,'email',t.email,'date_of_birth',t.date_of_birth,'phone_number',t.phone_number,'preferred_language',t.preferred_language,'is_enabled',t.is_enabled,'created_at',t.created_at,'updated_at',t.updated_at)::text";
            if(ResourceCatalog.Projection(ResourceCatalog.Get("users")) != expected) throw new Exception("Public projection changed.");
        });
        Test("users server-managed fields refused",() => {
            foreach(var field in new[] {"id","tenant_id","password_hash","security_stamp","failed_attempts","locked_until","must_change_password","is_super_admin","created_at","updated_at"})
                Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("users"),Json("{\""+field+"\":null}"),false));
        });
        Test("users writable profile fields and default metadata",() => {
            var values=ResourceCatalog.Validate(ResourceCatalog.Get("users"),Json("""{"username":"pending","first_name":"First","last_name":"Last","email":"sample@example.test","is_enabled":false}"""),true);
            if(values.Count != 5 || !Equals(values["is_enabled"],false)) throw new Exception();
            var language=ResourceCatalog.Get("users").Fields.Single(f => f.Name == "preferred_language");
            if(language.Required || language.DefaultValue != "it" || !language.Options!.SequenceEqual(new[] {"it","en"})) throw new Exception();
            Reject(() => ResourceCatalog.Validate(ResourceCatalog.Get("users"),Json("""{"display_name":"Legacy"}"""),false));
        });
        Test("own global identity visible only in superadmin listing",() => {
            var users=ResourceCatalog.Get("users");
            var scope=ResourceCatalog.ListScope(users,new User {IsSuperAdmin=true});
            if(!scope.Contains("id=@viewer::uuid") || !scope.Contains("tenant_id IS NULL AND is_super_admin")) throw new Exception("Own global identity missing.");
            if(ResourceCatalog.ListScope(users,new User {TenantId=Guid.NewGuid()}) != ResourceCatalog.Scope(users)) throw new Exception("Tenant visibility widened.");
            if(ResourceCatalog.ListScope(ResourceCatalog.Get("companies"),new User {IsSuperAdmin=true}) != ResourceCatalog.Scope(ResourceCatalog.Get("companies"))) throw new Exception("Other resource widened.");
        });
        Test("global admin excluded from tenant mutation scope",() => {
            if(ResourceCatalog.Scope(ResourceCatalog.Get("users")) != "tenant_id=@tenant::uuid AND NOT is_super_admin") throw new Exception();
        });
        Test("EF nullable credentials and required email mapped",() => {
            var options=new Microsoft.EntityFrameworkCore.DbContextOptionsBuilder<AppDb>();
            Microsoft.EntityFrameworkCore.NpgsqlDbContextOptionsBuilderExtensions.UseNpgsql(options,"Host=unused;Database=unused;Username=unused");
            using var db=new AppDb(options.Options); var entity=db.Model.FindEntityType(typeof(User))!;
            if(entity.FindProperty("UserId") != null || entity.FindProperty("Email")?.IsNullable != false || entity.FindProperty("PasswordHash")?.IsNullable != true) throw new Exception();
        });
        Test("reserved table identifier quoted",() => {
            if(SqlNames.Table(ResourceCatalog.Get("users").Table) != "\"foundation\".\"user\"") throw new Exception();
        });
        Test("BP persistence schema is masterdata while numbering remains foundation",() => {
            foreach(var table in new[] {"business_partner", "business_partner_tax_identifier", "business_partner_address", "business_partner_address_usage", "business_partner_contact_channel"})
                if(SqlNames.Table(table) != "\"masterdata\".\""+table+"\"") throw new Exception("Wrong BP schema: "+table);
            if(SqlNames.Table(ResourceCatalog.Get("business-partners").Table) != "\"masterdata\".\"business_partner\"") throw new Exception("Resource lookup uses wrong schema");
            foreach(var table in new[] {"numbering_series", "numbering_counter", "business_partner_fake", "masterdata.business_partner"})
                if(SqlNames.Table(table) != "\"foundation\".\""+table+"\"") throw new Exception("Schema routing must use exact finite names");
        });
        Test("identifier quotes escaped without splitting",() => {
            if(SqlNames.Table("a\".b") != "\"foundation\".\"a\"\".b\"") throw new Exception();
        });
        Test("invalid identifiers refused",() => {
            foreach(var name in new[] {"", "bad\0name"})
            {
                try { SqlNames.Table(name); }
                catch(ArgumentException) { continue; }
                throw new Exception("Invalid identifier accepted.");
            }
        });
        Test("EF queries quote reserved user table",() => {
            var options=new Microsoft.EntityFrameworkCore.DbContextOptionsBuilder<AppDb>();
            Microsoft.EntityFrameworkCore.NpgsqlDbContextOptionsBuilderExtensions.UseNpgsql(options,"Host=unused;Database=unused;Username=unused");
            using var db=new AppDb(options.Options);
            var sql=Microsoft.EntityFrameworkCore.EntityFrameworkQueryableExtensions.ToQueryString(db.Users.Where(u => u.IsEnabled));
            if(!sql.Contains("FROM foundation.\"user\"")) throw new Exception("Reserved table not quoted.");
        });
        Test("persisted identity hash format remains compatible",() => {
            var hasher=new Microsoft.AspNetCore.Identity.PasswordHasher<object>(Microsoft.Extensions.Options.Options.Create(new Microsoft.AspNetCore.Identity.PasswordHasherOptions {IterationCount=210000}));
            var hash=hasher.HashPassword(new object(),"long-test-password");
            if(Security.Hasher.VerifyHashedPassword(new User(),hash,"long-test-password") != Microsoft.AspNetCore.Identity.PasswordVerificationResult.Success) throw new Exception();
        });
        Test("commercial tracer1 sales name company and optional code",() => {
            var r=ResourceCatalog.Get("sales-organizations");
            var company=Guid.NewGuid();
            var values=ResourceCatalog.Validate(r,JsonSerializer.SerializeToElement(new {name="Vendite",company_id=company}),true);
            if(values.Count!=2 || !Equals(values["company_id"],company) || values.ContainsKey("code")) throw new Exception("Sales create must require name+company only, without generated code.");
            Reject(() => ResourceCatalog.Validate(r,JsonSerializer.SerializeToElement(new {name="Vendite"}),true));
            Reject(() => ResourceCatalog.Validate(r,JsonSerializer.SerializeToElement(new {company_id=company}),true));
        });
        Test("commercial finite catalog and assign scope native isolation",() => {
            if(PermissionCatalog.Codes.Length!=147 || !Allowed("purchasing-organizations.assign_scope",["purchasing-organizations.assign_scope"])) throw new Exception("Catalogo finito richiesto, incluse Tax Foundation, Classification, Company Tax Configuration, Tax Determination e Tax Calculation e senza permessi generici Impostazioni.");
            foreach(var other in new[]{"read","create","update","delete"}) {
                if(Allowed("purchasing-organizations.assign_scope",["purchasing-organizations."+other]) || Allowed("purchasing-organizations."+other,["purchasing-organizations.assign_scope"])) throw new Exception("Coverage and profile authority conflated.");
            }
        });
        OptionalCodeSelfTests.Run(Test);
        Enginia360.Verification.Catalog.CatalogItemCompanyTests.Run(Test);
        Enginia360.Verification.Catalog.CatalogItemCompanyCreationTests.Run(Test);
        SiteClassificationSelfTests.Run(Test);
        if(Environment.GetEnvironmentVariable("RBAC_DB_TESTS") == "true")
            RbacTests.Run(services.GetRequiredService<IConfiguration>().GetConnectionString("Database")!,Test);
        Console.WriteLine("PERMISSION_CATALOG "+JsonSerializer.Serialize(PermissionCatalog.Codes));
        Console.WriteLine($"{count} tests passed; {failed} failed.");
        if(failed > 0) throw new Exception("Self-tests failed.");
    }
}
