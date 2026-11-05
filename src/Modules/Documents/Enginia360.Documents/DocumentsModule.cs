using Microsoft.AspNetCore.Builder;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
namespace Enginia360.Documents;

public static class DocumentsModule
{
    public static IServiceCollection AddDocuments(this IServiceCollection services, string connection)
    {
        services.AddDbContext<DocumentsDbContext>(options => options.UseNpgsql(connection));
        return services;
    }
    public static void MapDocuments(this WebApplication app) => DocumentEndpoints.Map(app);
}
// Owns the whole confirmation, ledger, balances and audit transaction; never an
// Inventory/Workshop access adapter or a second pooled connection.
internal sealed class DocumentsDbContext(DbContextOptions<DocumentsDbContext> options) : DbContext(options);
