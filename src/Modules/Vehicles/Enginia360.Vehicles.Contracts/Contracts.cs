namespace Enginia360.Vehicles.Contracts;

// Internal application port for an already-authorized workshop use, not vehicle CRUD.
public sealed record VehicleChoice(Guid Id, string Label);
public sealed record SelectedVehicle(Guid Id, Guid HolderId);
public interface IWorkshopVehicles
{
    Task<IReadOnlyList<VehicleChoice>> List(Guid verifiedTenantId, CancellationToken ct);
    Task<SelectedVehicle?> Find(Guid verifiedTenantId, Guid vehicleId, CancellationToken ct);
}
