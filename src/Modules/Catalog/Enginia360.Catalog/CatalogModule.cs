using Enginia360.Catalog.Contracts;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace Enginia360.Catalog;

public static class CatalogModule
{
    public static void MapSupplierPurchasePrices(Microsoft.AspNetCore.Builder.WebApplication app) => PurchasePriceEndpoints.Map(app);
    public static IServiceCollection AddWorkshopCatalog(this IServiceCollection services, string connection)
    {
        services.AddDbContext<CatalogDbContext>(o => o.UseNpgsql(connection));
        services.AddScoped<IWorkshopCatalog, WorkshopCatalog>();
        return services;
    }
}
internal sealed class CatalogDbContext(DbContextOptions<CatalogDbContext> options) : DbContext(options)
{
    internal DbSet<CatalogItem> Items => Set<CatalogItem>();
    protected override void OnModelCreating(ModelBuilder b) => b.Entity<CatalogItem>().ToTable("items", "catalog").HasKey(x => x.Id);
}
internal sealed class CatalogItem
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid RegisteredCompanyId { get; set; }
    public required string Kind { get; set; }
    public required string Label { get; set; }
    public int Version { get; set; }
}
internal sealed class WorkshopCatalog(CatalogDbContext db) : IWorkshopCatalog
{
    public async Task<IReadOnlyList<CatalogChoice>> List(Guid verifiedTenantId, CancellationToken ct, int? limit = null, string? search = null, Guid? after = null)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {verifiedTenantId.ToString()}, true)", ct);
        var rows = await db.Items.AsNoTracking().Where(x => x.TenantId == verifiedTenantId)
            .Where(x => search == null || x.Label.Contains(search))
            .Where(x => after == null || x.Id.CompareTo(after.Value) > 0)
            .OrderBy(x => x.Id).Take(limit ?? int.MaxValue)
            .Select(x => new CatalogChoice(x.Id, x.Kind, x.Label, x.Version)).ToListAsync(ct);
        await tx.CommitAsync(ct);
        return rows;
    }
    public async Task<CatalogChoice?> Find(Guid verifiedTenantId, Guid itemId, CancellationToken ct)
    {
        var rows = await List(verifiedTenantId, ct);
        return rows.SingleOrDefault(x => x.Id == itemId);
    }
}
