export const taxSections = ['tax-codes','tax-types','tax-nature-codes','tax-item-classifications','tax-partner-classifications','tax-regimes','tax-rules','tax-determination'] as const;
export type TaxSection = typeof taxSections[number];
export const taxTreatments = ['TAXABLE','ZERO_RATED','EXEMPT','NON_TAXABLE','REVERSE_CHARGE','OUT_OF_SCOPE','EXCLUDED','MARGIN','OTHER_EU'] as const;
export type TaxTreatment = typeof taxTreatments[number];
export type TaxType = {id:string;code:string;name:string;description?:string|null;is_active:boolean};
export type TaxCountry = {id:string;iso_code:string;name:string};
export type TaxNature = {id:string;country_id:string;code:string;name?:string;description?:string;is_active?:boolean;valid_from?:string;valid_to?:string|null};
export type TaxVersion = {id?:string;rate:string;treatment:TaxTreatment;tax_nature_code_id:string|null;tax_nature_code?:string|null;legal_reference:string|null;valid_from:string;valid_to:string|null;created_at?:string;created_by?:string|null};
export type TaxCode = {id:string;tenant_id:string;tax_type_id:string;country_id:string;code:string;name:string;description:string|null;is_active:boolean;version:number;created_at:string;updated_at:string;versions?:TaxVersion[];tax_type_code?:string;country_code?:string;country_iso_code?:string;rate?:string|null;treatment?:TaxTreatment|null;tax_nature_code?:string|null};
export type TaxEditor = {id:string|null;expectedVersion:number;original:TaxCode|null;values:{name:string;code:string;description:string;tax_type_id:string;country_id:string};versions:TaxVersion[];readonly:boolean};
export type TaxState = {section:TaxSection;search:string;page:number;date:string;country:string;filtersExpanded:boolean;tab:'general'|'versions'|'audit';editor:TaxEditor|null;versionDraft:TaxVersion|null;versionIndex:number|null;installDate:string|null;transition:TaxCode|null};
export type TaxPending = {path:string;method:string;body:unknown;recordId:string|null;action:string};
export const blankTaxVersion = ():TaxVersion => ({rate:'22',treatment:'TAXABLE',tax_nature_code_id:null,legal_reference:null,valid_from:'',valid_to:null});
export const taxDefaults = (now=new Date()):TaxState => ({
  section:'tax-codes',search:'',page:1,
  // The filter is a local calendar day, not an instant converted to UTC.
  date:`${String(now.getFullYear()).padStart(4,'0')}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`,
  country:'',filtersExpanded:false,tab:'general',editor:null,versionDraft:null,
  versionIndex:null,installDate:null,transition:null,
});
export function taxKey(user:string,tenant:string) {return `tax-management:${encodeURIComponent(user)}:${encodeURIComponent(tenant)}`;}
export function taxDateValid(value:string):boolean {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(value)||value.startsWith('0000-'))return false;
  const date=new Date(value+'T00:00:00Z');
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0,10)===value;
}
export function taxRateValid(rate:string):boolean {
  if(rate.length>20 || !/^\d+(?:\.\d{1,6})?$/.test(rate))return false;
  return BigInt(rate.split('.')[0])<=999n;
}
export function taxNatureRequired(treatment:TaxTreatment,country:string):boolean {return country==='IT' && !['TAXABLE','ZERO_RATED'].includes(treatment);}
export const taxNatureTreatments:Partial<Record<TaxTreatment,string[]>>={EXCLUDED:['N1'],OUT_OF_SCOPE:['N2.1','N2.2'],NON_TAXABLE:['N3.1','N3.2','N3.3','N3.4','N3.5','N3.6'],EXEMPT:['N4'],MARGIN:['N5'],REVERSE_CHARGE:['N6.1','N6.2','N6.3','N6.4','N6.5','N6.6','N6.7','N6.8','N6.9'],OTHER_EU:['N7']};
export function taxNatureChoices(rows:TaxNature[],countryId:string,country:string,treatment:TaxTreatment) {
  if(['TAXABLE','ZERO_RATED'].includes(treatment))return [];
  return rows.filter(row=>row.country_id===countryId && row.is_active!==false && (country!=='IT'||taxNatureTreatments[treatment]?.includes(row.code)));
}
export function validateTaxVersion(row:TaxVersion,country:string,natures:TaxNature[]):string|null {
  if(row.legal_reference && row.legal_reference.length>255)return 'tax_field_too_long';
  if(!taxRateValid(row.rate))return 'tax_invalid_rate';
  if(!taxTreatments.includes(row.treatment))return 'tax_invalid_treatment';
  if(country==='IT' && row.treatment==='ZERO_RATED')return 'tax_zero_rated_not_applicable';
  const positive=/[1-9]/.test(row.rate);
  if(row.treatment==='TAXABLE' ? !positive || !!row.tax_nature_code_id : positive)return 'tax_invalid_rate';
  if(!taxDateValid(row.valid_from) || row.valid_to!==null && (!taxDateValid(row.valid_to) || row.valid_to<row.valid_from))return 'tax_invalid_period';
  const nature=natures.find(n=>n.id===row.tax_nature_code_id);
  if(row.tax_nature_code_id && (!nature || nature.is_active===false))return 'tax_invalid_nature';
  if(nature && (nature.valid_from && nature.valid_from>row.valid_from || nature.valid_to && (!row.valid_to || nature.valid_to<row.valid_to)))return 'tax_nature_validity_mismatch';
  if(['TAXABLE','ZERO_RATED'].includes(row.treatment) && row.tax_nature_code_id)return 'tax_invalid_nature';
  if(taxNatureRequired(row.treatment,country) && !nature)return 'tax_invalid_nature';
  if(country==='IT' && nature && !taxNatureTreatments[row.treatment]?.includes(nature.code))return 'tax_invalid_nature';
  return null;
}
export function validateTaxVersions(rows:TaxVersion[],country:string,natures:TaxNature[]):string|null {
  if(!rows.length)return 'initialVersionRequired';
  if(rows.length>100)return 'tax_versions_required';
  for(const row of rows){const error=validateTaxVersion(row,country,natures);if(error)return error;}
  const sorted=[...rows].sort((a,b)=>a.valid_from.localeCompare(b.valid_from));
  for(let i=1;i<sorted.length;i++)if(!sorted[i-1].valid_to || sorted[i-1].valid_to!>=sorted[i].valid_from)return 'tax_version_overlap';
  return null;
}
export function taxMetadataPayload(editor:TaxEditor) {return {values:{name:editor.values.name,description:editor.values.description || null},expectedVersion:editor.expectedVersion};}
export function taxCreatePayload(editor:TaxEditor) {return {values:{...editor.values,description:editor.values.description || null},versions:editor.versions.map(({rate,treatment,tax_nature_code_id,legal_reference,valid_from,valid_to})=>({rate,treatment,tax_nature_code_id,legal_reference:legal_reference||null,valid_from,valid_to}))};}
export function advanceTaxEditor(editor:TaxEditor,record:TaxCode,usedVersion:number):TaxEditor {
  // Solo il risultato della propria mutazione può avanzare la baseline della bozza.
  if(editor.id!==record.id || editor.expectedVersion!==usedVersion) return editor;
  return {...editor,expectedVersion:record.version,original:record,versions:record.versions??editor.versions};
}
export function readTaxState(storage:Pick<Storage,'getItem'>,key:string):TaxState {
  const defaults=taxDefaults();
  try {
    const saved=JSON.parse(storage.getItem(key)||'null');
    if(!saved || typeof saved!=='object')return defaults;
    const editor=saved.editor;
    return {...defaults,section:taxSections.includes(saved.section)?saved.section:defaults.section,search:typeof saved.search==='string'?saved.search:'',page:Number.isSafeInteger(saved.page)&&saved.page>0?saved.page:1,date:saved.date==='' || taxDateValid(saved.date)?saved.date:defaults.date,country:typeof saved.country==='string'?saved.country:'',filtersExpanded:saved.filtersExpanded===true,tab:['general','versions','audit'].includes(saved.tab)?saved.tab:'general',editor:editor && typeof editor.values?.name==='string' && typeof editor.values?.code==='string' && typeof editor.values?.country_id==='string' && typeof editor.values?.tax_type_id==='string' && Array.isArray(editor.versions) && Number.isSafeInteger(editor.expectedVersion) && (editor.id===null || typeof editor.id==='string' && editor.expectedVersion>0 && editor.original?.id===editor.id) ? editor:null,versionDraft:saved.versionDraft && typeof saved.versionDraft.rate==='string'?saved.versionDraft:null,versionIndex:Number.isSafeInteger(saved.versionIndex)?saved.versionIndex:null,installDate:typeof saved.installDate==='string'?saved.installDate:null,transition:saved.transition && typeof saved.transition.id==='string' && Number.isSafeInteger(saved.transition.version)?saved.transition:null};
  }catch{return defaults;}
}
export function resetTaxState(storage:Pick<Storage,'removeItem'|'getItem'>,key:string) {
  // Il marker e la bozza di un comando incerto devono restare disponibili per la verifica.
  if(!storage.getItem(key+':pending')&&!storage.getItem(key+':classifications:item:pending')&&!storage.getItem(key+':classifications:partner:pending'))storage.removeItem(key);
}
