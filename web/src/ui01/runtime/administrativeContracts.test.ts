import { expect, test } from 'vitest';
import { id } from './editorFixtures';
import { parseSummary } from './contracts';
import { parseRequest } from './administrativeContracts';
import { request, snapshot } from './administrativeFixtures';
const order = { id, legalEntityId: id, siteId: id, documentTypeId: id, configurationVersion: 7, payerId: id, vehicleId: id, vehicleHolderId: id, isCustomerOrder: true };
test('legacy single-group parser cannot represent the pinned snapshot, the administrative parser keeps all rows, groups and the persisted revision', () => {
  expect(() => parseSummary(snapshot, order)).toThrow();
  const parsed = parseRequest(request(), id) as unknown as { summary: { revision: number; lines: { kind: string; workingGroupId: string }[] } };
  expect(parsed.summary.revision).toBe(9);
  expect(parsed.summary.lines.map(l => l.kind)).toEqual(['Service', 'Service', 'Part', 'Part']);
  expect(new Set(parsed.summary.lines.map(l => l.workingGroupId)).size).toBe(2);
});
const withSummary = (over: Record<string, unknown>) => request({ summary: { ...snapshot, ...over } });
test.each([
  ['net not equal to the sum of the rows', withSummary({ netAmount: '36.750001' })],
  ['total not equal to net plus tax', withSummary({ total: '44.835001' })],
  ['row of another order', withSummary({ lines: [{ ...snapshot.lines[0], orderId: '12121212-1212-4212-8212-121212121212' }, ...snapshot.lines.slice(1)] })],
  ['duplicate row id', withSummary({ lines: [snapshot.lines[0], snapshot.lines[0], snapshot.lines[2], snapshot.lines[3]] })],
  ['negative persisted revision', withSummary({ revision: -1 })],
])('regression: tampered snapshot is not rendered (%s)', (_name, value) => expect(() => parseRequest(value, id)).toThrow());
test.each([
  ['Confirmed without a stable reference', request({ status: 'Confirmed' })],
  ['Confirmed with malformed reference', request({ status: 'Confirmed', externalReference: '-bad ref' })],
  ['Confirmed that also carries a rejection', request({ status: 'Confirmed', externalReference: 'AMM-SIM-000001', rejectionCode: 'x' })],
  ['Pending that already carries a reference', request({ externalReference: 'AMM-SIM-000001' })],
  ['Rejected without a code', request({ status: 'Rejected' })],
  ['Rejected with malformed code', request({ status: 'Rejected', rejectionCode: 'Bad Code' })],
  ['unknown business status', request({ status: 'Received' })],
  ['unknown delivery state', request({ delivery: { ...request().delivery, state: 'Delivered' } })],
  ['negative attempts', request({ delivery: { ...request().delivery, attempts: -1 } })],
])('request with inconsistent business outcome is not rendered (%s)', (_name, value) => expect(() => parseRequest(value, id)).toThrow());
test('consistent Confirmed and Rejected outcomes parse without altering the stable reference or code', () => {
  expect(parseRequest(request({ status: 'Confirmed', externalReference: 'AMM-SIM-000001', outcomeAt: '2026-10-24T08:02:00+00:00', delivery: { ...request().delivery, state: 'Completed' } }), id).externalReference).toBe('AMM-SIM-000001');
  expect(parseRequest(request({ status: 'Rejected', rejectionCode: 'synthetic_refusal', outcomeAt: '2026-10-24T08:02:00+00:00' }), id).rejectionCode).toBe('synthetic_refusal');
});
import { parseActions, parseGate, parseClosureState, parseTechnical, parseAdministrativeClosure } from './administrativeContracts';
import { actions, gate, state, technical, administrativeClosure, requestId } from './administrativeFixtures';
test('configured Giobby sales-order protocol is accepted as its actual runtime, not a simulator', () => {
  expect(parseActions(actions({ administrativeRuntime: { kind: 'GiobbyV1', contractVersion: 1 } }), id).administrativeRuntime.kind).toBe('GiobbyV1');
});
test('actions keep the persisted revision, exact flags, ordered reasons and the declared runtime', () => {
  const parsed = parseActions(actions({ technicalClosure: technical, canCompleteTechnical: false, actionReasons: [{ action: 'completeTechnical', code: 'already_closed' }, { action: 'readAdministrativeState', code: 'not_authorized' }] }), id) as any;
  expect(parsed.commercialRevision).toBe(9);
  expect(parsed.technicalClosure.revision).toBe(9);
  expect(parsed.canCompleteTechnical).toBe(false);
  expect(parsed.actionReasons).toEqual([{ action: 'completeTechnical', code: 'already_closed' }, { action: 'readAdministrativeState', code: 'not_authorized' }]);
  expect(parsed.administrativeRuntime).toEqual({ kind: 'SimulatorV1', contractVersion: 1 });
});
test.each([
  ['foreign order', actions({ orderId: requestId })], ['non integer revision', actions({ commercialRevision: 1.5 })], ['flag not boolean', actions({ canCompleteTechnical: 'yes' })],
  ['unknown reason code', actions({ actionReasons: [{ action: 'completeTechnical', code: 'because' }] })], ['unknown action', actions({ actionReasons: [{ action: 'closeEverything', code: 'not_authorized' }] })],
  ['provider named Giobby', actions({ administrativeRuntime: { kind: 'Giobby', contractVersion: 1 } })], ['simulator with version 0', actions({ administrativeRuntime: { kind: 'SimulatorV1', contractVersion: 0 } })],
  ['unavailable with a version', actions({ administrativeRuntime: { kind: 'Unavailable', contractVersion: 1 } })],
  ['administrative flag without read', actions({ canReadAdministrativeState: false, canRequestAdministrative: true })],
  ['technical closure of another order', actions({ technicalClosure: { ...technical, orderId: requestId } })],
  ['unknown extra capability', actions({ canForceConfirm: true })],
  ['technical closure offered on a closed order', actions({ technicalClosure: technical, canCompleteTechnical: true })],
])('actions contract is closed and honest (%s)', (_name, value) => expect(() => parseActions(value, id)).toThrow());
test('gate is a carcass requirement and a read failure is never Clear', () => {
  expect((parseGate(gate('Blocked'), id) as any).status).toBe('Blocked');
  expect((parseGate(gate('Clear'), id) as any).requirements).toEqual([]);
  expect(() => parseGate({ ...gate('Clear'), status: 'Ready' }, id)).toThrow();
  expect(() => parseGate({ ...gate('Blocked'), requirements: [] }, id)).toThrow();
  expect(() => parseGate({ ...gate('Clear'), orderId: requestId }, id)).toThrow();
});
test('technical and administrative closures are immutable receipts of this order', () => {
  expect((parseTechnical(technical, id) as any).revision).toBe(9);
  expect(() => parseTechnical({ ...technical, revision: -1 }, id)).toThrow();
  expect((parseAdministrativeClosure(administrativeClosure, id) as any).externalReference).toBe('AMM-SIM-000001');
  expect(() => parseAdministrativeClosure({ ...administrativeClosure, externalReference: ' ' }, id)).toThrow();
});
test('closure state binds the request snapshot to the frozen technical revision and the status to its facts', () => {
  const confirmed = request({ status: 'Confirmed', externalReference: 'AMM-SIM-000001', outcomeAt: '2026-10-24T08:02:00+00:00', delivery: { ...request().delivery, state: 'Completed' } });
  expect((parseClosureState(state('AwaitingAdministrativeConfirmation', { request: request() }), id) as any).request.summary.revision).toBe(9);
  expect((parseClosureState(state('AdministrativelyConfirmed', { request: confirmed }), id) as any).status).toBe('AdministrativelyConfirmed');
  expect((parseClosureState(state('AdministrativelyClosed', { request: confirmed, administrativeClosure }), id) as any).administrativeClosure.requestId).toBe(requestId);
  for (const bad of [
    state('Open', { technicalClosure: technical }), state('TechnicallyClosed', { technicalClosure: null }), state('AwaitingAdministrativeConfirmation', { request: null }),
    state('AwaitingAdministrativeConfirmation', { request: request({ summary: { ...snapshot, revision: 8 } }) }), state('AdministrativelyConfirmed', { request: request() }),
    state('AdministrativeRejected', { request: confirmed }), state('AdministrativelyClosed', { request: confirmed }), state('Mystery'),
    state('AdministrativelyClosed', { request: confirmed, administrativeClosure: { ...administrativeClosure, externalReference: 'AMM-SIM-999999' } }),
    state('AdministrativelyClosed', { request: confirmed, administrativeClosure: { ...administrativeClosure, requestId: id } }),
  ]) expect(() => parseClosureState(bad, id)).toThrow();
});
test('a Clear gate may still list its covered requirement, with nothing outstanding; Blocked needs something outstanding', () => {
  const covered = { orderId: id, status: 'Clear', requirements: [{ lineId: id, catalogItemId: id, requiredInstalled: '2', returned: '2', outstanding: '0' }] };
  expect((parseGate(covered, id) as any).requirements).toHaveLength(1);
  expect(() => parseGate({ ...covered, status: 'Blocked' }, id)).toThrow();
  expect(() => parseGate({ ...covered, requirements: [{ ...covered.requirements[0], outstanding: '1' }] }, id)).toThrow();
});
