using Microsoft.AspNetCore.Builder;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
namespace Enginia360.DocumentTypes;

public static class DocumentTypesModule
{
    public static IServiceCollection AddDocumentTypes(this IServiceCollection services, string connection)
    {
        services.AddDbContext<DocumentTypesDbContext>(options => options.UseNpgsql(connection));
        return services;
    }
    public static void MapDocumentTypes(this WebApplication app) => ManagementEndpoints.Map(app);
}
internal sealed class DocumentTypesDbContext(DbContextOptions<DocumentTypesDbContext> options) : DbContext(options);
