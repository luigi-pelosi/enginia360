using System.Security.Claims;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.Logging;

namespace Enginia360.Workshop;

// Bounded operational audit, matching the existing private proof. No business payload.
internal sealed class TechnicalAuditFilter(ILogger<TechnicalAuditFilter> logger) : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var http = context.HttpContext;
        var action = http.Request.Method + " " + (http.GetEndpoint() as RouteEndpoint)?.RoutePattern.RawText;
        Guid.TryParse(http.Request.RouteValues["id"]?.ToString(), out var resource);
        Guid.TryParse(http.User.FindFirstValue(ClaimTypes.NameIdentifier), out var identity);
        var status = 500;
        try
        {
            var result = await next(context);
            status = (result as IStatusCodeHttpResult)?.StatusCode ?? 200;
            if (result is IValueHttpResult { Value: OrderContract order }) resource = order.Id;
            if (result is IValueHttpResult { Value: LineContract line }) resource = line.Id;
            if (result is IValueHttpResult { Value: InstallationResult installation }) resource = installation.Installation.Id;
            return result;
        }
        finally
        {
            logger.LogInformation(new EventId(404), "Workshop audit {Action} {Outcome} {ResourceId} {IdentityId}", action, status, resource, identity);
        }
    }
}
