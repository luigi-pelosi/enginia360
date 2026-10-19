using Enginia360.Vehicles.Contracts;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace Enginia360.Vehicles;

public static class VehiclesModule
{
    public static IServiceCollection AddWorkshopVehicles(this IServiceCollection services, string connection)
    {
        services.AddDbContext<VehiclesDbContext>(o => o.UseNpgsql(connection));
        services.AddScoped<IWorkshopVehicles, WorkshopVehicles>();
        return services;
    }
}
internal sealed class VehiclesDbContext(DbContextOptions<VehiclesDbContext> options) : DbContext(options)
{
    internal DbSet<Vehicle> Vehicles => Set<Vehicle>();
    protected override void OnModelCreating(ModelBuilder b) => b.Entity<Vehicle>().ToTable("vehicles", "vehicles").HasKey(x => x.Id);
}
internal sealed class Vehicle
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid RegisteredCompanyId { get; set; }
    public Guid HolderId { get; set; }
    public required string Label { get; set; }
}
internal sealed class WorkshopVehicles(VehiclesDbContext db) : IWorkshopVehicles
{
    public async Task<IReadOnlyList<VehicleChoice>> List(Guid verifiedTenantId, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {verifiedTenantId.ToString()}, true)", ct);
        var rows = await db.Vehicles.AsNoTracking().Where(x => x.TenantId == verifiedTenantId)
            .OrderBy(x => x.Id).Select(x => new VehicleChoice(x.Id, x.Label)).ToListAsync(ct);
        await tx.CommitAsync(ct);
        return rows;
    }
    public async Task<SelectedVehicle?> Find(Guid verifiedTenantId, Guid vehicleId, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {verifiedTenantId.ToString()}, true)", ct);
        var row = await db.Vehicles.AsNoTracking().Where(x => x.TenantId == verifiedTenantId && x.Id == vehicleId)
            .Select(x => new SelectedVehicle(x.Id, x.HolderId)).SingleOrDefaultAsync(ct);
        await tx.CommitAsync(ct);
        return row;
    }
}
