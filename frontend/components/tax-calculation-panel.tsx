"use client";

import {useTranslations} from 'next-intl';
import type {ReactNode} from 'react';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {Badge} from '@/components/ui/badge';
import {
  taxCalculationStale,
  type TaxAdjustment,
  type TaxCalculationDraft,
  type TaxCalculationState,
  type TaxCalculationPolicyResponse,
  type TaxCalculationError,
  type TaxCalculationSnapshot,
} from '@/lib/tax-calculation';

export type TaxCalculationPanelProps = {
  state: TaxCalculationState;
  policy: TaxCalculationPolicyResponse | null;
  disabled: boolean;
  canRun: boolean;
  currentCompany: string;
  error: TaxCalculationError | null;
  onChange: (state: TaxCalculationState) => void;
  onCalculate: () => void;
};

/** Controlled presentation only. Requests, fresh authority and recovery belong to TaxSimulator. */
export function TaxCalculationPanel({state, policy, disabled, canRun, currentCompany, error, onChange, onCalculate}: TaxCalculationPanelProps) {
  const t = useTranslations('taxCalculation');
  const draft = state.draft;
  const companyMismatch = !!draft.lines.length && draft.company_id !== currentCompany;
  const change = (next: TaxCalculationDraft) => {if (!disabled) onChange({...state, draft: next});};
  const text = (key: string) => t.has(key) ? t(key) : key;
  const issue = (field: string) => error?.field === field || !!error?.field?.startsWith(field + '.');

  function decimal(id: string, label: string, value: string, field: string, update: (value: string) => void, nullable = false) {
    return <label className="grid min-w-0 gap-1 text-xs" htmlFor={id}>
      <span className="text-muted-foreground">{label}</span>
      <Input id={id} type="text" inputMode="decimal" className="text-right tabular-nums" maxLength={40}
        value={value} disabled={disabled} placeholder={nullable ? t('unknown') : undefined}
        aria-invalid={issue(field)} onChange={event => update(event.target.value)}/>
      {issue(field) && <span className="text-destructive">{text(error!.code)}</span>}
    </label>;
  }
  function choice(id: string, label: string, value: string, values: string[], update: (value: string) => void) {
    return <label className="grid min-w-0 gap-1 text-xs" htmlFor={id}>
      <span className="text-muted-foreground">{label}</span>
      <select id={id} className="h-9 w-full rounded-md border bg-background px-2 text-sm" value={value}
        disabled={disabled} onChange={event => update(event.target.value)}>
        {values.map(option => <option key={option} value={option}>{text(option)}</option>)}
      </select>
    </label>;
  }
  function adjustments(values: TaxAdjustment[], update: (values: TaxAdjustment[]) => void, prefix: string, field: string, document = false) {
    function set(index: number, patch: Partial<TaxAdjustment>) {
      update(values.map((entry, i) => i === index ? {...entry, ...patch} : entry));
    }
    function move(index: number, direction: number) {
      const ordered = [...values];
      [ordered[index], ordered[index + direction]] = [ordered[index + direction], ordered[index]];
      update(ordered.map((entry, i) => ({...entry, sequence: i + 1})));
    }
    return <div className="space-y-2">
      {values.map((entry, i) => <div key={entry.adjustment_id} className="rounded border p-2 space-y-2">
        <div className="grid gap-2 sm:grid-cols-[2rem_1fr_1fr_1fr_auto] items-end">
          <span className="pb-2 text-xs text-muted-foreground">{entry.sequence}.</span>
          {choice(prefix + '-type-' + entry.adjustment_id, t('type'), entry.type, ['DISCOUNT', 'SURCHARGE'], type => set(i, {type: type as TaxAdjustment['type']}))}
          {choice(prefix + '-mode-' + entry.adjustment_id, t('mode'), entry.calculation_mode, ['PERCENTAGE', 'FIXED_AMOUNT'], mode => set(i, {calculation_mode: mode as TaxAdjustment['calculation_mode']}))}
          {decimal(prefix + '-value-' + entry.adjustment_id, t('value'), entry.value, `${field}[${i}].value`, value => set(i, {value}))}
          <div className="flex gap-1">
            <Button variant="ghost" size="icon" disabled={disabled || i === 0} aria-label={t('moveUp')} onClick={() => move(i, -1)}>↑</Button>
            <Button variant="ghost" size="icon" disabled={disabled || i === values.length - 1} aria-label={t('moveDown')} onClick={() => move(i, 1)}>↓</Button>
            <Button variant="ghost" size="icon" disabled={disabled} aria-label={t('removeAdjustment')} onClick={() => update(values.filter((_, index) => index !== i).map((a, index) => ({...a, sequence: index + 1})))}>×</Button>
          </div>
        </div>
        {document && <fieldset className="flex flex-wrap gap-3 text-xs">
          <legend className="mb-1 text-muted-foreground">{t('scope')}</legend>
          <label className="flex gap-1"><input type="checkbox" checked={entry.applicable_line_ids === undefined} disabled={disabled}
            onChange={event => set(i, {applicable_line_ids: event.target.checked ? undefined : draft.lines.map(line => line.line_id)})}/>{t('allLines')}</label>
          {entry.applicable_line_ids !== undefined && draft.lines.map((line, lineIndex) => <label key={line.line_id} className="flex gap-1">
            <input type="checkbox" checked={entry.applicable_line_ids!.includes(line.line_id)} disabled={disabled}
              onChange={event => set(i, {applicable_line_ids: event.target.checked ? [...entry.applicable_line_ids!, line.line_id] : entry.applicable_line_ids!.filter(id => id !== line.line_id)})}/>
            {t('line')} {lineIndex + 1}
          </label>)}
          {new Set(draft.lines.filter(line => entry.applicable_line_ids === undefined || entry.applicable_line_ids.includes(line.line_id)).map(line => line.price_mode)).size > 1 && <p role="alert" className="text-destructive">{t('mixedModes')}</p>}
        </fieldset>}
      </div>)}
      <Button id={prefix + '-add'} variant="outline" disabled={disabled || values.length >= 20}
        onClick={() => update([...values, {adjustment_id: crypto.randomUUID(), type: 'DISCOUNT', calculation_mode: 'PERCENTAGE', value: '0', sequence: values.length + 1}])}>
        {t('addAdjustment')}
      </Button>
    </div>;
  }
  function readonly(value: unknown, depth = 0): ReactNode {
    if (value === null || value === undefined) return <span className="text-muted-foreground">{t('unknown')}</span>;
    if (typeof value === 'boolean') return text(value ? 'yes' : 'no');
    if (typeof value !== 'object') return <span className="tabular-nums break-words [overflow-wrap:anywhere]">{text(String(value))}</span>;
    if (depth > 12) return '—';
    if (Array.isArray(value)) return <ol className="min-w-0 space-y-3">{value.map((item, index) => <li key={index} className="min-w-0 rounded border p-3">{readonly(item, depth + 1)}</li>)}</ol>;
    return <dl className="grid min-w-0 grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
      {Object.entries(value).map(([key, item]) => {
        const composite = item !== null && typeof item === 'object';
        return <div key={key} className="contents">
          <dt className={'min-w-0 text-xs text-muted-foreground break-words [overflow-wrap:anywhere]' + (composite ? ' col-span-full mt-2 font-medium' : '')}>{text(key)}</dt>
          <dd className={'min-w-0 text-sm' + (composite ? ' col-span-full text-left' : ' sm:text-right')}>{readonly(item, depth + 1)}</dd>
        </div>;
      })}
    </dl>;
  }
  function result(snapshot: TaxCalculationSnapshot, id: string) {
    const output = snapshot.output;
    return <div id={id} className="min-w-0 space-y-3">
      <div className="flex flex-wrap gap-2"><Badge>{t(output.isSimulation ? 'simulation' : 'calculation')}</Badge><Badge variant="outline">{output.result.currency}</Badge><span className="text-xs text-muted-foreground">{output.result.calculationPolicyCode} · v{output.result.calculationPolicyVersion}</span></div>
      <section className="rounded border p-3"><h4 className="font-medium mb-2">{t('totals')}</h4>{readonly(output.result.totals)}</section>
      <details><summary className="cursor-pointer font-medium">{t('summaries')}</summary><div className="pt-2">{readonly(output.result.summaries)}</div></details>
      <details><summary className="cursor-pointer font-medium">{t('lineResults')}</summary><div className="pt-2">{readonly(output.result.lines)}</div></details>
      <details><summary className="cursor-pointer font-medium">{t('trace')}</summary><div className="pt-2">{readonly(output.result.calculationTrace)}</div></details>
      <details><summary className="cursor-pointer text-sm">{t('submittedInput')}</summary><div className="pt-2">{readonly(snapshot.input)}</div></details>
    </div>;
  }
  return <section id="tax-calculation-panel" className="space-y-4 pt-4">
    <div className="flex flex-wrap items-center gap-2">
      <h3 className="font-semibold">{t('title')}</h3>
      <Badge variant="outline">EUR</Badge>
      <span className="text-xs text-muted-foreground break-all">{draft.company_id}</span>
      <div className="ml-auto">{choice('tax-calc-direction', t('direction'), draft.direction, ['NORMAL', 'REVERSAL'], direction => change({...draft, direction: direction as TaxCalculationDraft['direction']}))}</div>
    </div>
    <p className="text-sm text-muted-foreground">{t('revalidationHint')}</p>
    <p className="text-xs text-muted-foreground">{t('chargesHint')}</p>
    {draft.operation_type === 'PURCHASE' && <p className="text-xs text-muted-foreground">{t('purchaseHint')}</p>}
    {policy && <details id="tax-calc-policy" className="rounded border p-3 text-sm"><summary className="cursor-pointer">{t('policy')} · {policy.policy.code} · v{policy.policy.version}</summary><div className="pt-2">{readonly(policy.policy)}</div></details>}
    {companyMismatch && <p role="alert" className="text-destructive">{t('contextMismatch')}</p>}
    {error && <div role="alert" className="rounded border border-destructive p-3 text-sm text-destructive">
      {text(error.code)}{error.field && <span> · {error.field}</span>}
      {error.trace != null && <details className="mt-2"><summary>{t('fiscalTrace')}</summary>{readonly(error.trace)}</details>}
    </div>}
    <div className="max-h-[65vh] overflow-y-auto space-y-3 pr-1">
      {draft.lines.map((line, i) => {
        const update = (patch: Partial<typeof line>) => change({...draft, lines: draft.lines.map((value, index) => index === i ? {...value, ...patch} : value)});
        return <article key={line.line_id} id={'tax-calc-line-' + line.line_id} className="rounded-lg border p-3 space-y-3">
          <div className="flex items-start gap-3"><div className="min-w-0 flex-1">
            <h4 className="text-sm font-semibold">{t('line')} {i + 1} · {line.scenario.input.tax_date}</h4>
            <p className="text-xs text-muted-foreground break-all">{t('item')}: {line.scenario.input.item_id}</p>
            <p className="text-xs text-muted-foreground break-all">{t('partner')}: {line.scenario.input.business_partner_id}</p>
            {!!line.scenario.draftVersionIds.length && <Badge variant="secondary">{t('draftScenario')}</Badge>}
          </div><Button id={'tax-calc-remove-' + line.line_id} size="icon" variant="ghost" disabled={disabled} aria-label={t('removeLine')}
            onClick={() => change({...draft, lines: draft.lines.filter(value => value.line_id !== line.line_id), document_adjustments: draft.document_adjustments.map(value => value.applicable_line_ids === undefined ? value : {...value, applicable_line_ids: value.applicable_line_ids.filter(id => id !== line.line_id)})})}>×</Button></div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {decimal('tax-calc-quantity-' + line.line_id, t('quantity'), line.quantity, `lines[${i}].quantity`, quantity => update({quantity}))}
            {decimal('tax-calc-price-' + line.line_id, t('unitPrice'), line.unit_price, `lines[${i}].unit_price`, unit_price => update({unit_price}))}
            {choice('tax-calc-price-mode-' + line.line_id, t('priceMode'), line.price_mode, ['TAX_EXCLUSIVE', 'TAX_INCLUSIVE'], price_mode => update({price_mode: price_mode as typeof line.price_mode}))}
            {draft.operation_type === 'PURCHASE' && decimal('tax-calc-deductible-' + line.line_id, t('deductiblePercentage'), line.deductible_percentage ?? '', `lines[${i}].deductible_percentage`, value => update({deductible_percentage: value || null}), true)}
          </div>
          <details><summary className="cursor-pointer text-sm">{t('lineAdjustments')} ({line.adjustments.length})</summary><div className="pt-2">{adjustments(line.adjustments, adjustments => update({adjustments}), 'tax-calc-adjustments-' + line.line_id, `lines[${i}].adjustments`)}</div></details>
          {issue(`lines[${i}].fiscal_context`) && <p role="alert" className="text-sm text-destructive">{t('fiscalContextError')}</p>}
        </article>;
      })}
    </div>
    {!draft.lines.length && <p className="text-sm text-muted-foreground">{t('empty')}</p>}
    <section className="space-y-2"><h4 className="text-sm font-medium">{t('documentAdjustments')}</h4>
      {adjustments(draft.document_adjustments, document_adjustments => change({...draft, document_adjustments}), 'tax-calc-document', 'document_adjustments', true)}
    </section>
    <div className="flex flex-wrap gap-2 items-center">
      <Button id="tax-calc-run" disabled={disabled || !canRun || !policy || !draft.lines.length || companyMismatch} onClick={onCalculate}>{t('calculateRevalidate')}</Button>
      {taxCalculationStale(state.submitted, draft) && <Badge id="tax-calc-stale" variant="secondary">{t('stale')}</Badge>}
      <Button id="tax-calc-reset" variant="ghost" disabled={disabled} onClick={() => change({...draft, lines: [], document_adjustments: []})}>{t('clearLines')}</Button>
    </div>
    {state.submitted && <section className="space-y-3 border-t pt-4">
      <div className="flex flex-wrap gap-2"><Button id="tax-calc-pin" variant="outline" disabled={disabled} onClick={() => onChange({...state, comparison: structuredClone(state.submitted)})}>{t('pin')}</Button>
        {state.comparison && <Button variant="ghost" disabled={disabled} onClick={() => onChange({...state, comparison: null})}>{t('clearPin')}</Button>}
      </div>
      <div className={state.comparison ? 'grid gap-4 lg:grid-cols-2' : ''}>
        {state.comparison && <div className="min-w-0"><h4 className="font-medium mb-2">{t('pinned')}</h4>{result(state.comparison, 'tax-calc-comparison')}</div>}
        <div className="min-w-0"><h4 className="font-medium mb-2">{t('latest')}</h4>{result(state.submitted, 'tax-calc-result')}</div>
      </div>
    </section>}
  </section>;
}
