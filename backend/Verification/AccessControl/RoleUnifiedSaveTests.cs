using Enginia360.Api.Resources;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.AccessControl;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using System.Reflection;
using System.Text.Json;

namespace Enginia360.Verification.AccessControl;

public static class RoleUnifiedSaveTests
{
    // Native parser/policy proof: denied commands must never touch even a database handle.
    public static void RunNative(Action<string,Action> test)
    {
        var services=new ServiceCollection(); services.AddLogging(); PermissionCatalog.Configure(services);
        using var provider=services.BuildServiceProvider();
        void Refuse(string body,string[] grants,int status,Guid? id=null,string resource="roles",bool foreignTenant=false)
        {
            var ctx=new DefaultHttpContext {RequestServices=provider};
            var user=new User {TenantId=Guid.NewGuid(),Username="role-native",FirstName="Role",LastName="Native",Email="native@example.test",IsEnabled=true};
            ctx.Items["identity"]=new IdentityState(user,user.Username,user.FullName,grants);
            if(foreignTenant) ctx.Request.QueryString=new QueryString("?tenantId="+Guid.NewGuid());
            var save=typeof(DataEndpoints).GetMethod("Save",BindingFlags.Static|BindingFlags.NonPublic)!;
            try {
                var result=(Task<IResult>)save.Invoke(null,[ctx,null,resource,id,JsonSerializer.Deserialize<JsonElement>(body)])!;
                result.GetAwaiter().GetResult();
                throw new Exception("Expected refusal before database access.");
            } catch(ApiException e) {if(e.Status!=status) throw new Exception($"Expected {status}, actual {e.Status}: {body}");}
        }
        var id=Guid.NewGuid();
        test("role unified native: permissions-only authority cannot assign companies",()=>
            Refuse("{\"companyIds\":[]}",["roles.assign_permissions"],403,id));
        test("role unified native: update authority cannot assign companies",()=>
            Refuse("{\"values\":{\"name\":\"Denied\"},\"companyIds\":[]}",["roles.update"],403,id));
        test("role unified native: company authority cannot change values",()=>
            Refuse("{\"values\":{\"name\":\"Denied\"},\"companyIds\":[]}",["roles.assign_companies"],403,id));
        test("role unified native: create requires create and company gates",()=> {
            Refuse("{\"values\":{\"name\":\"Denied\"},\"companyIds\":[]}",["roles.create"],403);
            Refuse("{\"values\":{\"name\":\"Denied\"},\"companyIds\":[]}",["roles.assign_companies"],403);
        });
        test("role unified native: combined links require all independent gates",()=>
            Refuse("{\"links\":{\"role-permissions\":[]},\"companyIds\":[]}",["roles.assign_companies"],403,id));
        test("role unified native: companyIds is forbidden on other resources",()=>
            Refuse("{\"companyIds\":[]}",[],400,id,"groups"));
        test("role unified native: create cannot omit values",()=>
            Refuse("{\"companyIds\":[]}",["roles.create","roles.assign_companies"],400));
        test("role unified native: company-only actor cannot override tenant",()=>
            Refuse("{\"companyIds\":[]}",["roles.assign_companies"],403,id,foreignTenant:true));
        test("role unified native: malformed company field refuses before authorization or DB",()=> {
            foreach(var body in new[]{"{\"companyIds\":null}","{\"companyIds\":{}}","{\"companyIds\":[],\"companyIds\":[]}","{\"companyIds\":[null]}","{\"companyIds\":[42]}","{\"companyIds\":[\"bad\"]}","{\"companyIds\":[\"00000000-0000-0000-0000-000000000000\"]}"})
                Refuse(body,[],400,id);
        });
        test("role unified native: shared parser accepts empty and exact 1000 UUIDs",()=> {
            if(RoleCompanyEndpoints.Parse(JsonSerializer.SerializeToElement(Array.Empty<string>())).Count!=0) throw new Exception("Empty replacement rejected.");
            var ids=Enumerable.Range(0,1000).Select(_=>Guid.NewGuid()).ToArray();
            if(!RoleCompanyEndpoints.Parse(JsonSerializer.SerializeToElement(ids)).SetEquals(ids)) throw new Exception("1000 IDs rejected or changed.");
        });
        test("role unified native: shared parser rejects duplicates malformed and oversized",()=> {
            var uuid=Guid.NewGuid();
            foreach(var raw in new[]{JsonSerializer.Serialize(new[]{uuid,uuid}),JsonSerializer.Serialize(new[]{uuid.ToString("N")}),JsonSerializer.Serialize(Enumerable.Range(0,1001).Select(_=>Guid.NewGuid()).ToArray()),"null","{}","[null]","[false]","[\"\\ud800\"]","[\"00000000-0000-0000-0000-000000000000\"]"}) {
                try {RoleCompanyEndpoints.Parse(JsonSerializer.Deserialize<JsonElement>(raw)); throw new Exception("Invalid company IDs accepted: "+raw);}
                catch(ApiException e) when(e.Status==400) { }
            }
        });
    }
}
