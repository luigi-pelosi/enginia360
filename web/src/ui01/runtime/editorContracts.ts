import { check, decimal, parseOrder, positive, record, uuid, type Line, type Order } from './contracts';
export type Policy = Readonly<{ state: 'ready' | 'line_policy_missing'; documentConfigurationVersion: number; currentLinePolicyVersion: number | null; calculationPolicy: string | null; multipleWorkingGroups: boolean; structurePolicyVersion: number; limits: Readonly<{ maxActiveLines: number; maxActiveGroups: number; maxActiveNotes: number; maxDescriptionLength: number }> }>;
export type Group = Readonly<{ id: string; title: string; version: number; sequence: number }>;
export type Row = Readonly<{ id: string; kind: 'Service' | 'Part' | 'Note'; workingGroupId: string; sequence: number; version: number; description: string | null; line: Line | null }>;
export type Capabilities = Readonly<{ closed: boolean; canAddLine: boolean; canEditLine: boolean; canRemoveLine: boolean; canWriteNotes: boolean; canWriteGroups: boolean; materialStructureEdit: boolean; materialStructureEditReason: string | null }>;
export type EditorSummary = Readonly<{ orderId: string; payerId: string; revision: number; lines: readonly Line[]; netAmount: string; taxAmount: string; total: string; currency: string; policy: string }>;
export type Editor = Readonly<{ order: Order; revision: number; linePolicy: Policy; groups: readonly Group[]; rows: readonly Row[]; summary: EditorSummary; capabilities: Capabilities }>;
const nonNegative = (n: unknown): n is number => typeof n === 'number' && Number.isSafeInteger(n) && n >= 0;
const money = (v: unknown) => typeof v === 'string' && /^\d+\.\d{6}$/.test(v);
export function parseEditor(value: unknown, id: string): Editor {
  const row = record(value), order = parseOrder(row.order, id);
  check(nonNegative(row.revision));
  const p = record(row.linePolicy), lim = record(p.limits);
  check((p.state === 'ready' || p.state === 'line_policy_missing') && p.orderId === id && positive(p.documentConfigurationVersion) && (p.currentLinePolicyVersion === null ? p.state === 'line_policy_missing' : positive(p.currentLinePolicyVersion)) && typeof p.multipleWorkingGroups === 'boolean' && positive(p.structurePolicyVersion) && ['maxActiveLines', 'maxActiveGroups', 'maxActiveNotes', 'maxDescriptionLength'].every(k => positive(lim[k])));
  const caps = record(row.capabilities);
  check(['closed', 'canAddLine', 'canEditLine', 'canRemoveLine', 'canWriteNotes', 'canWriteGroups', 'materialStructureEdit'].every(k => typeof caps[k] === 'boolean'));
  check(Array.isArray(row.groups) && Array.isArray(row.rows));
  const groups = row.groups.map(g => { const r = record(g); check(uuid(r.id) && typeof r.title === 'string' && r.title.length > 0 && positive(r.version) && nonNegative(r.sequence)); return r as unknown as Group; });
  const groupIds = new Set(groups.map(g => g.id)); check(groupIds.size === groups.length);
  const ids = new Set<string>();
  const rows = row.rows.map(v => {
    const r = record(v); check(uuid(r.id) && !ids.has(r.id as string) && ['Service', 'Part', 'Note'].includes(r.kind as string) && groupIds.has(r.workingGroupId as string) && nonNegative(r.sequence) && positive(r.version)); ids.add(r.id as string);
    if (r.kind === 'Note') check(r.line === null && typeof r.description === 'string' && r.description.length > 0);
    else { const l = record(r.line); check(l.id === r.id && l.kind === r.kind && l.orderId === id && l.workingGroupId === r.workingGroupId && l.payerId === order.payerId && decimal(l.quantity) && decimal(l.unitPrice) && typeof l.discountPercent === 'string' && money(l.netAmount) && (r.description === null || typeof r.description === 'string')); }
    return r as unknown as Row;
  });
  const s = record(row.summary);
  check(s.orderId === id && s.payerId === order.payerId && s.revision === row.revision && s.currency === 'EUR' && s.policy === 'Case001' && money(s.netAmount) && money(s.taxAmount) && money(s.total) && Array.isArray(s.lines));
  const commercial = rows.filter(r => r.kind !== 'Note').map(r => r.id).sort();
  check(JSON.stringify((s.lines as readonly Line[]).map(l => l.id).sort()) === JSON.stringify(commercial));
  return { order, revision: row.revision, linePolicy: p as unknown as Policy, groups, rows, summary: s as unknown as EditorSummary, capabilities: caps as unknown as Capabilities };
}
