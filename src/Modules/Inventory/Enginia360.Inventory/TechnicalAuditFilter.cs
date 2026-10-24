using System.Security.Claims;
using Enginia360.Inventory.Contracts;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.Logging;

namespace Enginia360.Inventory;

// Bounded operational diagnostics, not a durable compliance journal.
internal sealed class TechnicalAuditFilter(ILogger<TechnicalAuditFilter> logger) : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var http = context.HttpContext;
        var action = http.Request.Method + " " + (http.GetEndpoint() as RouteEndpoint)?.RoutePattern.RawText;
        Guid.TryParse(http.Request.RouteValues["lineId"]?.ToString(), out var resource);
        Guid.TryParse(http.User.FindFirstValue(ClaimTypes.NameIdentifier), out var identity);
        var status = 500;
        try
        {
            var result = await next(context);
            status = (result as IStatusCodeHttpResult)?.StatusCode ?? 200;
            if (result is IValueHttpResult { Value: ReservationContract reservation }) resource = reservation.Id;
            if (result is IValueHttpResult { Value: PickContract pick }) resource = pick.Id;
            if (result is IValueHttpResult { Value: NewPartReturnContract newReturn }) resource = newReturn.Id;
            if (result is IValueHttpResult { Value: CarcassReturnContract carcass }) resource = carcass.Id;
            return result;
        }
        finally
        {
            logger.LogInformation(new EventId(606), "Inventory audit {Action} {Outcome} {ResourceId} {IdentityId}", action, status, resource, identity);
        }
    }
}
