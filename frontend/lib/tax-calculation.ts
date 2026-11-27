import {ApiError, refreshCsrf} from './api.ts';
import {taxDeterminationCommand, type TaxSimulationSnapshot} from './tax-rules.ts';

export type TaxAdjustment = {
  adjustment_id: string;
  type: 'DISCOUNT' | 'SURCHARGE';
  calculation_mode: 'PERCENTAGE' | 'FIXED_AMOUNT';
  value: string;
  sequence: number;
  applicable_line_ids?: string[];
};
export type TaxCalculationLineDraft = {
  line_id: string;
  quantity: string;
  unit_price: string;
  price_mode: 'TAX_EXCLUSIVE' | 'TAX_INCLUSIVE';
  adjustments: TaxAdjustment[];
  deductible_percentage: string | null;
  scenario: TaxSimulationSnapshot;
};
export type TaxCalculationDraft = {
  company_id: string;
  currency: 'EUR';
  operation_type: 'SALE' | 'PURCHASE';
  direction: 'NORMAL' | 'REVERSAL';
  lines: TaxCalculationLineDraft[];
  document_adjustments: TaxAdjustment[];
};
export type TaxCalculationResult = {
  currency: string;
  calculationPolicyCode: string;
  calculationPolicyVersion: number;
  lines: Record<string, unknown>[];
  summaries: Record<string, unknown>[];
  totals: Record<string, unknown>;
  calculationTrace: unknown;
};
export type TaxCalculationOutput = {isSimulation: boolean; result: TaxCalculationResult};
export type TaxCalculationPolicyResponse = {
  policy: {
    code: string; version: number; currency: string; currencyScale: number;
    internalScale: number; roundingMode: string; roundingScope: string;
    residualAllocationMode: string;
  };
  currency: {id: string; code: string; minor_units: number; version: number};
  permissions: string[];
};
export type TaxCalculationSnapshot = {input: TaxCalculationDraft; output: TaxCalculationOutput};
export type TaxCalculationState = {
  draft: TaxCalculationDraft;
  submitted: TaxCalculationSnapshot | null;
  comparison: TaxCalculationSnapshot | null;
};
export function emptyTaxCalculation(): TaxCalculationState {
  return {
    draft: {company_id: '', currency: 'EUR', operation_type: 'SALE', direction: 'NORMAL', lines: [], document_adjustments: []},
    submitted: null,
    comparison: null,
  };
}

/** Capture only the explicitly successful F4 snapshot, never the live editor. */
export function appendTaxCalculationScenario(
  draft: TaxCalculationDraft,
  scenario: TaxSimulationSnapshot,
  id: () => string = () => crypto.randomUUID(),
): TaxCalculationDraft {
  if (scenario.output.outcome !== 'SUCCESS' || !scenario.output.result) throw new ApiError('scenarioRequired', 422);
  if (draft.lines.length >= 100) throw new ApiError('lineLimit', 422);
  if (draft.lines.length && (draft.company_id !== scenario.input.company_id || draft.operation_type !== scenario.input.operation_type)) {
    throw new ApiError('contextMismatch', 422);
  }
  return {
    ...structuredClone(draft),
    company_id: scenario.input.company_id,
    operation_type: scenario.input.operation_type,
    lines: [...structuredClone(draft.lines), {
      line_id: id(), quantity: '1', unit_price: '0.00', price_mode: 'TAX_EXCLUSIVE',
      adjustments: [], deductible_percentage: null, scenario: structuredClone(scenario),
    }],
  };
}

/** Only a simple decimal comma is normalized, never grouping or scientific notation. */
export function taxCalculationDecimal(value: string): string {
  return /^\d+,\d+$/.test(value) ? value.replace(',', '.') : value;
}
function adjustmentCommand(value: TaxAdjustment, document: boolean) {
  return {
    adjustment_id: value.adjustment_id, type: value.type, calculation_mode: value.calculation_mode,
    value: taxCalculationDecimal(value.value), sequence: value.sequence,
    ...(document && value.applicable_line_ids !== undefined ? {applicable_line_ids: [...value.applicable_line_ids]} : {}),
  };
}
export function taxCalculationCommand(draft: TaxCalculationDraft, simulation = true) {
  if (!simulation && draft.lines.some(line => line.scenario.draftVersionIds.length)) throw new ApiError('draftsSimulationOnly', 422);
  return {
    company_id: draft.company_id, currency: draft.currency, operation_type: draft.operation_type, direction: draft.direction,
    lines: draft.lines.map(line => ({
      line_id: line.line_id, quantity: taxCalculationDecimal(line.quantity), unit_price: taxCalculationDecimal(line.unit_price),
      price_mode: line.price_mode, adjustments: line.adjustments.map(value => adjustmentCommand(value, false)),
      deductible_percentage: line.deductible_percentage === null || line.deductible_percentage === '' ? null : taxCalculationDecimal(line.deductible_percentage),
      fiscal_context: taxDeterminationCommand(line.scenario.input, simulation ? line.scenario.draftVersionIds : undefined),
    })),
    document_adjustments: draft.document_adjustments.map(value => adjustmentCommand(value, true)),
  };
}

/** Arrays retain their order: sequence is executable commercial input, not a set. */
export function taxCalculationCanonical(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(taxCalculationCanonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
    .map(([key, entry]) => JSON.stringify(key) + ':' + taxCalculationCanonical(entry)).join(',') + '}';
  return JSON.stringify(value);
}
export function taxCalculationStale(snapshot: TaxCalculationSnapshot | null, draft: TaxCalculationDraft) {
  return !!snapshot && taxCalculationCanonical(taxCalculationCommand(snapshot.input)) !== taxCalculationCanonical(taxCalculationCommand(draft));
}

export class TaxCalculationError extends ApiError {
  trace?: unknown;
  outcome?: string;
  isSimulation?: boolean;
  constructor(code: string, status: number, field?: string, details?: {trace?: unknown; outcome?: string; isSimulation?: boolean}) {
    super(code, status, field);
    this.trace = details?.trace;
    this.outcome = details?.outcome;
    this.isSimulation = details?.isSimulation;
  }
}
/** Dedicated adapter preserves fiscal 422 evidence; the generic API adapter is untouched. */
export async function postTaxCalculation(path: string, draft: TaxCalculationDraft): Promise<TaxCalculationOutput> {
  const token = await refreshCsrf();
  let response: Response;
  try {
    response = await fetch('/api' + path, {
      method: 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: {'Content-Type': 'application/json', 'X-CSRF-TOKEN': token!},
      body: JSON.stringify(taxCalculationCommand(draft)),
    });
  } catch { throw new TaxCalculationError('network_error', 0); }
  const payload = await response.json();
  if (!response.ok) throw new TaxCalculationError(payload.code || 'server_error', response.status, payload.field, payload);
  return payload;
}

function record(value: unknown): value is Record<string, any> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}
function validAdjustments(value: unknown): value is TaxAdjustment[] {
  return Array.isArray(value) && value.length <= 20 && value.every(a => record(a) && typeof a.adjustment_id === 'string'
    && ['DISCOUNT', 'SURCHARGE'].includes(a.type) && ['PERCENTAGE', 'FIXED_AMOUNT'].includes(a.calculation_mode)
    && typeof a.value === 'string' && Number.isSafeInteger(a.sequence) && a.sequence > 0
    && (a.applicable_line_ids === undefined || Array.isArray(a.applicable_line_ids) && a.applicable_line_ids.every((id: unknown) => typeof id === 'string')));
}
function validDraft(value: unknown): value is TaxCalculationDraft {
  return record(value) && typeof value.company_id === 'string' && value.currency === 'EUR'
    && ['SALE', 'PURCHASE'].includes(value.operation_type) && ['NORMAL', 'REVERSAL'].includes(value.direction)
    && validAdjustments(value.document_adjustments) && Array.isArray(value.lines) && value.lines.length <= 100
    && value.lines.every(line => record(line) && typeof line.line_id === 'string' && typeof line.quantity === 'string'
      && typeof line.unit_price === 'string' && ['TAX_EXCLUSIVE', 'TAX_INCLUSIVE'].includes(line.price_mode)
      && (line.deductible_percentage === null || typeof line.deductible_percentage === 'string')
      && validAdjustments(line.adjustments) && record(line.scenario) && record(line.scenario.input)
      && record(line.scenario.input.transaction_facts) && line.scenario.input.company_id === value.company_id
      && line.scenario.input.operation_type === value.operation_type && Array.isArray(line.scenario.draftVersionIds)
      && line.scenario.draftVersionIds.every((id: unknown) => typeof id === 'string')
      && line.scenario.output?.outcome === 'SUCCESS' && record(line.scenario.output.result));
}
function validSnapshot(value: unknown): value is TaxCalculationSnapshot {
  return record(value) && validDraft(value.input) && record(value.output) && typeof value.output.isSimulation === 'boolean'
    && record(value.output.result) && Array.isArray(value.output.result.lines) && Array.isArray(value.output.result.summaries)
    && record(value.output.result.totals);
}
/** A legacy F4 envelope has no calculation slice. Invalid F5 data never discards F4. */
export function recoverTaxCalculation(value: unknown): TaxCalculationState {
  if (!record(value) || !validDraft(value.draft)) return emptyTaxCalculation();
  return {
    draft: structuredClone(value.draft),
    submitted: validSnapshot(value.submitted) ? structuredClone(value.submitted) : null,
    comparison: validSnapshot(value.comparison) ? structuredClone(value.comparison) : null,
  };
}
