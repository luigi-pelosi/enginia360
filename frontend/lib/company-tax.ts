import type {Row} from './model';
export function taxRegimeKey(user:string,tenant:string){return `tax-regimes:v1:${encodeURIComponent(user)}:${encodeURIComponent(tenant)}`;}
export function clearTaxRegimeDraft(storage:Pick<Storage,'removeItem'>,user:string,tenant:string){try{storage.removeItem(taxRegimeKey(user,tenant));}catch{/* Storage can be unavailable. */}}
export type CompanyTaxAction='read'|'create'|'update'|'activate'|'suspend'|'register'|'close'|'assign_regime'|'schedule_regime';
export type CompanyTaxRegimeDraft={tax_regime_id:string;valid_from:string;valid_to:string|null};
export type CompanyTaxRegistrationValues={country_id:string;tax_identifier:string;registration_type:string;valid_from:string;valid_to:string|null;notes:string|null};
export type CompanyTaxRegistrationDraft={values:CompanyTaxRegistrationValues;profiles?:CompanyTaxRegimeDraft[]};
export type CompanyTaxDraft={values:{tax_type_id:string;establishment_country_id:string;tax_code?:string|null};registrations?:CompanyTaxRegistrationDraft[]};
export type CompanyTaxRegime=Row & {country_id:string;tax_type_id:string;code:string;name:string;is_active:boolean;is_supported:boolean;valid_from:string;valid_to:string|null};
export type CompanyTaxProfile=CompanyTaxRegimeDraft & {id:string};
export type CompanyTaxRegistration=CompanyTaxRegistrationValues & {id:string;profiles:CompanyTaxProfile[]};
export type CompanyTaxConfiguration={id:string;tenant_id:string;company_id:string;tax_type_id:string;establishment_country_id:string;tax_code?:string|null;status:'DRAFT'|'ACTIVE'|'SUSPENDED';version:number;registrations:CompanyTaxRegistration[]};
export type CompanyTaxLookups={countries:Row[];types:Row[];regimes:CompanyTaxRegime[];registrationTypesByCountry:Record<string,string[]>};
export const emptyCompanyTaxLookups:CompanyTaxLookups={countries:[],types:[],regimes:[],registrationTypesByCountry:{}};
export function companyTaxToday(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
export function companyTaxDefaultCountry(refs:CompanyTaxLookups){const countries=refs.countries.filter(x=>x.is_enabled!==false&&x.is_active!==false&&x.is_supported===true);return String((countries.find(x=>x.iso_code==='IT')??countries[0])?.id??'');}
export function companyTaxInitial(refs:CompanyTaxLookups):CompanyTaxDraft{return {values:{tax_type_id:String(refs.types.find(x=>x.is_active===true&&x.code==='VAT')?.id??refs.types.find(x=>x.is_active===true)?.id??''),establishment_country_id:companyTaxDefaultCountry(refs)},registrations:[]};}
export function companyTaxRegimeOptions(refs:CompanyTaxLookups,country:string,type:string){return refs.regimes.filter(x=>x.is_active===true&&x.is_supported===true&&x.country_id===country&&x.tax_type_id===type);}
export function companyTaxKey(user:string,tenant:string,company='new'){return `company-tax:v1:${encodeURIComponent(user)}:${encodeURIComponent(tenant)}:${encodeURIComponent(company)}`;}
type TaxStorage=Pick<Storage,'getItem'|'removeItem'|'length'|'key'>;
/** Menu reset discards ordinary editors, never unresolved commands or their frozen tokens. */
export function clearCompanyTaxDrafts(storage:TaxStorage,user:string,tenant:string,companyId?:string){const prefix=`company-tax:v1:${encodeURIComponent(user)}:${encodeURIComponent(tenant)}:`;try{for(let i=storage.length-1;i>=0;i--){const key=storage.key(i);if(!key?.startsWith(prefix)||companyId!==undefined&&key!==companyTaxKey(user,tenant,companyId))continue;try{const value=JSON.parse(storage.getItem(key)||'null');if(!value?.pending)storage.removeItem(key);}catch{/* Unreadable recovery is not safe to discard. */}}}catch{/* Storage can be unavailable. */}}
export function companyTaxIdentifier(iso:string,value:string){const pattern=iso==='IT'?/^IT[0-9]{11}$/:iso==='DE'?/^DE[0-9]{9}$/:iso==='FR'?/^FR[0-9A-HJ-NP-Z]{2}[0-9]{9}$/:null;return !!pattern&&pattern.test(value)&&!/[\r\n]/.test(value);}
export function companyTaxDate(value:string){if(!/^\d{4}-\d{2}-\d{2}$/.test(value)||value.startsWith('0000'))return false;const d=new Date(value+'T00:00:00Z');return !Number.isNaN(d.valueOf())&&d.toISOString().slice(0,10)===value;}
export function companyTaxRange(from:string,to:string|null){return companyTaxDate(from)&&(!to||companyTaxDate(to)&&to>=from);}
/** Exact accepted root, not merely a matching revision. Array order is immaterial. */
export function companyTaxReadback(saved:CompanyTaxConfiguration,actual:CompanyTaxConfiguration,tenant:string,company:string){
 const canonical=(value:unknown):string=>{if(Array.isArray(value))return '['+value.map(canonical).sort().join(',')+']';if(value&&typeof value==='object')return '{'+Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>JSON.stringify(k)+':'+canonical(v)).join(',')+'}';return JSON.stringify(value);};
 return !!saved.id&&saved.id===actual.id&&saved.tenant_id===tenant&&actual.tenant_id===tenant&&saved.company_id===company&&actual.company_id===company&&Number.isSafeInteger(saved.version)&&saved.version>0&&saved.version===actual.version&&canonical(saved)===canonical(actual);
}
