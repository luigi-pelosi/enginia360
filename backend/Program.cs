using Enginia360.Api.Resources;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.AccessControl;
using Enginia360.Modules.Geography;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Enginia360.Verification.Geography;
using Enginia360.Verification.Organizations;
using Enginia360.Verification.Shared;
using GeographyCatalog = global::Enginia360.Modules.Geography.Geography;
using System.Security.Claims;
using System.Text.Json;
using Microsoft.AspNetCore.Antiforgery;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.EntityFrameworkCore;
using Npgsql;

var builder = WebApplication.CreateBuilder(args.Length > 0 && args[0] is "bootstrap" or "self-test" or "self-test-tax" or "self-test-tax-classification" or "self-test-company-tax" or "self-test-tax-determination" or "self-test-tax-calculation" or "self-test-site-addresses" or "import-geography" or "self-test-geography" ? [] : args);
builder.WebHost.ConfigureKestrel(k => { k.Limits.MaxRequestBodySize=65536; k.Limits.RequestHeadersTimeout=TimeSpan.FromSeconds(15); });
builder.Logging.ClearProviders();
builder.Logging.AddConsole();
builder.Logging.AddFilter("Microsoft.EntityFrameworkCore.Database.Command", LogLevel.None);
builder.Services.Configure<Microsoft.AspNetCore.Routing.RouteHandlerOptions>(o => o.ThrowOnBadRequest=true);
builder.Services.ConfigureHttpJsonOptions(o => { o.SerializerOptions.UnmappedMemberHandling=System.Text.Json.Serialization.JsonUnmappedMemberHandling.Disallow; o.SerializerOptions.MaxDepth=32; });
builder.Services.AddDbContext<AppDb>(o => o.UseNpgsql(builder.Configuration.GetConnectionString("Database") ?? throw new InvalidOperationException("Database configuration required.")));
builder.Services.AddDataProtection().PersistKeysToFileSystem(new DirectoryInfo("/app/keys")).SetApplicationName("Enginia360");
builder.Services.AddAntiforgery(o => { o.HeaderName="X-CSRF-TOKEN"; o.Cookie.Name="enginia360.csrf"; o.Cookie.HttpOnly=true; o.Cookie.SameSite=SameSiteMode.Strict; o.Cookie.SecurePolicy=CookieSecurePolicy.Always; });
builder.Services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme).AddCookie(o => {
    o.Cookie.Name="enginia360.session"; o.Cookie.HttpOnly=true; o.Cookie.SameSite=SameSiteMode.Strict; o.Cookie.SecurePolicy=CookieSecurePolicy.Always;
    o.ExpireTimeSpan=TimeSpan.FromHours(8); o.SlidingExpiration=false;
    o.Events.OnRedirectToLogin = c => { c.Response.StatusCode=401; return Task.CompletedTask; };
    o.Events.OnRedirectToAccessDenied = c => { c.Response.StatusCode=403; return Task.CompletedTask; };
});
PermissionCatalog.Configure(builder.Services);
var app = builder.Build();
if (args.Length > 0 && args[0] == "bootstrap")
{
    try { Check.Require(args.Length == 2); await Security.Bootstrap(app.Services,args[1]); }
    catch { Console.Error.WriteLine("Bootstrap failed; no credentials disclosed."); Environment.ExitCode=1; }
    return;
}
if (args.Length > 0 && args[0] == "import-geography")
{
    try { Check.Require(args.Length==2); await GeographyCatalog.Import(app.Services,args[1]); }
    catch { Console.Error.WriteLine("Geography import failed."); Environment.ExitCode=1; }
    return;
}

if (args.Length > 0 && args[0] == "self-test-geography") { GeographySelfTests.Run(app.Services); return; }
if (args.Length > 0 && args[0] == "self-test-bp-phase2") { await BusinessPartnerPhase2Tests.Run(builder.Configuration.GetConnectionString("Database")!); return; }
if (args.Length > 0 && args[0] == "self-test") { SelfTests.Run(app.Services); return; }
if (args.Length > 0 && args[0] == "self-test-tax") { Enginia360.Verification.TaxManagement.TaxSelfTests.Run(); return; }
if (args.Length > 0 && args[0] == "self-test-tax-classification") { Enginia360.Verification.TaxManagement.ClassificationSelfTests.Run(); return; }
if (args.Length > 0 && args[0] == "self-test-company-tax") { Enginia360.Verification.TaxManagement.CompanyTaxSelfTests.Run(); return; }
if (args.Length > 0 && args[0] == "self-test-tax-determination") { Enginia360.Verification.TaxManagement.TaxDeterminationSelfTests.Run(); return; }
if (args.Length > 0 && args[0] == "self-test-tax-calculation") { Enginia360.Verification.TaxManagement.TaxCalculationSelfTests.Run(); return; }
if (args.Length > 0 && args[0] == "self-test-site-addresses") { SiteAddressSelfTests.Run(app.Services); return; }
var origin = app.Configuration["App:Origin"];
if (!Uri.TryCreate(origin,UriKind.Absolute,out var originUri) || originUri.GetLeftPart(UriPartial.Authority) != origin || originUri.Scheme != "https")
    throw new InvalidOperationException("Canonical HTTPS App:Origin required (without trailing slash).");
app.Use(async (ctx,next) => {
    // Il calcolo multi-riga ha un limite dedicato; gli altri endpoint restano a 64 KiB.
    if (ctx.Request.Method == "POST" && ctx.Request.Path is var calculationPath &&
        (calculationPath == "/api/tax/calculations" || calculationPath == "/api/tax/calculations/simulate"))
    {
        var bodyLimit = ctx.Features.Get<IHttpMaxRequestBodySizeFeature>();
        if (bodyLimit is {IsReadOnly: false}) bodyLimit.MaxRequestBodySize = 1024 * 1024;
    }
    // TLS termina sull'ingresso privato; lo schema deriva dall'origine configurata, non da header del client.
    ctx.Request.Scheme=originUri.Scheme;
    ctx.Response.Headers.CacheControl="no-store";
    ctx.Response.Headers.XContentTypeOptions="nosniff";
    try { await next(); }
    catch (Exception ex)
    {
        var (status,code) = ex switch {
            ApiException e => (e.Status,e.Code),
            AntiforgeryValidationException => (400,"validation_error"),
            BadHttpRequestException e => (e.StatusCode,"validation_error"),
            JsonException => (400,"validation_error"),
            ArgumentException => (400,"validation_error"),
            PostgresException p when p.SqlState is "23505" or "23503" or "23001" => (409,"conflict"),
            PostgresException p when p.SqlState is "23514" or "23502" or "22001" or "22P02" or "22P05" => (400,"validation_error"),
            DbUpdateException e when e.InnerException is PostgresException p && p.SqlState is "23505" or "23503" or "23001" => (409,"conflict"),
            _ => (500,"server_error")
        };
        if (status == 500) app.Logger.LogError("Request failed ({ExceptionType}).",ex.GetType().Name);
        ctx.Response.Clear(); ctx.Response.StatusCode=status;
        ctx.Response.Headers.CacheControl="no-store";
        ctx.Response.Headers.XContentTypeOptions="nosniff";
        await ctx.Response.WriteAsJsonAsync(ex is ApiException { Field: not null } error
            ? (object)new { code, field = error.Field } : new { code });
    }
});
app.UseAuthentication();
app.Use(async (ctx,next) => {
    if (ctx.Request.Method is "POST" or "PUT" or "PATCH" or "DELETE")
    {
        Check.Require(ctx.Request.Headers.Origin.Count == 1 && ctx.Request.Headers.Origin.ToString() == origin,403,"forbidden");
        await ctx.RequestServices.GetRequiredService<IAntiforgery>().ValidateRequestAsync(ctx);
    }
    if (!ctx.Request.Path.StartsWithSegments("/api") || ctx.Request.Path == "/api/health" || ctx.Request.Path == "/api/auth/login" || ctx.Request.Path == "/api/auth/csrf") { await next(); return; }
    var db=ctx.RequestServices.GetRequiredService<AppDb>();
    await using var tx=await db.Database.BeginTransactionAsync();
    // Serializza la verifica fresca delle autorizzazioni con le mutazioni amministrative.
    await Security.Lock(db);
    Check.Require(Guid.TryParse(ctx.User.FindFirstValue(ClaimTypes.NameIdentifier),out var id),401,"invalid_credentials");
    Guid? selectedTenantId=Guid.TryParse(ctx.User.FindFirstValue(Security.SelectedTenantClaim),out var selected) ? selected : null;
    var state=await Security.Load(db,id,ctx.User.FindFirstValue("stamp"),selectedTenantId);
    Check.Require(state != null,401,"invalid_credentials");
    ctx.Items["identity"]=state;
    Check.Require(!state!.User.MustChangePassword || ctx.Request.Path is var path && (path == "/api/session" || path == "/api/auth/password" || path == "/api/auth/logout"),403,"password_change_required");
    if(ctx.Request.Method == "GET" && ctx.Request.Path == AddressLookup.Path)
    {
        await AddressLookup.Prepare(ctx,db);
        await tx.CommitAsync();
        await next();
        return;
    }
    var originalBody=ctx.Response.Body;
    await using var buffer=new MemoryStream();
    ctx.Response.Body=buffer;
    try
    {
        await next();
        if(ctx.Response.StatusCode < 400) await tx.CommitAsync();
        else await tx.RollbackAsync();
        ctx.Response.Body=originalBody;
        buffer.Position=0;
        await buffer.CopyToAsync(originalBody,ctx.RequestAborted);
    }
    finally { ctx.Response.Body=originalBody; }
});
app.MapGet("/api/health",async (AppDb db) => { await db.Database.OpenConnectionAsync(); await db.Scalar("SELECT 1"); return Results.Ok(new {status="ok"}); });
app.MapGet("/api/auth/csrf",(HttpContext ctx,IAntiforgery csrf) => Results.Ok(new {token=csrf.GetAndStoreTokens(ctx).RequestToken}));
AuthEndpoints.Map(app);
DataEndpoints.Map(app);
AddressLookup.Map(app);
GeographyCatalog.Map(app);
Enginia360.Modules.Payments.PaymentMethodsEndpoints.Map(app);
Enginia360.Modules.Payments.PaymentTermsEndpoints.Map(app);
Enginia360.Modules.Payments.PaymentDefaultsEndpoints.Map(app);
Enginia360.Modules.Catalog.CatalogEndpoints.Map(app);
Enginia360.Modules.Catalog.CatalogItemEndpoints.Map(app);
Enginia360.Modules.Catalog.CatalogItemCompanyEndpoints.Map(app);
Enginia360.Modules.TaxManagement.TaxEndpoints.Map(app);
Enginia360.Modules.TaxManagement.TaxClassificationEndpoints.Map(app);
Enginia360.Modules.TaxManagement.CompanyTaxEndpoints.Map(app);
Enginia360.Modules.TaxManagement.TaxRuleEndpoints.Map(app);
Enginia360.Modules.TaxManagement.TaxDeterminationEndpoints.Map(app);
Enginia360.Modules.TaxManagement.TaxCalculationEndpoints.Map(app);
app.MapFallback("/api/{**path}",() => Results.Json(new {code="not_found"},statusCode:404));
await app.RunAsync();
