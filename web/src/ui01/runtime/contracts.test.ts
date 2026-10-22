import { expect, test } from 'vitest';
import { parseOrder, parseSummary } from './contracts';
const id = '11111111-1111-4111-8111-111111111111';
const order = { id, legalEntityId: id, siteId: id, documentTypeId: id, configurationVersion: 7, payerId: id, vehicleId: id, vehicleHolderId: id, isCustomerOrder: false };
const summary = { orderId: id, payerId: id, revision: 0, lines: [], netAmount: '0.000000', taxAmount: '0.000000', total: '0.000000', currency: 'EUR', policy: 'Case001' };
test.each([{ ...summary, orderId: 'foreign' }, { ...summary, payerId: 'foreign' }, { ...summary, revision: 99 }, { ...summary, total: 0 }, { ...summary, policy: 'Unknown' }, { ...summary, total: '0.00' }])('invalid/mismatched summary is not rendered: %j', value => expect(() => parseSummary(value, order)).toThrow());
test('document version7 and exact q6 amounts survive parsing without rounding', () => { expect(parseOrder(order,id)).toBe(order); expect(parseSummary(summary,order)).toBe(summary); });
