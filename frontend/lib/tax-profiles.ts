import type {Row} from './model';
export type TaxProfileKind='item'|'partner';
export type TaxProfileDraft={country_id:string;tax_type_id:string;item_tax_classification_id?:string;partner_tax_classification_id?:string;valid_from:string;valid_to:string|null};
export type TaxProfile=TaxProfileDraft & {id:string;classification_code?:string;classification_name?:string;classification_is_active?:boolean;country_name?:string;country_iso_code?:string;tax_type_name?:string;tax_type_code?:string};
export type TaxProfileLookups={countries:Row[];types:Row[];classifications:Row[]};
export type TaxProfilePage={items:TaxProfile[];total:number;page:number;pageSize:number;version:number};
export type TaxProfileOperation='assign'|'schedule';
export type TaxProfileEditor={values:TaxProfileDraft;operation:TaxProfileOperation;expectedVersion:number;index?:number};
export type TaxProfilePending={body:{values:TaxProfileDraft;expectedVersion:number};operation:TaxProfileOperation;committedVersion?:number};
export const emptyTaxProfileLookups:TaxProfileLookups={countries:[],types:[],classifications:[]};
export function taxProfilePath(kind:TaxProfileKind,id:string){return `/tax/${kind==='item'?'items':'partners'}/${encodeURIComponent(id)}/profiles`;}
export function taxProfileKey(user:string,tenant:string,kind:TaxProfileKind,id:string){return `tax-profiles:v1:${encodeURIComponent(user)}:${encodeURIComponent(tenant)}:${kind}:${encodeURIComponent(id)}`;}
type ProfileStorage=Pick<Storage,'getItem'|'removeItem'|'length'|'key'>;
/** Clear ordinary editors across subjects; unresolved commands retain original drafts and tokens. */
export function clearTaxProfileDrafts(storage:ProfileStorage,user:string,tenant:string,kind?:TaxProfileKind,subjectId?:string){
 const prefix=`tax-profiles:v1:${encodeURIComponent(user)}:${encodeURIComponent(tenant)}:`;
 try{for(let index=storage.length-1;index>=0;index--){const key=storage.key(index);if(!key?.startsWith(prefix)||kind&&!key.startsWith(prefix+kind+':')||subjectId&&key!==taxProfileKey(user,tenant,kind!,subjectId))continue;try{const value=JSON.parse(storage.getItem(key)||'null');if(!value?.pending)storage.removeItem(key);}catch{/* An unreadable marker is not safe to discard. */}}}catch{/* Recovery storage may be inaccessible. */}
}
export function taxProfileToday(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
export function taxProfileValues(kind:TaxProfileKind,values:TaxProfileDraft):TaxProfileDraft{return {country_id:values.country_id,tax_type_id:values.tax_type_id,[kind==='item'?'item_tax_classification_id':'partner_tax_classification_id']:values[kind==='item'?'item_tax_classification_id':'partner_tax_classification_id']??'',valid_from:values.valid_from,valid_to:values.valid_to||null};}
export function taxProfileOptions(lookups:TaxProfileLookups,values:Pick<TaxProfileDraft,'country_id'|'tax_type_id'>){
 const classifications=lookups.classifications.filter(row=>row.is_active===true&&row.country_id===values.country_id&&row.tax_type_id===values.tax_type_id);
 return {countries:lookups.countries.filter(row=>row.is_active!==false&&row.is_enabled!==false),types:lookups.types.filter(row=>row.is_active===true&&(!row.country_id||row.country_id===values.country_id)),classifications};
}
export function taxProfileInitial(kind:TaxProfileKind,lookups:TaxProfileLookups,date=taxProfileToday()):TaxProfileDraft{
 const classification=lookups.classifications.find(row=>row.is_active===true&&lookups.countries.some(country=>country.id===row.country_id&&country.is_active!==false&&country.is_enabled!==false)&&lookups.types.some(type=>type.id===row.tax_type_id&&type.is_active===true&&(!type.country_id||type.country_id===row.country_id)));
 const values:TaxProfileDraft={country_id:String(classification?.country_id??''),tax_type_id:String(classification?.tax_type_id??''),valid_from:date,valid_to:null};
 return {...values,[kind==='item'?'item_tax_classification_id':'partner_tax_classification_id']:classification?.id??''};
}
function calendarDate(value:string){if(!/^\d{4}-\d{2}-\d{2}$/.test(value)||value.startsWith('0000'))return false;const parsed=new Date(value+'T00:00:00Z');return !Number.isNaN(parsed.valueOf())&&parsed.toISOString().slice(0,10)===value;}
export function taxProfileError(kind:TaxProfileKind,values:TaxProfileDraft,lookups:TaxProfileLookups):string|null{
 if(!calendarDate(values.valid_from)||values.valid_to&&!calendarDate(values.valid_to))return 'invalidDate';
 if(values.valid_to&&values.valid_to<values.valid_from)return 'invalidRange';
 const options=taxProfileOptions(lookups,values);
 if(!options.countries.some(row=>row.id===values.country_id)||!options.types.some(row=>row.id===values.tax_type_id)||!options.classifications.some(row=>row.id===values[kind==='item'?'item_tax_classification_id':'partner_tax_classification_id']))return 'classificationUnavailable';
 return null;
}
