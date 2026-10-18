using System.Security.Claims;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.Logging;
namespace Enginia360.Counterparties;

// Operational, bounded technical audit; not a durable compliance journal.
internal sealed class TechnicalAuditFilter(ILogger<TechnicalAuditFilter> logger) : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var http = context.HttpContext;
        var action = http.Request.Method + " " + (http.GetEndpoint() as RouteEndpoint)?.RoutePattern.RawText;
        Guid.TryParse(http.Request.RouteValues["id"]?.ToString(), out var resource);
        Guid.TryParse(http.User.FindFirstValue(ClaimTypes.NameIdentifier), out var identity);
        try
        {
            var result = await next(context);
            var status = (result as IStatusCodeHttpResult)?.StatusCode ?? 200;
            logger.LogInformation(new EventId(303), "Counterparty audit {Action} {Outcome} {ResourceId} {IdentityId}", action, status, resource, identity);
            return result;
        }
        catch
        {
            logger.LogInformation(new EventId(303), "Counterparty audit {Action} {Outcome} {ResourceId} {IdentityId}", action, 500, resource, identity);
            throw;
        }
    }
}
