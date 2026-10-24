using System.Text.Json.Serialization;

namespace Enginia360.Workshop.Contracts;

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
[JsonNumberHandling(JsonNumberHandling.Strict)]
public sealed record RecordOwnActualTimeCommand(Guid CommandId, Guid EntryId, Guid WorkingGroupId,
    int ExpectedOwnRevision, int ExpectedGroupVersion, string WorkDate, int DurationSeconds, string Note);
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
[JsonNumberHandling(JsonNumberHandling.Strict)]
public sealed record CorrectOwnActualTimeCommand(Guid CommandId, int ExpectedOwnRevision, int ExpectedEntryVersion,
    string WorkDate, int DurationSeconds, string Note, string CorrectionNote);
public sealed record OwnActualTimeVersion(int Version, string WorkDate, int DurationSeconds, string Note, string? CorrectionNote,
    Guid InternalIdentityId, Guid MembershipId, Guid CommandId, int OwnRevision, DateTimeOffset RecordedAt);
public sealed record OwnActualTimeHistory(Guid OrderId, Guid EntryId, Guid WorkingGroupId, IReadOnlyList<OwnActualTimeVersion> Versions, int? NextAfterVersion);
public sealed record OwnActualTimeReceipt(Guid CommandId, Guid OrderId, Guid EntryId, int AppliedOwnRevision, int EntryVersion, string ResultKind);
public sealed record OwnActualTimeEntry(Guid EntryId, Guid WorkingGroupId, int Version, string WorkDate, int DurationSeconds,
    string Note, DateTimeOffset RecordedAt);
public sealed record OwnActualTimePage(Guid OrderId, int OwnRevision, bool Closed, bool CanRecord,
    IReadOnlyList<OwnActualTimeEntry> Entries, Guid? NextAfter);
