using System.Data.Common;
using System.Security.Claims;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authentication.OpenIdConnect;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.IdentityModel.Tokens;
using Microsoft.AspNetCore.Antiforgery;

namespace Enginia360.Api.BrowserAuthentication;

public static class BrowserSessionModule
{
    public static IServiceCollection AddBrowserSessions(this IServiceCollection services, IConfiguration configuration)
    {
        if (!configuration.GetValue<bool>("BrowserSessions:Enabled"))
            return services;
        if (configuration["Authentication:Profile"] == "SyntheticLegacy"
            || !ValidHttps(configuration["BrowserSessions:PublicOrigin"], originOnly: true)
            || !ValidHttps(configuration["BrowserSessions:Authority"], originOnly: false)
            || string.IsNullOrWhiteSpace(configuration["BrowserSessions:ClientId"])
            || configuration["BrowserSessions:ClientId"] == configuration["Authentication:Audience"]
            || string.IsNullOrWhiteSpace(configuration["BrowserSessions:ClientSecret"]))
            throw new InvalidOperationException("Browser session configuration is invalid.");
        services.AddAntiforgery(options =>
        {
            options.HeaderName = "X-CSRF-TOKEN";
            options.Cookie.Name = "__Host-enginia360-csrf";
            options.Cookie.Path = "/";
            options.Cookie.HttpOnly = true;
            options.Cookie.SecurePolicy = CookieSecurePolicy.Always;
            options.Cookie.SameSite = SameSiteMode.Strict;
        });
        services.AddSingleton<TimeProvider>(TimeProvider.System);
        services.AddSingleton<ITicketStore, BoundedTicketStore>();
        services.AddDataProtection().UseEphemeralDataProtectionProvider();
        services.AddAuthentication(options =>
        {
            options.DefaultScheme = "browser-or-bearer";
            options.DefaultAuthenticateScheme = "browser-or-bearer";
            options.DefaultChallengeScheme = "browser-or-bearer";
        })
        .AddPolicyScheme("browser-or-bearer", null, options =>
            options.ForwardDefaultSelector = context => context.Request.Headers.ContainsKey("Authorization")
                ? JwtBearerDefaults.AuthenticationScheme : "browser")
        .AddCookie("browser", options =>
        {
            options.Cookie.Name = "__Host-enginia360-session";
            options.Cookie.Path = "/";
            options.Cookie.HttpOnly = true;
            options.Cookie.SecurePolicy = CookieSecurePolicy.Always;
            options.Cookie.SameSite = SameSiteMode.Lax;
            options.ExpireTimeSpan = BoundedTicketStore.Lifetime;
            options.SlidingExpiration = false;
            options.Events.OnValidatePrincipal = async context =>
            {
                var issuer = context.Principal?.FindFirstValue(ExternalIdentityResolver.IssuerClaim);
                var subject = context.Principal?.FindFirstValue(ExternalIdentityResolver.SubjectClaim);
                var resolved = issuer is not null && subject is not null
                    ? await context.HttpContext.RequestServices.GetRequiredService<ExternalIdentityResolver>()
                        .Resolve(issuer, subject, "browser", context.HttpContext.RequestAborted)
                    : null;
                if (resolved is null || resolved.FindFirstValue(ClaimTypes.NameIdentifier)
                    != context.Principal?.FindFirstValue(ClaimTypes.NameIdentifier))
                {
                    context.RejectPrincipal();
                    await context.HttpContext.SignOutAsync("browser");
                }
                else
                    context.ReplacePrincipal(resolved);
            };
            options.Events.OnRedirectToLogin = context =>
            {
                context.Response.StatusCode = 401;
                return Task.CompletedTask;
            };
            options.Events.OnRedirectToAccessDenied = context =>
            {
                context.Response.StatusCode = 403;
                return Task.CompletedTask;
            };
        })
        .AddOpenIdConnect("oidc", options =>
        {
            options.SignInScheme = "browser";
            options.Authority = configuration["BrowserSessions:Authority"];
            options.ClientId = configuration["BrowserSessions:ClientId"];
            options.ClientSecret = configuration["BrowserSessions:ClientSecret"];
            options.RequireHttpsMetadata = true;
            options.MapInboundClaims = false;
            options.ResponseType = "code";
            options.ResponseMode = "query";
            options.UsePkce = true;
            options.SaveTokens = false;
            options.GetClaimsFromUserInfoEndpoint = false;
            options.Scope.Clear();
            options.Scope.Add("openid");
            options.RemoteAuthenticationTimeout = TimeSpan.FromMinutes(5);
            options.ProtocolValidator.NonceLifetime = TimeSpan.FromMinutes(5);
            options.CorrelationCookie.SecurePolicy = CookieSecurePolicy.Always;
            options.NonceCookie.SecurePolicy = CookieSecurePolicy.Always;
            options.TokenValidationParameters = new()
            {
                ValidateIssuer = true,
                ValidIssuer = configuration["BrowserSessions:Authority"],
                ValidateAudience = true,
                ValidAudience = configuration["BrowserSessions:ClientId"],
                ValidateLifetime = true,
                RequireExpirationTime = true,
                RequireSignedTokens = true,
                ValidateIssuerSigningKey = true,
                ClockSkew = TimeSpan.Zero,
                ValidAlgorithms = [SecurityAlgorithms.RsaSha256],
            };
            options.Events.OnTokenValidated = context =>
            {
                // Retain only the handler-validated issuer across the default claim actions.
                context.Properties ??= new AuthenticationProperties();
                context.Properties.Items["verified-issuer"] = context.SecurityToken.Issuer;
                return Task.CompletedTask;
            };
            options.Events.OnTicketReceived = async context =>
            {
                var subjects = context.Principal?.FindAll("sub").ToArray() ?? [];
                context.Properties ??= new AuthenticationProperties();
                context.Properties.Items.TryGetValue("verified-issuer", out var issuer);
                ClaimsPrincipal? resolved = null;
                try
                {
                    if (subjects.Length == 1 && issuer is not null && issuer == configuration["BrowserSessions:Authority"])
                        resolved = await context.HttpContext.RequestServices.GetRequiredService<ExternalIdentityResolver>()
                            .Resolve(issuer, subjects[0].Value, "browser", context.HttpContext.RequestAborted);
                }
                catch (Exception error) when (error is DbException or TimeoutException)
                {
                    context.HttpContext.Items["IdentityStoreUnavailable"] = true;
                }
                if (resolved is null)
                {
                    context.HandleResponse();
                    context.Response.StatusCode = context.HttpContext.Items.ContainsKey("IdentityStoreUnavailable") ? 503 : 403;
                    await context.Response.WriteAsJsonAsync(new { error = "identity_not_assigned" });
                    return;
                }
                context.Principal = resolved;
                context.Properties ??= new AuthenticationProperties();
                context.Properties.IsPersistent = false;
                context.Properties.ExpiresUtc = DateTimeOffset.UtcNow + BoundedTicketStore.Lifetime;
            };
            options.Events.OnRemoteFailure = async context =>
            {
                context.HandleResponse();
                context.Response.StatusCode = context.HttpContext.Items.ContainsKey("IdentityStoreUnavailable") ? 503 : 400;
                await context.Response.WriteAsJsonAsync(new { error = "login_failed" });
            };
        });
        services.AddOptions<CookieAuthenticationOptions>("browser").Configure<ITicketStore>((options, store) => options.SessionStore = store);
        services.PostConfigure<OpenIdConnectOptions>("oidc", options =>
            options.ConfigurationManager = new HttpsOidcConfigurationManager(options.ConfigurationManager!, configuration["BrowserSessions:Authority"]!));
        return services;
    }

    private static bool ValidHttps(string? value, bool originOnly) =>
        Uri.TryCreate(value, UriKind.Absolute, out var uri)
        && uri.Scheme == "https" && uri.UserInfo.Length == 0
        && uri.Query.Length == 0 && uri.Fragment.Length == 0
        && (!originOnly || uri.AbsolutePath == "/")
        && value == (originOnly ? uri.GetLeftPart(UriPartial.Authority) : uri.AbsoluteUri.TrimEnd('/'));

    public static WebApplication UseBrowserSessionTransport(this WebApplication app)
    {
        if (!app.Configuration.GetValue<bool>("BrowserSessions:Enabled"))
            return app;
        var origin = app.Configuration["BrowserSessions:PublicOrigin"]!;
        app.Use(async (context, next) =>
        {
            // This profile uses end-to-end TLS. Forwarded headers are deliberately not trusted.
            if (!context.Request.IsHttps
                || "https://" + context.Request.Host != origin)
            {
                context.Response.StatusCode = 400;
                return;
            }
            context.Response.Headers.CacheControl = "no-store";
            context.Response.Headers["Referrer-Policy"] = context.Request.Path == "/signin-oidc" ? "no-referrer" : "same-origin";
            try
            {
                await next(context);
            }
            catch (Exception error) when (error is DbException or TimeoutException or BrowserIdentityConfigurationException)
            {
                context.Response.Clear();
                context.Response.StatusCode = 503;
                context.Response.Headers.CacheControl = "no-store";
                await context.Response.WriteAsJsonAsync(new { error = "store_unavailable" });
            }
        });
        return app;
    }

    public static WebApplication UseBrowserSessionCsrf(this WebApplication app)
    {
        if (!app.Configuration.GetValue<bool>("BrowserSessions:Enabled"))
            return app;
        var origin = app.Configuration["BrowserSessions:PublicOrigin"]!;
        app.Use(async (context, next) =>
        {
            var request = context.Request;
            var command = !HttpMethods.IsGet(request.Method) && !HttpMethods.IsHead(request.Method)
                && !HttpMethods.IsOptions(request.Method);
            var authCommand = request.Path.StartsWithSegments("/auth", StringComparison.OrdinalIgnoreCase);
            var cookieCommand = context.User.Identity?.IsAuthenticated == true
                && context.User.Identity.AuthenticationType == "browser"
                && request.Path.StartsWithSegments("/api", StringComparison.OrdinalIgnoreCase);
            if (command && (authCommand || cookieCommand))
            {
                try
                {
                    if ((request.Headers.Origin.Count > 0 && request.Headers.Origin != origin)
                        || request.Headers["Sec-Fetch-Site"] == "cross-site")
                        throw new AntiforgeryValidationException("Origin rejected.");
                    await context.RequestServices.GetRequiredService<IAntiforgery>().ValidateRequestAsync(context);
                }
                catch (AntiforgeryValidationException)
                {
                    context.Response.StatusCode = 400;
                    await context.Response.WriteAsJsonAsync(new { error = "csrf_invalid" });
                    return;
                }
            }
            await next(context);
        });
        return app;
    }

    public static WebApplication MapBrowserSessions(this WebApplication app)
    {
        if (!app.Configuration.GetValue<bool>("BrowserSessions:Enabled"))
            return app;
        app.MapPost("/auth/login", (HttpContext context) =>
        {
            // Fixed redirect only: no caller-controlled provider or return URL.
            return Results.Challenge(new AuthenticationProperties { RedirectUri = "/" }, ["oidc"]);
        });
        app.MapPost("/auth/logout", async (HttpContext context) =>
        {
            if (context.User.Identity?.IsAuthenticated != true)
                return Results.Unauthorized();
            await context.SignOutAsync("browser");
            return Results.Redirect("/");
        });
        app.MapGet("/auth/session", (HttpContext context) =>
        {
            context.Response.Headers.CacheControl = "no-store";
            return Results.Ok(new { authenticated = context.User.Identity?.IsAuthenticated == true });
        });
        app.MapGet("/auth/csrf", (HttpContext context, IAntiforgery antiforgery) =>
        {
            var tokens = antiforgery.GetAndStoreTokens(context);
            context.Response.Headers.CacheControl = "no-store";
            return Results.Ok(new { requestToken = tokens.RequestToken });
        });
        return app;
    }
}
