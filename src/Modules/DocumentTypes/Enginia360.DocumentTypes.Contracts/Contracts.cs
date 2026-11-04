using System.Text.Json.Serialization;
namespace Enginia360.DocumentTypes.Contracts;

[JsonConverter(typeof(JsonStringEnumConverter<QuantityEffect>))]
public enum QuantityEffect { Load, Unload, Transfer, None }

// A persisted configuration version, not an executed document/stock fact.
public sealed record DocumentTypeVersion(Guid Id, Guid LegalEntityId, int Revision,
    string Label, QuantityEffect Effect, DateTimeOffset OccurredAt);
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record DocumentTypeCommand(Guid CommandId, string Operation, Guid LegalEntityId,
    Guid? DocumentTypeId, int ExpectedRevision, string Label, QuantityEffect Effect);
