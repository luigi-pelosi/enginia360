namespace Enginia360.Workshop.Contracts;

// R03.a public order-workspace contract. Server-owned versions and revision; no client-supplied setup numbers.
public sealed record WorkspaceLimits(int MaxActiveLines, int MaxActiveGroups, int MaxActiveNotes, int MaxDescriptionLength);

// State is "ready" or "line_policy_missing" (never an implicit version 1). Structure version is the server's workspace contract version.
public sealed record LinePolicyContract(Guid OrderId, string State, Guid DocumentTypeId, int DocumentConfigurationVersion,
    int? CurrentLinePolicyVersion, string? CalculationPolicy, bool MultipleWorkingGroups, int StructurePolicyVersion,
    WorkspaceLimits Limits, IReadOnlyList<string> SupportedCommands);

public sealed record WorkingGroupContract(Guid Id, string Title, int Version, int Sequence);
// Row is a discriminated union by Kind: Service|Part carry Line; Note carries only Description.
public sealed record EditorRow(Guid Id, string Kind, Guid WorkingGroupId, int Sequence, int Version, string? Description, LineContract? Line);
// Informational flags only: the server re-authorizes every command. Material structure edits are explicitly unsupported in R03.a.
public sealed record EditorCapabilities(bool Closed, bool CanAddLine, bool CanEditLine, bool CanRemoveLine, bool CanWriteNotes,
    bool CanWriteGroups, bool MaterialStructureEdit, string? MaterialStructureEditReason);
public sealed record WorkshopEditorContract(OrderContract Order, int Revision, LinePolicyContract LinePolicy,
    IReadOnlyList<WorkingGroupContract> Groups, IReadOnlyList<EditorRow> Rows, CommercialSummary Summary, EditorCapabilities Capabilities);

[System.Text.Json.Serialization.JsonUnmappedMemberHandling(System.Text.Json.Serialization.JsonUnmappedMemberHandling.Disallow)]
public sealed record EditorCommand(string Type, Guid CommandId, int ExpectedRevision, int? ExpectedLinePolicyVersion,
    int ExpectedStructurePolicyVersion, Guid? GroupId, Guid? LineId, string? Title, string? Description,
    Guid? CatalogItemId, int? CatalogVersion, string? Quantity, string? UnitPrice, string? DiscountPercent);
public sealed record WorkshopEditReceipt(Guid CommandId, Guid OrderId, int AppliedRevision, string ResultKind, Guid TargetId);
public sealed record WorkshopOrderListItem(Guid Id, Guid DocumentTypeId, int DocumentConfigurationVersion, Guid PayerId, Guid VehicleId,
    int Revision, bool Closed);
