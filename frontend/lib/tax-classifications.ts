import type {TaxCountry, TaxType} from './tax';
export type ClassificationKind='item'|'partner';
export const classificationTemplateCodes={item:['GENERAL_GOODS','GENERAL_SERVICES','FOOD','BOOKS','MEDICAL_GOODS','DIGITAL_SERVICES','REPAIR_SERVICES','TRANSPORT_SERVICES','INTELLECTUAL_PROPERTY','ANCILLARY_CHARGES'],partner:['TAXABLE_PERSON','NON_TAXABLE_PERSON','UNKNOWN']} as const;
export type TaxClassification={id:string;tenant_id:string;country_id:string;tax_type_id:string;code:string;name:string;description:string|null;is_active:boolean;version:number;country_iso_code?:string;tax_type_code?:string;updated_at?:string};
export type ClassificationEditor={id:string|null;expectedVersion:number;original:TaxClassification|null;readonly:boolean;values:{name:string;code:string;description:string;country_id:string;tax_type_id:string}};
export type ClassificationState={search:string;country:string;type:string;status:string;page:number;filtersExpanded:boolean;editor:ClassificationEditor|null;transition:TaxClassification|null;install:{country_id:string;tax_type_id:string}|null};
export type ClassificationLookups={countries:TaxCountry[];types:TaxType[];classifications:TaxClassification[]};
export const classificationDefaults=():ClassificationState=>({search:'',country:'',type:'',status:'',page:1,filtersExpanded:false,editor:null,transition:null,install:null});
export function classificationKey(base:string,kind:ClassificationKind){return base+':classifications:'+kind;}
export function classificationEditor(row:TaxClassification|null,lookups:ClassificationLookups,readonly=false):ClassificationEditor {
 return row?{id:row.id,expectedVersion:row.version,original:row,readonly,values:{name:row.name,code:row.code,description:row.description||'',country_id:row.country_id,tax_type_id:row.tax_type_id}}:{id:null,expectedVersion:0,original:null,readonly:false,values:{name:'',code:'',description:'',country_id:lookups.countries[0]?.id||'',tax_type_id:lookups.types.find(t=>t.code==='VAT'&&t.is_active)?.id||''}};
}
export function classificationPayload(editor:ClassificationEditor) {
 const {name,description,code,country_id,tax_type_id}=editor.values;
 return editor.id?{values:{name,description:description||null},expectedVersion:editor.expectedVersion}:{values:{name,description:description||null,code,country_id,tax_type_id}};
}
export function classificationValid(editor:ClassificationEditor){const v=editor.values;return !!v.name.trim()&&v.name.length<=150&&!!v.code.trim()&&v.code.length<=50&&v.description.length<=10000&&!!v.country_id&&!!v.tax_type_id;}
export function readClassificationState(storage:Pick<Storage,'getItem'>,key:string):ClassificationState {
 const defaults=classificationDefaults();try {
  const s=JSON.parse(storage.getItem(key)||'null');if(!s||typeof s!=='object')return defaults;
  for(const field of ['search','country','type','status'] as const)if(typeof s[field]==='string')defaults[field]=s[field];
  if(!['','true','false'].includes(defaults.status))defaults.status='';
  defaults.page=Number.isSafeInteger(s.page)&&s.page>0?s.page:1;defaults.filtersExpanded=s.filtersExpanded===true;
  const e=s.editor;if(e&&typeof e.readonly==='boolean'&&e.values&&['name','code','description','country_id','tax_type_id'].every(k=>typeof e.values[k]==='string')&&(e.id===null&&e.expectedVersion===0||typeof e.id==='string'&&Number.isSafeInteger(e.expectedVersion)&&e.expectedVersion>0&&e.original?.id===e.id&&e.original.version===e.expectedVersion))defaults.editor=e;
  if(s.transition&&typeof s.transition.id==='string'&&Number.isSafeInteger(s.transition.version)&&typeof s.transition.is_active==='boolean')defaults.transition=s.transition;
  if(s.install&&typeof s.install.country_id==='string'&&typeof s.install.tax_type_id==='string')defaults.install=s.install;
  return defaults;
 }catch{return defaults;}
}
export function resetClassificationState(storage:Pick<Storage,'getItem'|'removeItem'>,base:string){for(const kind of ['item','partner'] as const){const key=classificationKey(base,kind);if(!storage.getItem(key+':pending'))storage.removeItem(key);}}
