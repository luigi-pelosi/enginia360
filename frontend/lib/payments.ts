export type Installment = {percentage:string; offsetMonths:number; offsetDays:number; dateRule:string; offsetBase:string; fixedDay:number|null; methodId:string|null};
export function installmentsValid(rows: Installment[]): boolean {
  if (!rows.length) return false;
  let sum = 0;
  for (const row of rows) {
    const match = /^(\d{1,3})(?:\.(\d{1,4}))?$/.exec(row.percentage);
    if (!match) return false;
    const value = Number(match[1]) * 10000 + Number((match[2] || '').padEnd(4, '0'));
    if (value <= 0 || value > 1000000 || !Number.isSafeInteger(row.offsetMonths) || !Number.isSafeInteger(row.offsetDays) || row.offsetMonths < 0 || row.offsetDays < 0) return false;
    if (!['EXACT','END_OF_MONTH','FIXED_DAY'].includes(row.dateRule) || !['REFERENCE_DATE','REFERENCE_MONTH_END'].includes(row.offsetBase)) return false;
    if (row.dateRule === 'FIXED_DAY' ? !Number.isInteger(row.fixedDay) || row.fixedDay! < 1 || row.fixedDay! > 31 : row.fixedDay !== null) return false;
    sum += value;
  }
  return sum === 1000000;
}

export type PaymentReference = {id?:string; code:string; name:string; isActive:boolean};
export type PaymentMethodReference = PaymentReference & {direction:string};
export type PaymentTermReference = PaymentReference & {defaultMethodId:string|null; installments:{methodId:string|null}[]};
export function methodCompatible(method:PaymentMethodReference, direction:'INBOUND'|'OUTBOUND'):boolean { return method.isActive && (method.direction === 'BOTH' || method.direction === direction); }
export function termCompatible(term:PaymentTermReference, methods:PaymentMethodReference[], direction:'INBOUND'|'OUTBOUND'):boolean {
  return term.isActive && [term.defaultMethodId,...term.installments.map(row=>row.methodId)].every(id=>!id || methods.some(method=>method.id===id && methodCompatible(method,direction)));
}
export function referenceOptions<T extends PaymentReference>(rows:T[], selected:string|null, allowed:(row:T)=>boolean, disabledLabel:string) {
  const label=(row:T)=>`${row.code} · ${row.name}${row.isActive?'':` · ${disabledLabel}`}`;
  const options=rows.filter(allowed).filter(row=>row.id).map(row=>({value:row.id!,label:label(row)}));
  if(selected && !options.some(option=>option.value===selected)) { const row=rows.find(item=>item.id===selected); options.push({value:selected,label:row?label(row):selected}); }
  return options;
}

export type PaymentCurrency = {code:string; name:string; is_enabled:boolean; minor_units:number|null};
export function paymentCurrencyOptions(rows:PaymentCurrency[]) { return rows.filter(row => row.is_enabled === true && row.minor_units !== null).map(row => ({value:row.code,label:`${row.code} · ${row.name}`})); }
