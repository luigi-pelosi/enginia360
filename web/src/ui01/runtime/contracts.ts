export type Order = Readonly<{ id: string; legalEntityId: string; siteId: string; documentTypeId: string; configurationVersion: number; payerId: string; vehicleId: string; vehicleHolderId: string; isCustomerOrder: boolean }>;
export type Line = Readonly<{ id: string; orderId: string; catalogItemId: string; catalogVersion: number; catalogLabel: string; kind: 'Service' | 'Part'; quantity: string; unitPrice: string; discountPercent: string; netAmount: string; taxRate: string; payerId: string; workingGroupId: string; configurationVersion: number }>;
export type Summary = Readonly<{ orderId: string; payerId: string; revision: number; lines: readonly Line[]; netAmount: string; taxAmount: string; total: string; currency: string; policy: string }>;
export const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value) && !/^0{8}-0{4}-0{4}-0{4}-0{12}$/.test(value);
export function record(value: unknown): Record<string, unknown> { if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Contratto server non valido.'); return value as Record<string, unknown>; }
export function check(condition: unknown): asserts condition { if (!condition) throw new Error('Contratto server non valido o non supportato.'); }
export const positive = (n: unknown): n is number => typeof n === 'number' && Number.isSafeInteger(n) && n > 0;
export const decimal = (n: unknown): n is string => typeof n === 'string' && /^[0-9]{1,6}(?:\.[0-9]{1,6})?$/.test(n);
export function parseOrder(value: unknown, id: string): Order {
  const row = record(value); check(row.id === id && ['id','legalEntityId','siteId','documentTypeId','payerId','vehicleId','vehicleHolderId'].every(k => uuid(row[k])) && positive(row.configurationVersion) && typeof row.isCustomerOrder === 'boolean'); return row as Order;
}
export function parseSummary(value: unknown, order: Order): Summary {
  const row = record(value);
  check(row.orderId === order.id && row.payerId === order.payerId && Number.isSafeInteger(row.revision) && Array.isArray(row.lines) && row.revision === row.lines.length && row.currency === 'EUR' && row.policy === 'Case001');
  check(['netAmount','taxAmount','total'].every(k => typeof row[k] === 'string' && /^\d+\.\d{6}$/.test(row[k] as string)));
  const ids = new Set(), kinds = new Set();
  for (const value of row.lines) {
    const l = record(value); check(uuid(l.id) && uuid(l.catalogItemId) && l.orderId === order.id && l.payerId === order.payerId && l.workingGroupId === order.id && positive(l.catalogVersion) && positive(l.configurationVersion) && typeof l.catalogLabel === 'string' && ['Service','Part'].includes(l.kind as string) && !ids.has(l.id) && !kinds.has(l.kind) && ['quantity','unitPrice','discountPercent','taxRate'].every(k => decimal(l[k])) && typeof l.netAmount === 'string' && /^\d+\.\d{6}$/.test(l.netAmount)); ids.add(l.id); kinds.add(l.kind);
  }
  return row as Summary;
}
