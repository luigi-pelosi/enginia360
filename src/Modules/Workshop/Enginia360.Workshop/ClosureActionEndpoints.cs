using System.Security.Claims;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.DependencyInjection;

namespace Enginia360.Workshop;

// R03.c advisory read: which existing closure commands this exact identity may attempt now, and why not.
// Introduces no permission and no closure condition; each command remains the authority under its own lock.
internal static class ClosureActionEndpoints
{
    internal static void Map(RouteGroupBuilder routes, bool externalAdministrationEnabled, AdministrativeRuntime runtime) =>
        routes.MapGet("/orders/{id:guid}/closure-actions", (Guid id, HttpContext http, ClaimsPrincipal user, IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct) =>
            Read(id, http, user, access, db, externalAdministrationEnabled, runtime, ct));

    private static async Task<IResult> Read(Guid id, HttpContext http, ClaimsPrincipal user, IWorkshopAccess access, WorkshopDbContext db,
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
        var (canRequest, canReconcile, canComplete) = (false, false, false);
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
            // Delivery state is a second public observation, taken after the Workshop connection was released.
            var delivery = snapshot.Request is null ? null
                : (await http.RequestServices.GetRequiredService<IAdministrativeDeliveries>().Read(member.TenantId, [snapshot.Request.Id], ct)).GetValueOrDefault(snapshot.Request.Id);
            if (!await Granted("workshop.administrative-requests.reconcile", false)) reasons.Add(new("reconcile", "not_authorized"));
            else if (!await Granted("workshop.administrative-requests.reconcile", true) || !await access.CapabilityEnabled(member.TenantId, order.LegalEntityId, "external-administration", ct))
                reasons.Add(new("reconcile", "capability_disabled"));
            else if (snapshot.Request is null || snapshot.Outcome is not null || delivery is not { State: "NeedsReconciliation" }) reasons.Add(new("reconcile", "reconciliation_not_available"));
            else canReconcile = true;
            if (!await Granted("workshop.orders.complete-administrative", false)) reasons.Add(new("completeAdministrative", "not_authorized"));
            else if (!await Granted("workshop.orders.complete-administrative", true)) reasons.Add(new("completeAdministrative", "capability_disabled"));
            else if (snapshot.Administrative is not null) reasons.Add(new("completeAdministrative", "already_closed"));
            else if (snapshot.Outcome is not { Status: "Confirmed", ExternalReference: not null }) reasons.Add(new("completeAdministrative", "external_confirmation_required"));
            else canComplete = true;
        }
        return Results.Ok(new OrderClosureActions(id, snapshot.CommercialRevision, snapshot.Technical?.Contract(), canRead, canTechnical,
            canRequest, canReconcile, canComplete, reasons, runtime));
    }
}
