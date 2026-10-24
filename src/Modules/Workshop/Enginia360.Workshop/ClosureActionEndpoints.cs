using System.Security.Claims;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;

namespace Enginia360.Workshop;

// R03.c advisory read: which existing closure commands this exact identity may attempt now, and why not.
// Introduces no permission and no closure condition; each command remains the authority under its own lock.
internal static class ClosureActionEndpoints
{
    internal static void Map(RouteGroupBuilder routes, bool externalAdministrationEnabled, AdministrativeRuntime runtime) =>
        routes.MapGet("/orders/{id:guid}/closure-actions", (Guid id, ClaimsPrincipal user, IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct) =>
            Read(id, user, access, db, externalAdministrationEnabled, runtime, ct));

    private static async Task<IResult> Read(Guid id, ClaimsPrincipal user, IWorkshopAccess access, WorkshopDbContext db,
        bool externalEnabled, AdministrativeRuntime runtime, CancellationToken ct)
    {
        var subject = user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
        var found = await AdministrativeEndpoints.Find(id, subject, access, db, ct);
        if (found is null) return Results.NotFound();
        var (member, order) = found.Value;
        if (await access.Authorize(subject, order.LegalEntityId, order.SiteId, "workshop.orders.read", false, ct) is null) return Results.NotFound();
        var snapshot = await AdministrativeEndpoints.ReadSnapshot(db, member.TenantId, id, ct, actionFacts: true);
        var reasons = new List<ActionReason>();
        async Task<bool> Granted(string permission, bool capability) =>
            await access.Authorize(subject, order.LegalEntityId, order.SiteId, permission, capability, ct) is not null;
        var canRead = externalEnabled && await Granted("workshop.administrative-requests.read", false);
        if (!canRead) reasons.Add(new("readAdministrativeState", externalEnabled ? "not_authorized" : "route_unavailable"));
        var canTechnical = false;
        if (snapshot.Technical is not null) reasons.Add(new("completeTechnical", "already_closed"));
        else if (!await Granted("workshop.orders.complete-technical", true)) reasons.Add(new("completeTechnical", "not_authorized"));
        else canTechnical = true;
        var canRequest = false;
        if (!canRead)
        {
            foreach (var action in new[] { "requestAdministrative", "reconcile", "completeAdministrative" })
                reasons.Add(new(action, "administrative_read_required"));
        }
        else
        {
            // Same order as the POST: grant and capability first, then the facts it re-reads under its own lock.
            if (!await Granted("workshop.administrative-requests.create", false)) reasons.Add(new("requestAdministrative", "not_authorized"));
            else if (!await Granted("workshop.administrative-requests.create", true) || !await access.CapabilityEnabled(member.TenantId, order.LegalEntityId, "external-administration", ct))
                reasons.Add(new("requestAdministrative", "capability_disabled"));
            else if (snapshot.Technical is null) reasons.Add(new("requestAdministrative", "technical_closure_required"));
            else if (snapshot.Request is not null) reasons.Add(new("requestAdministrative", "already_requested"));
            else if (snapshot.InternalClaim) reasons.Add(new("requestAdministrative", "internal_invoice_already_allocated"));
            else if (!snapshot.ExternalDestination) reasons.Add(new("requestAdministrative", "administrative_destination_missing"));
            else canRequest = true;
            reasons.Add(new("completeAdministrative", "external_confirmation_required"));
        }
        return Results.Ok(new OrderClosureActions(id, snapshot.CommercialRevision, snapshot.Technical?.Contract(), canRead, canTechnical,
            canRequest, false, false, reasons, runtime));
    }
}
