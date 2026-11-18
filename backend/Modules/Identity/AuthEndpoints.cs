using Enginia360.Api.Resources;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Shared.Validation;
using ResourceCatalog = global::Enginia360.Api.Resources.Resources;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Modules.Identity;

public static class AuthEndpoints
{
    public sealed record LoginInput(string Username,string Password,string? TenantCode);
    public sealed record PasswordInput(string CurrentPassword,string NewPassword);
    public sealed record ResetInput(string NewPassword);
    private static readonly User Dummy = new();
    private static readonly string DummyHash = Security.Hasher.HashPassword(Dummy,"dummy-password-not-used-for-login");
    private static readonly string[] ProfileNames = ["first_name","last_name","email","date_of_birth","phone_number","preferred_language"];
    private static readonly Resource ProfileResource = ResourceCatalog.Get("users") with { Fields=ResourceCatalog.Get("users").Fields.Where(f=>ProfileNames.Contains(f.Name,StringComparer.Ordinal)).ToArray() };

    private static Dictionary<string,object?> ProfileFields(User user) => new(StringComparer.Ordinal) {
        ["first_name"]=user.FirstName, ["last_name"]=user.LastName, ["email"]=user.Email,
        ["date_of_birth"]=user.DateOfBirth, ["phone_number"]=user.PhoneNumber, ["preferred_language"]=user.PreferredLanguage
    };
    private static object PublicProfile(User user)
    {
        var fields=ProfileFields(user); fields.Add("id",user.Id); fields.Add("username",user.Username); return fields;
    }
    private static (Dictionary<string,object?> Values,string? Current,string? New) ParseProfile(JsonElement body)
    {
        Check.Require(body.ValueKind==JsonValueKind.Object);
        var seen=new HashSet<string>(StringComparer.Ordinal);
        Dictionary<string,object?> values=new(StringComparer.Ordinal);
        string? current=null, next=null;
        foreach(var prop in body.EnumerateObject())
        {
            var name=ResourceCatalog.ReadName(prop);
            Check.Require(seen.Add(name));
            switch(name)
            {
                case "values": values=ResourceCatalog.Validate(ProfileResource,prop.Value,false); break;
                case "currentPassword": current=ResourceCatalog.ReadString(prop.Value); break;
                case "newPassword": next=ResourceCatalog.ReadString(prop.Value); break;
                default: throw new ApiException(400,"validation_error");
            }
        }
        var password=seen.Contains("currentPassword") || seen.Contains("newPassword");
        Check.Require(values.Count>0 || password);
        if(password) ValidateOwnPasswordInput(current,next);
        return (values,current,next);
    }
    private static void ApplyProfile(User user,Dictionary<string,object?> values)
    {
        foreach(var (name,value) in values)
            switch(name)
            {
                case "first_name": user.FirstName=(string)value!; break;
                case "last_name": user.LastName=(string)value!; break;
                case "email": user.Email=(string)value!; break;
                case "date_of_birth": user.DateOfBirth=(DateOnly?)value; break;
                case "phone_number": user.PhoneNumber=(string?)value; break;
                case "preferred_language": user.PreferredLanguage=(string)value!; break;
                default: throw new ApiException(400,"validation_error");
            }
    }
    private static void ValidateOwnPasswordInput(string? current,string? next)
    {
        Check.Require(current is {Length: >0 and <=256});
        Check.Password(next);
        Check.Require(!string.IsNullOrWhiteSpace(next));
    }
    private static void ChangeOwnPassword(User user,string current,string next)
    {
        ValidateOwnPasswordInput(current,next);
        Check.Require(user.PasswordHash!=null && Security.Hasher.VerifyHashedPassword(user,user.PasswordHash,current)!=PasswordVerificationResult.Failed,400,"current_password_invalid");
        Check.Require(Security.Hasher.VerifyHashedPassword(user,user.PasswordHash!,next)==PasswordVerificationResult.Failed);
        user.PasswordHash=Security.Hasher.HashPassword(user,next); user.MustChangePassword=false; user.SecurityStamp=Guid.NewGuid();
        user.FailedAttempts=0; user.LockedUntil=null;
    }

    public static void Map(WebApplication app)
    {
        app.MapGet("/api/profile",(HttpContext ctx)=>Results.Ok(PublicProfile(Security.State(ctx).User)));
        app.MapPut("/api/profile",async (HttpContext ctx,AppDb db,JsonElement body)=>{
            var state=Security.State(ctx); var user=state.User;
            var (values,current,next)=ParseProfile(body);
            var before=ProfileFields(user);
            // Valida prima di modificare il profilo; commit e rollback appartengono al middleware esistente.
            if(next!=null) ChangeOwnPassword(user,current!,next);
            ApplyProfile(user,values);
            await db.SaveChangesAsync();
            if(values.Count>0) await db.Audit(user.Id,user.TenantId,"profile_update","users",user.Id,new {before,after=ProfileFields(user)});
            if(next!=null)
            {
                await db.Audit(user.Id,user.TenantId,"password_change","users",user.Id);
                await Security.Issue(ctx,user,state.SelectedTenantId);
            }
            return Results.Ok(PublicProfile(user));
        });
        app.MapGet("/api/session",(HttpContext ctx) => Results.Ok(Security.State(ctx).Session));
        app.MapPost("/api/auth/login",async (HttpContext ctx,AppDb db,LoginInput input) => {
            Check.Require(input.Username is {Length: >0 and <=500} && input.Password is {Length: >0 and <=256} && (input.TenantCode == null || input.TenantCode.Length <=500));
            await using var tx=await db.Database.BeginTransactionAsync();
            await Security.Lock(db);
            var ip=ctx.Connection.RemoteIpAddress?.ToString() ?? "unknown";
            var key=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(ip)));
            var now=DateTimeOffset.UtcNow;
            var count=(int)(await db.Scalar("""
                INSERT INTO foundation.login_limit(key,window_start,attempts) VALUES (@key,@now,1)
                ON CONFLICT(key) DO UPDATE SET
                attempts=CASE WHEN foundation.login_limit.window_start < @now - interval '1 minute' THEN 1 ELSE foundation.login_limit.attempts+1 END,
                window_start=CASE WHEN foundation.login_limit.window_start < @now - interval '1 minute' THEN @now ELSE foundation.login_limit.window_start END
                RETURNING attempts
                """,("key",key),("now",now)))!;
            if(count > 30) { await tx.CommitAsync(); throw new ApiException(429,"rate_limited"); }
            Guid? tenant=null;
            bool validScope=true;
            if (!string.IsNullOrEmpty(input.TenantCode))
            {
                var found=await db.Scalar("SELECT id FROM foundation.tenant WHERE code=@code AND is_enabled",("code",input.TenantCode));
                validScope=found is Guid;
                tenant=found as Guid?;
            }
            var username=input.Username.ToLowerInvariant();
            var global=validScope ? await db.Users.SingleOrDefaultAsync(a => a.TenantId==null && a.Username.ToLower()==username) : null;
            var local=validScope && tenant != null ? await db.Users.SingleOrDefaultAsync(a => a.TenantId==tenant && a.Username.ToLower()==username) : null;
            // Verifica entrambi i candidati, anche fittizi, prima di scegliere l'identità.
            // Le credenziali globali prevalgono; quelle locali identificano solo l'utente del tenant.
            var globalResult=Security.Hasher.VerifyHashedPassword(global ?? Dummy,global?.PasswordHash ?? DummyHash,input.Password);
            var localResult=Security.Hasher.VerifyHashedPassword(local ?? Dummy,local?.PasswordHash ?? DummyHash,input.Password);
            var globalMatches=global?.PasswordHash != null && globalResult != PasswordVerificationResult.Failed;
            var localMatches=local?.PasswordHash != null && localResult != PasswordVerificationResult.Failed;
            var user=globalMatches ? global : localMatches ? local : local ?? global;
            var result=user == global ? globalResult : localResult;
            var state=user == null ? null : await Security.Load(db,user.Id,selectedTenantId:tenant);
            if(state == null || user!.PasswordHash == null || result == PasswordVerificationResult.Failed || user!.LockedUntil > now)
            {
                var errorCode="login_details_invalid";
                if(!validScope) errorCode="invalid_organization_code";
                else if(user?.PasswordHash != null && result != PasswordVerificationResult.Failed)
                {
                    // Lo stato dell'utenza è comunicato soltanto dopo la verifica della password.
                    if(!user.IsEnabled) errorCode="account_disabled";
                    else if(user.LockedUntil > now) errorCode="account_temporarily_locked";
                }
                // Una collisione non aggira il blocco di nessuno dei due utenti.
                // Un accesso locale riuscito non penalizza l'utenza globale omonima.
                foreach(var candidate in new[] {global,local}.Where(a => a != null).Cast<User>())
                {
                    if(candidate.LockedUntil > now) continue;
                    candidate.FailedAttempts++;
                    if(candidate.FailedAttempts >= 5) { candidate.LockedUntil=now.AddMinutes(15); candidate.SecurityStamp=Guid.NewGuid(); }
                }
                await db.SaveChangesAsync();
                await db.Audit(user?.Id,tenant,"login_failed","users",user?.Id);
                await tx.CommitAsync();
                throw new ApiException(401,errorCode);
            }
            user!.FailedAttempts=0; user.LockedUntil=null;
            if(result == PasswordVerificationResult.SuccessRehashNeeded) user.PasswordHash=Security.Hasher.HashPassword(user,input.Password);
            await db.SaveChangesAsync(); await db.Audit(user.Id,user.TenantId,"login","users",user.Id);
            await tx.CommitAsync();
            await Security.Issue(ctx,user,state.SelectedTenantId);
            return Results.Ok(state.Session);
        });
        app.MapPost("/api/auth/logout",async (HttpContext ctx,AppDb db) => {
            var a=Security.State(ctx).User; a.SecurityStamp=Guid.NewGuid();
            await db.SaveChangesAsync(); await db.Audit(a.Id,a.TenantId,"logout","users",a.Id);
            await ctx.SignOutAsync(); return Results.NoContent();
        });
        app.MapPut("/api/auth/password",async (HttpContext ctx,AppDb db,PasswordInput input) => {
            var a=Security.State(ctx).User;
            ChangeOwnPassword(a,input.CurrentPassword,input.NewPassword);
            await db.SaveChangesAsync(); await db.Audit(a.Id,a.TenantId,"password_change","users",a.Id);
            await Security.Issue(ctx,a,Security.State(ctx).SelectedTenantId); return Results.NoContent();
        });
        app.MapPut("/api/users/{id:guid}/password",async (HttpContext ctx,AppDb db,Guid id,ResetInput input) => {
            var state=Security.State(ctx); await Security.Authorize(ctx,"users.reset_password");
            var tenant=state.Tenant(ctx,"users"); Check.Password(input.NewPassword);
            var a=await db.Users.SingleOrDefaultAsync(a => a.Id==id && a.TenantId==tenant && !a.IsSuperAdmin)
                ?? throw new ApiException(404,"not_found");
            a.PasswordHash=Security.Hasher.HashPassword(a,input.NewPassword); a.MustChangePassword=true; a.SecurityStamp=Guid.NewGuid();
            a.FailedAttempts=0; a.LockedUntil=null;
            await db.SaveChangesAsync(); await db.Audit(state.User.Id,tenant,"password_reset","users",id);
            return Results.NoContent();
        });
    }
}
