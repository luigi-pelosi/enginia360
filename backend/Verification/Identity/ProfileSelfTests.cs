using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using System.Reflection;
using System.Text.Json;
using Microsoft.AspNetCore.Identity;

namespace Enginia360.Verification.Identity;

public static class ProfileSelfTests
{
    static object? Call(string name,params object?[] args)
    {
        var method=typeof(AuthEndpoints).GetMethod(name,BindingFlags.NonPublic|BindingFlags.Static)
            ?? throw new Exception("Missing self-profile primitive: "+name);
        try { return method.Invoke(null,args); }
        catch(TargetInvocationException e) when(e.InnerException != null)
        { System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(e.InnerException).Throw(); throw; }
    }
    static (Dictionary<string,object?> Values,string? Current,string? New) Parse(string json) =>
        ((Dictionary<string,object?>,string?,string?))Call("ParseProfile",JsonSerializer.Deserialize<JsonElement>(json))!;
    static void Refuse(Action action,string code="validation_error")
    {
        try {action();} catch(ApiException e) when(e.Status==400 && e.Code==code) {return;}
        throw new Exception("Expected profile refusal: "+code);
    }
    public static void Run(Action<string,Action> test)
    {
        test("self profile public projection contains exactly eight safe fields",()=>{
            var user=new User {Username="self",FirstName="First",LastName="Last",Email="self@example.test",IsSuperAdmin=true,PasswordHash="not-public"};
            var json=JsonSerializer.SerializeToElement(Call("PublicProfile",user));
            var expected=new[]{"id","username","first_name","last_name","email","date_of_birth","phone_number","preferred_language"};
            if(!json.EnumerateObject().Select(p=>p.Name).Order().SequenceEqual(expected.Order())) throw new Exception("Unsafe profile projection");
        });
        test("self profile six fields reuse user validation and normalization",()=>{
            var parsed=Parse("""{"values":{"first_name":"  Élodie  李 ","last_name":" Last ","email":" self@example.test ","date_of_birth":"2000-01-02","phone_number":null,"preferred_language":"en"}}""");
            if(parsed.Values.Count!=6 || !Equals(parsed.Values["first_name"],"Élodie 李") || !Equals(parsed.Values["email"],"self@example.test") || parsed.Values["date_of_birth"] is not DateOnly) throw new Exception("Validation not reused");
        });
        test("self profile rejects authority identity unknown and duplicate fields",()=>{
            foreach(var key in new[]{"id","username","is_enabled","is_super_admin","tenant_id","grants","password_hash","security_stamp","unknown"})
                Refuse(()=>Parse("{\"values\":{\""+key+"\":\"x\"}}"));
            foreach(var raw in new[]{"{}","{\"values\":{}}","{\"values\":null}","{\"tenantId\":null}","{\"values\":{\"first_name\":\"a\",\"first_name\":\"b\"}}","{\"values\":{\"first_name\":\"a\"},\"values\":{\"last_name\":\"b\"}}"}) Refuse(()=>Parse(raw));
        });
        test("self profile invalid field cases use shared metadata",()=>{
            foreach(var raw in new[]{"{\"email\":\"bad\"}","{\"first_name\":null}","{\"last_name\":\" \"}","{\"preferred_language\":null}","{\"preferred_language\":\"fr\"}","{\"date_of_birth\":\"3000-01-01\"}","{\"phone_number\":\""+new string('1',51)+"\"}"}) Refuse(()=>Parse("{\"values\":"+raw+"}"));
        });
        test("self profile optional password requires complete pair",()=>{
            foreach(var raw in new[]{"{\"currentPassword\":\"old\"}","{\"newPassword\":\"long-enough-new-password\"}","{\"currentPassword\":null,\"newPassword\":\"long-enough-new-password\"}","{\"currentPassword\":\"\",\"newPassword\":\"long-enough-new-password\"}","{\"currentPassword\":\"old\",\"newPassword\":\"short\"}","{\"currentPassword\":\"old\",\"currentPassword\":\"old\",\"newPassword\":\"long-enough-new-password\"}"}) Refuse(()=>Parse(raw));
            var parsed=Parse("{\"currentPassword\":\"old-password-for-test\",\"newPassword\":\"new-password-for-test\"}");
            if(parsed.Values.Count!=0 || parsed.Current==null || parsed.New==null) throw new Exception("Password-only unsupported");
        });
        test("self profile rejects whitespace-only new password before mutation",()=>{
            Refuse(()=>Parse(JsonSerializer.Serialize(new {currentPassword="current-password-test",newPassword=new string(' ',14)})));
            var user=new User(); user.PasswordHash=Security.Hasher.HashPassword(user,"current-password-test");
            var before=JsonSerializer.Serialize(user);
            Refuse(()=>Call("ChangeOwnPassword",user,"current-password-test",new string(' ',14)));
            if(JsonSerializer.Serialize(user)!=before) throw new Exception("Blank password mutated user");
        });
        test("self profile patch preserves identity authority hash and stamp",()=>{
            var user=new User {Username="fixed",TenantId=Guid.NewGuid(),IsSuperAdmin=false,PasswordHash="hash",MustChangePassword=false,FirstName="Before",LastName="Keep"};
            var before=JsonSerializer.Serialize(user); var stamp=user.SecurityStamp;
            Call("ApplyProfile",user,Parse("{\"values\":{\"first_name\":\"After\",\"phone_number\":null}}").Values);
            if(user.FirstName!="After" || user.LastName!="Keep" || user.PasswordHash!="hash" || user.SecurityStamp!=stamp || user.Username!="fixed" || user.TenantId==null || user.IsSuperAdmin || user.MustChangePassword) throw new Exception("Patch modified nonprofile fields");
        });
        test("own password invalid current leaves user unchanged and has specific code",()=>{
            var user=new User(); user.PasswordHash=Security.Hasher.HashPassword(user,"current-password-test");
            var before=JsonSerializer.Serialize(user);
            Refuse(()=>Call("ChangeOwnPassword",user,"wrong-password-test","replacement-password-test"),"current_password_invalid");
            Refuse(()=>Call("ChangeOwnPassword",user,"current-password-test","current-password-test"));
            if(JsonSerializer.Serialize(user)!=before) throw new Exception("Rejected password mutated state");
        });
        test("shared own password mutation rotates stamp clears forced gate and lock",()=>{
            var user=new User {FailedAttempts=4,LockedUntil=DateTimeOffset.UtcNow.AddHours(1)};
            user.PasswordHash=Security.Hasher.HashPassword(user,"current-password-test"); var stamp=user.SecurityStamp;
            Call("ChangeOwnPassword",user,"current-password-test","replacement-password-test");
            if(user.SecurityStamp==stamp || user.MustChangePassword || user.FailedAttempts!=0 || user.LockedUntil!=null || Security.Hasher.VerifyHashedPassword(user,user.PasswordHash!,"replacement-password-test")==PasswordVerificationResult.Failed) throw new Exception("Password mutation incomplete");
        });
    }
}
