using System.Data.Common;
using System.Net.Http.Json;
using System.Security.Claims;
using Enginia360.Api.BrowserAuthentication;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;

namespace Enginia360.Api.OrganizationAccess;

public static class OrganizationAccessModule
{
    public const string ContextCapability = "organization-context",
        ReadPermission = "organization-context.read",
        WritePermission = "organization-context.write";

    public static IServiceCollection AddOrganizationAccess(
        this IServiceCollection services,
        IConfiguration configuration
    )
    {
        var connection =
            configuration.GetConnectionString("OrganizationAccess")
            ?? throw new InvalidOperationException(
                "ConnectionStrings:OrganizationAccess is required."
            );
        var issuer =
            configuration["Authentication:ValidIssuer"]
            ?? throw new InvalidOperationException("Authentication:ValidIssuer is required.");
        var audience =
            configuration["Authentication:Audience"]
            ?? throw new InvalidOperationException("Authentication:Audience is required.");
        services.AddDbContext<OrganizationAccessDbContext>(o => o.UseNpgsql(connection));
        services.AddScoped<OrganizationContextService>();
        services.AddScoped<ExternalIdentityResolver>();
        var syntheticLegacy = configuration["Authentication:Profile"] == "SyntheticLegacy"
            && !configuration.GetValue<bool>("BrowserSessions:Enabled");
        services.AddHttpClient();
        services
            .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
            .AddJwtBearer(o =>
            {
                var authority = configuration["Authentication:Authority"];
                if (!string.IsNullOrWhiteSpace(authority))
                    o.Authority = authority;
                var metadata = configuration["Authentication:MetadataAddress"];
                if (!string.IsNullOrWhiteSpace(metadata))
                    o.MetadataAddress = metadata;
                o.Audience = audience;
                o.RequireHttpsMetadata = configuration.GetValue(
                    "Authentication:RequireHttpsMetadata",
                    true
                );
                o.MapInboundClaims = syntheticLegacy;
                o.Events = new JwtBearerEvents
                {
                    OnTokenValidated = async context =>
                    {
                        if (syntheticLegacy)
                            return;
                        var subjects = context.Principal?.FindAll("sub").ToArray() ?? [];
                        if (context.SecurityToken.Issuer != context.Options.TokenValidationParameters.ValidIssuer
                            || subjects.Length != 1)
                        {
                            context.Fail("identity_not_assigned");
                            return;
                        }
                        try
                        {
                            var principal = await context.HttpContext.RequestServices
                                .GetRequiredService<ExternalIdentityResolver>()
                                .Resolve(context.SecurityToken.Issuer, subjects[0].Value,
                                    JwtBearerDefaults.AuthenticationScheme, context.HttpContext.RequestAborted);
                            if (principal is null)
                                context.Fail("identity_not_assigned");
                            else
                                context.Principal = principal;
                        }
                        catch (Exception error) when (error is DbException or TimeoutException)
                        {
                            context.HttpContext.Items["IdentityStoreUnavailable"] = true;
                            context.Fail("identity_store_unavailable");
                        }
                    },
                    OnChallenge = context =>
                    {
                        if (context.HttpContext.Items.ContainsKey("IdentityStoreUnavailable"))
                        {
                            context.HandleResponse();
                            context.Response.StatusCode = StatusCodes.Status503ServiceUnavailable;
                        }
                        return Task.CompletedTask;
                    },
                };
                o.TokenValidationParameters = new TokenValidationParameters
                {
                    ValidateIssuer = true,
                    ValidIssuer = issuer,
                    ValidateAudience = true,
                    ValidAudience = audience,
                    ValidateLifetime = true,
                    ValidateIssuerSigningKey = true,
                    ClockSkew = TimeSpan.Zero,
                    NameClaimType = "preferred_username",
                };
            });
        services.AddAuthorization();
        services
            .AddHealthChecks()
            .AddDbContextCheck<OrganizationAccessDbContext>("postgresql", tags: ["external"]);
        return services;
    }

    public static WebApplication MapOrganizationAccess(this WebApplication app)
    {
        if (app.Configuration["Authentication:Profile"] == "SyntheticLegacy"
            && !app.Configuration.GetValue<bool>("BrowserSessions:Enabled")
            && app.Configuration.GetValue<bool>("DevelopmentTestLogin:Enabled"))
            app.MapPost("/api/v1/development/login", DevelopmentLogin);
        var g = app.MapGroup("/api/v1/organization").RequireAuthorization();
        g.MapGet(
            "/contexts",
            async (ClaimsPrincipal u, OrganizationContextService s, CancellationToken c) =>
                Subject(u) is string sub
                    ? Results.Ok(await s.ListContexts(sub, c))
                    : Results.Unauthorized()
        );
        g.MapPost(
            "/context-notes",
            async (
                ClaimsPrincipal u,
                CreateContextNoteRequest r,
                OrganizationContextService s,
                CancellationToken c
            ) =>
                Subject(u) is not string sub
                    ? Results.Unauthorized()
                    : ToHttp(await s.CreateNote(sub, r, c))
        );
        g.MapGet(
            "/context-notes/{id:guid}",
            async (Guid id, ClaimsPrincipal u, OrganizationContextService s, CancellationToken c) =>
                Subject(u) is not string sub
                    ? Results.Unauthorized()
                    : (await s.GetNote(sub, id, c) is { } n ? Results.Ok(n) : Results.NotFound())
        );
        if (app.Configuration["Authentication:Profile"] == "SyntheticLegacy"
            && !app.Configuration.GetValue<bool>("BrowserSessions:Enabled")
            && app.Configuration.GetValue<bool>("DevelopmentTestLogin:Enabled"))
            g.MapGet(
                "/database-session",
                async (ClaimsPrincipal u, OrganizationContextService s, CancellationToken c) =>
                    Subject(u) is string sub
                        ? Results.Ok(await s.DatabaseSession(sub, c))
                        : Results.Unauthorized()
            );
        return app;
    }

    private static string? Subject(ClaimsPrincipal u) =>
        u.FindFirstValue(ClaimTypes.NameIdentifier);

    private static IResult ToHttp(CreateContextNoteResult r) =>
        r switch
        {
            CreateContextNoteResult.Created x => Results.Created(
                $"/api/v1/organization/context-notes/{x.Note.Id}",
                x.Note
            ),
            CreateContextNoteResult.InvalidMessage => Results.BadRequest(
                new ProblemDetailsContract(
                    "Messaggio non valido",
                    "La nota deve contenere da 1 a 200 caratteri dopo la normalizzazione."
                )
            ),
            CreateContextNoteResult.CapabilityDisabled => Results.Json(
                new ProblemDetailsContract(
                    "Capability disabled",
                    "The organization-context capability is disabled for the selected legal entity."
                ),
                statusCode: 403
            ),
            _ => Results.Json(
                new ProblemDetailsContract(
                    "Forbidden",
                    "The selected organizational references are not authorized for this identity."
                ),
                statusCode: 403
            ),
        };

    private static async Task<IResult> DevelopmentLogin(
        DevelopmentLoginRequest request,
        IConfiguration config,
        IHttpClientFactory clients,
        CancellationToken cancellationToken
    )
    {
        if (
            string.IsNullOrWhiteSpace(request.Username)
            || string.IsNullOrWhiteSpace(request.Password)
        )
            return Results.BadRequest();
        var endpoint =
            config["DevelopmentTestLogin:TokenEndpoint"]
            ?? throw new InvalidOperationException("Development test token endpoint is required.");
        using var content = new FormUrlEncodedContent(
            new Dictionary<string, string>
            {
                { "grant_type", "password" },
                { "client_id", "enginia360-test-runner" },
                { "username", request.Username },
                { "password", request.Password },
            }
        );
        using var response = await clients
            .CreateClient()
            .PostAsync(endpoint, content, cancellationToken);
        if (!response.IsSuccessStatusCode)
            return Results.Unauthorized();
        var token = await response.Content.ReadFromJsonAsync<TokenResponse>(cancellationToken);
        return token?.AccessToken is { Length: > 0 } value
            ? Results.Ok(new DevelopmentLoginResponse(value))
            : Results.Unauthorized();
    }
}

public sealed class OrganizationContextService(OrganizationAccessDbContext db)
{
    private async Task SetIdentity(string subject, CancellationToken c)
    {
        await db.Database.ExecuteSqlInterpolatedAsync(
            $"SELECT set_config('app.identity_subject', {subject}, true)",
            c
        );
        var tenant = await db
            .Memberships.Where(x => x.IdentitySubject == subject)
            .Select(x => (Guid?)x.TenantId)
            .SingleOrDefaultAsync(c);
        if (tenant is Guid tenantId)
            await db.Database.ExecuteSqlInterpolatedAsync(
                $"SELECT set_config('app.tenant_id', {tenantId.ToString()}, true)",
                c
            );
    }

    public async Task<IReadOnlyList<OrganizationContextContract>> ListContexts(
        string subject,
        CancellationToken c
    )
    {
        await using var tx = await db.Database.BeginTransactionAsync(c);
        await SetIdentity(subject, c);
        var result = await (
            from m in db.Memberships
            join t in db.Tenants on m.TenantId equals t.Id
            join s in db.MembershipScopes on m.Id equals s.MembershipId
            join le in db.LegalEntities on s.LegalEntityId equals le.Id
            join site in db.Sites on s.SiteId equals site.Id
            join w in db.Warehouses on s.WarehouseId equals w.Id
            join a in db.CapabilityActivations on le.Id equals a.LegalEntityId
            where
                m.IdentitySubject == subject
                && s.Permission == OrganizationAccessModule.ReadPermission
                && a.Capability == OrganizationAccessModule.ContextCapability
            orderby t.Name, le.Name, site.Name, w.Name
            select new OrganizationContextContract(
                t.Id,
                t.Name,
                le.Id,
                le.Name,
                site.Id,
                site.Name,
                w.Id,
                w.Name,
                a.Enabled
            )
        )
            .AsNoTracking()
            .ToListAsync(c);
        await tx.CommitAsync(c);
        return result;
    }

    public async Task<CreateContextNoteResult> CreateNote(
        string subject,
        CreateContextNoteRequest r,
        CancellationToken c
    )
    {
        var message = r.Message?.Trim();
        if (string.IsNullOrWhiteSpace(message) || message.Length > 200)
            return new CreateContextNoteResult.InvalidMessage();
        await using var tx = await db.Database.BeginTransactionAsync(c);
        await SetIdentity(subject, c);
        var auth = await (
            from m in db.Memberships
            join s in db.MembershipScopes on m.Id equals s.MembershipId
            join a in db.CapabilityActivations on s.LegalEntityId equals a.LegalEntityId
            where
                m.IdentitySubject == subject
                && m.TenantId == r.TenantId
                && s.TenantId == r.TenantId
                && s.LegalEntityId == r.LegalEntityId
                && s.SiteId == r.SiteId
                && s.WarehouseId == r.WarehouseId
                && s.Permission == OrganizationAccessModule.WritePermission
                && a.Capability == OrganizationAccessModule.ContextCapability
            select new { a.Enabled }
        ).SingleOrDefaultAsync(c);
        if (auth is null)
            return new CreateContextNoteResult.Forbidden();
        if (!auth.Enabled)
            return new CreateContextNoteResult.CapabilityDisabled();
        var n = new ContextNote
        {
            Id = Guid.NewGuid(),
            TenantId = r.TenantId,
            LegalEntityId = r.LegalEntityId,
            SiteId = r.SiteId,
            WarehouseId = r.WarehouseId,
            Message = message,
        };
        db.ContextNotes.Add(n);
        await db.SaveChangesAsync(c);
        await tx.CommitAsync(c);
        return new CreateContextNoteResult.Created(ToContract(n));
    }

    public async Task<ContextNoteContract?> GetNote(string subject, Guid id, CancellationToken c)
    {
        await using var tx = await db.Database.BeginTransactionAsync(c);
        await SetIdentity(subject, c);
        var n = await db
            .ContextNotes.AsNoTracking()
            .SingleOrDefaultAsync(
                note =>
                    note.Id == id
                    && db.Memberships.Any(membership =>
                        membership.IdentitySubject == subject
                        && membership.TenantId == note.TenantId
                        && db.MembershipScopes.Any(scope =>
                            scope.MembershipId == membership.Id
                            && scope.TenantId == note.TenantId
                            && scope.LegalEntityId == note.LegalEntityId
                            && scope.SiteId == note.SiteId
                            && scope.WarehouseId == note.WarehouseId
                            && scope.Permission == OrganizationAccessModule.ReadPermission
                        )
                    ),
                c
            );
        await tx.CommitAsync(c);
        return n is null ? null : ToContract(n);
    }

    public async Task<DatabaseSessionContract> DatabaseSession(string subject, CancellationToken c)
    {
        await using var tx = await db.Database.BeginTransactionAsync(c);
        await SetIdentity(subject, c);
        var row = await db
            .Database.SqlQuery<DatabaseSessionRow>(
                $"SELECT pg_backend_pid() AS \"BackendPid\", current_setting('app.identity_subject', true) AS \"IdentitySubject\""
            )
            .SingleAsync(c);
        await tx.CommitAsync(c);
        return new(row.BackendPid, row.IdentitySubject);
    }

    private static ContextNoteContract ToContract(ContextNote n) =>
        new(n.Id, n.TenantId, n.LegalEntityId, n.SiteId, n.WarehouseId, n.Message);
}

public sealed record OrganizationContextContract(
    Guid TenantId,
    string TenantName,
    Guid LegalEntityId,
    string LegalEntityName,
    Guid SiteId,
    string SiteName,
    Guid WarehouseId,
    string WarehouseName,
    bool CapabilityEnabled
);

public sealed record CreateContextNoteRequest(
    Guid TenantId,
    Guid LegalEntityId,
    Guid SiteId,
    Guid WarehouseId,
    string? Message
);

public sealed record ContextNoteContract(
    Guid Id,
    Guid TenantId,
    Guid LegalEntityId,
    Guid SiteId,
    Guid WarehouseId,
    string Message
);

public sealed record ProblemDetailsContract(string Title, string Detail);

public sealed record DevelopmentLoginRequest(string Username, string Password);

public sealed record DevelopmentLoginResponse(string AccessToken);

internal sealed record TokenResponse(
    [property: System.Text.Json.Serialization.JsonPropertyName("access_token")] string AccessToken
);

public sealed record DatabaseSessionContract(int BackendPid, string IdentitySubject);

public sealed record DatabaseSessionRow(int BackendPid, string IdentitySubject);

public abstract record CreateContextNoteResult
{
    private CreateContextNoteResult() { }

    public sealed record Created(ContextNoteContract Note) : CreateContextNoteResult;

    public sealed record Forbidden : CreateContextNoteResult;

    public sealed record CapabilityDisabled : CreateContextNoteResult;

    public sealed record InvalidMessage : CreateContextNoteResult;
}
