using System.Text.Json.Serialization;
namespace Enginia360.Documents;

// Quantities deliberately remain invariant decimal strings across the wire.
// SQL validates precision and canonicalizes accepted values before replay.
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record DocumentLineInput(Guid Id, Guid ItemId, int CatalogRevision,
    string Quantity, Guid? WarehouseId, Guid? DestinationWarehouseId);
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record SaveDocumentCommand(Guid CommandId, string Operation, Guid LegalEntityId,
    Guid SiteId, Guid? DocumentId, int ExpectedRevision, Guid DocumentTypeId,
    int ExpectedTypeRevision, string Title, IReadOnlyList<DocumentLineInput> Lines);
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record ConfirmDocumentCommand(Guid CommandId, string Operation, Guid LegalEntityId,
    Guid SiteId, Guid DocumentId, int ExpectedRevision, int ExpectedTypeRevision, int ExpectedPolicyRevision);
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record QuantityPolicyCommand(Guid CommandId, string Operation, Guid LegalEntityId,
    int ExpectedRevision, bool AllowNegative);

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record OriginAllocationInput(Guid SourceDocumentId, Guid SourceLineId,
    string Quantity, int ExpectedPathRevision);
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record DevelopedLineInput(Guid Id, Guid ItemId, int CatalogRevision,
    string Quantity, Guid? WarehouseId, Guid? DestinationWarehouseId,
    IReadOnlyList<OriginAllocationInput> Origins);
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record DevelopDocumentCommand(Guid CommandId, string Operation, Guid LegalEntityId,
    Guid SiteId, Guid? DocumentId, int ExpectedRevision, Guid DocumentTypeId,
    int ExpectedTypeRevision, string Title, IReadOnlyList<DevelopedLineInput> Lines);
