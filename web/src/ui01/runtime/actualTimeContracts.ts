import { check, record, uuid, positive } from './contracts';
export type OwnEntry = Readonly<{
    entryId: string;
    workingGroupId: string;
    version: number;
    workDate: string;
    durationSeconds: number;
    note: string;
    recordedAt: string;
}>;
export type OwnTime = Readonly<{
    orderId: string;
    ownRevision: number;
    closed: boolean;
    canRecord: boolean;
    entries: readonly OwnEntry[];
    nextAfter: string | null;
}>;
export function parseOwnTime(value: unknown, id: string): OwnTime {
    const p = record(value);
    check(p.orderId === id && Number.isInteger(p.ownRevision) && Number(p.ownRevision) >= 0 && typeof p.closed === 'boolean' && typeof p.canRecord === 'boolean' && Array.isArray(p.entries));
    for (const item of p.entries as unknown[]) {
        const e = record(item);
        check(uuid(e.entryId) && uuid(e.workingGroupId) && positive(e.version) && positive(e.durationSeconds) && Number(e.durationSeconds) <= 2147483647 && typeof e.note === 'string' && e.note.length <= 500 && typeof e.workDate === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(e.workDate) && typeof e.recordedAt === 'string');
    }
    check(p.nextAfter === null || uuid(p.nextAfter));
    return p as unknown as OwnTime;
}
export type OwnVersion = Readonly<{
    version: number;
    workDate: string;
    durationSeconds: number;
    note: string;
    correctionNote: string | null;
    internalIdentityId: string;
    membershipId: string;
    commandId: string;
    ownRevision: number;
    recordedAt: string;
}>;
export type OwnHistory = Readonly<{
    orderId: string;
    entryId: string;
    workingGroupId: string;
    versions: readonly OwnVersion[];
    nextAfterVersion: number | null;
}>;
export function parseOwnHistory(value: unknown, order: string, entry: string): OwnHistory {
    const h = record(value);
    check(h.orderId === order && h.entryId === entry && uuid(h.workingGroupId) && Array.isArray(h.versions));
    for (const item of h.versions as unknown[]) {
        const v = record(item);
        check(positive(v.version) && positive(v.durationSeconds) && typeof v.workDate === 'string' && typeof v.note === 'string' && (v.correctionNote === null || typeof v.correctionNote === 'string') && uuid(v.internalIdentityId) && uuid(v.membershipId) && uuid(v.commandId) && positive(v.ownRevision) && typeof v.recordedAt === 'string');
    }
    check(h.nextAfterVersion === null || positive(h.nextAfterVersion));
    return h as unknown as OwnHistory;
}
