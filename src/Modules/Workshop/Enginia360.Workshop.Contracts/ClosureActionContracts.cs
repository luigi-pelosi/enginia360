namespace Enginia360.Workshop.Contracts;

// Advisory read model (R03.c). Flags guide the UI only; every command re-authorizes and re-evaluates under its own lock.
// Kind is declared from the composition's same frozen configuration: SimulatorV1, GiobbyV1 or Unavailable; never a readiness claim.
public sealed record AdministrativeRuntime(string Kind, int ContractVersion)
{
    public static AdministrativeRuntime Unavailable { get; } = new("Unavailable", 0);
}
public sealed record ActionReason(string Action, string Code);
public sealed record OrderClosureActions(Guid OrderId, int CommercialRevision, TechnicalClosureContract? TechnicalClosure,
    bool CanReadAdministrativeState, bool CanCompleteTechnical, bool CanRequestAdministrative, bool MayRequestReconciliation,
    bool CanCompleteAdministrative, IReadOnlyList<ActionReason> ActionReasons, AdministrativeRuntime AdministrativeRuntime);
