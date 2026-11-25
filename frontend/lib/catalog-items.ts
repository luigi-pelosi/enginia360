import type {Row} from './model';
import type {CatalogKind} from './catalog';
import type {CatalogCompanyValues,CatalogCompanyOption} from './catalog-companies';
export type ItemCompanyDraft={company_id:string;values:CatalogCompanyValues};
export type ItemKind=CatalogKind;
export type ItemStatus='ACTIVE'|'SUSPENDED'|'ARCHIVED';
export type ItemRecord=Row & {version:number;kind:ItemKind;status:ItemStatus;activated_at?:string|null;identifiers:Row[];units:Row[];physicalData:Record<string,unknown>|null};
export type ItemOptions={types:Row[];categories:Row[];units:Row[];brands:Row[];numbering:Partial<Record<ItemKind,{mode:'AUTO'|'MANUAL'}>>};
export type ItemEditor={id:string|null;version:number;values:Record<string,unknown>;original:Record<string,unknown>;record:ItemRecord;readonly:boolean;statusDraft?:ItemStatus;physicalDraft?:Record<string,unknown>;companyDrafts?:ItemCompanyDraft[]};
export type ItemRowEditor={collection:'identifiers'|'units'|'physical-data';id:string|null;values:Record<string,unknown>;readonly:boolean;version:number};
export type ItemState={filtersExpanded?:boolean;filterVersion:2;search:string;status:string;itemTypeId:string;page:number;tab:'general'|'identifiers'|'units'|'physical'|'companies';editor:ItemEditor|null;rowEditor:ItemRowEditor|null;removing:boolean;transition:ItemStatus|null;conversion:{sourceUnitId:string;targetUnitId:string;quantity:string}|null};
export type ItemPending={id:string|null;path:string;method:string;body:unknown;version:number;committed?:boolean};
export const itemDefaults:ItemState={filterVersion:2,search:'',status:'ACTIVE',itemTypeId:'ALL',page:1,tab:'general',editor:null,rowEditor:null,removing:false,transition:null,conversion:null};
export function itemInitial():Record<string,unknown>{return {name:'',code:'',description:'',item_type_id:null,category_id:null,base_uom_id:null,brand_id:null};}
const mainFields=['name','code','description','item_type_id','category_id','base_uom_id','brand_id'];
export function itemValues(values:Record<string,unknown>){return Object.fromEntries(mainFields.map(name=>[name,values[name]===''||values[name]===undefined?null:values[name]]));}
export function itemEditor(record:Partial<ItemRecord> & Row,readonly=false):ItemEditor {
 const root={...record,version:Number(record.version??0),status:record.status??'ACTIVE',kind:record.kind??'GOOD',identifiers:record.identifiers??[],units:record.units??[],physicalData:record.physicalData??null} as ItemRecord;
 const values={...itemInitial(),...itemValues(root)};
 return {id:root.id||null,version:root.version,values,original:structuredClone(values),record:root,readonly};
}
// Il token cambia solo dopo una mutazione verificata sulla versione precedente.
export function adoptItemChildren(editor:ItemEditor,record:Partial<ItemRecord> & Row):ItemEditor {
 if(record.id!==editor.id||Number(record.version)<=editor.version)throw new Error('stale_version');
 return {...editor,version:Number(record.version),record:record as ItemRecord};
}
export function itemCanChangeBase(editor:ItemEditor){return !editor.record.activated_at&&!editor.record.units.length&&!editor.record.identifiers.length&&!editor.record.physicalData&&!physicalPresent(editor.physicalDraft);}
export function itemCodeEditable(editor:ItemEditor,mode:string){return mode==='MANUAL'&&(!editor.id||editor.record.status==='SUSPENDED'&&!editor.record.activated_at);}
// Contratto condiviso tra input e validazione: nessuna normalizzazione del codice manuale.
export const itemManualCodePattern='[A-Za-z0-9]{1,40}';
export const itemManualCodeMaxLength=40;
export const itemManualCodeError='catalog_item_manual_code_invalid';
export function itemManualCodeInvalid(editor:ItemEditor,mode:string|undefined):boolean {
 if(mode!=='MANUAL'||editor.id&&editor.values.code===editor.original.code)return false;
 const code=editor.values.code;
 return typeof code!=='string'||code.length<1||code.length>itemManualCodeMaxLength||/[^A-Za-z0-9]/.test(code);
}
export function itemTransitions(status:string):ItemStatus[]{return status==='ACTIVE'?['SUSPENDED','ARCHIVED']:status==='SUSPENDED'?['ACTIVE','ARCHIVED']:[];}
export function itemUnitValues(values:Record<string,unknown>,unit?:Row,base?:Row){return {uom_id:values.uom_id,conversion_numerator:unit?.conversion_scope==='UNIVERSAL'?String(unit.factor_to_base):String(values.conversion_numerator??''),conversion_denominator:unit?.conversion_scope==='UNIVERSAL'?String(base?.factor_to_base??''):String(values.conversion_denominator??''),is_active:!!values.is_active};}
export function identifierValues(values:Record<string,unknown>){return {identifier_type:values.identifier_type,value:values.value,uom_id:values.uom_id||null,is_primary:!!values.is_primary};}
export function physicalValues(values:Record<string,unknown>){return Object.fromEntries(['net_weight','gross_weight','weight_uom_id','length','width','height','dimension_uom_id'].map(name=>[name,values[name]===''||values[name]==null?null:String(values[name])]));}
export function invalidPhysicalField(values:Record<string,unknown>|null|undefined):string|null {
 for(const name of ['net_weight','gross_weight','length','width','height']) {
  const text=String(values?.[name]??'').trim();
  if(text && (!/^-?(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,12})?$/.test(text) || (text.startsWith('-') && /[1-9]/.test(text))))return name;
 }
 return null;
}
export function physicalPresent(values?:Record<string,unknown>|null){return !!values&&Object.values(physicalValues(values)).some(value=>value!==null);}
export function itemPhysicalPayload(editor:ItemEditor){if(!editor.physicalDraft)return {};const values=physicalValues(editor.physicalDraft);return physicalPresent(values)?{physicalData:values}:editor.record.physicalData?{physicalData:null}:{};}
export function localItemRow(editor:ItemEditor,row:ItemRowEditor,remove=false):ItemEditor {
 if(row.collection==='physical-data')return {...editor,record:{...editor.record,physicalData:remove?null:physicalValues(row.values)}};
 let rows=editor.record[row.collection].filter(r=>r.id!==row.id);
 if(!remove){const values=row.collection==='identifiers'?identifierValues(row.values):row.values;if(row.collection==='identifiers'&&values.is_primary)rows=rows.map(r=>r.identifier_type===values.identifier_type?{...r,is_primary:false}:r);rows.push({...values,id:row.id??`local-${globalThis.crypto.randomUUID()}`});}
 return {...editor,record:{...editor.record,[row.collection]:rows}};
}
export function itemCompanyInitial(type:Row|undefined,kind:ItemKind):CatalogCompanyValues {
 return {is_enabled:true,is_sellable:type?.default_sellable===true,is_purchasable:type?.default_purchasable===true,track_stock:kind==='GOOD'&&type?.default_track_stock===true,default_sales_uom_id:null,default_purchase_uom_id:null};
}
export function itemCompanyUnits(baseId:unknown,localUnits:Row[],units:Row[]):Row[]{return units.filter(unit=>unit.is_active===true&&(unit.id===baseId||localUnits.some(row=>row.uom_id===unit.id&&row.is_active===true)));}
export function itemCompanyDraftError(editor:ItemEditor,options:ItemOptions,companies?:CatalogCompanyOption[]):'draftStockInvalid'|'draftUnitInvalid'|'draftCompanyUnavailable'|null {
 const drafts=editor.companyDrafts??[],kind=options.types.find(row=>row.id===editor.values.item_type_id)?.kind??editor.record.kind;
 const units=itemCompanyUnits(editor.values.base_uom_id,editor.record.units,options.units),seen=new Set<string>();
 for(const draft of drafts){
  if(kind!=='GOOD'&&draft.values.track_stock)return 'draftStockInvalid';
  for(const name of ['default_sales_uom_id','default_purchase_uom_id'] as const)if(draft.values[name]&&!units.some(unit=>unit.id===draft.values[name]))return 'draftUnitInvalid';
  if(!draft.company_id||seen.has(draft.company_id)||companies&&!companies.some(company=>company.id===draft.company_id&&company.is_enabled&&company.permissions.includes('read')&&company.permissions.includes('create')))return 'draftCompanyUnavailable';
  seen.add(draft.company_id);
 }
 return null;
}
export function itemCreation(editor:ItemEditor){return {values:itemValues(editor.values),...(editor.companyDrafts?.length?{companies:editor.companyDrafts}:{}),identifiers:editor.record.identifiers.map(identifierValues),units:editor.record.units.map(r=>({uom_id:r.uom_id,conversion_numerator:r.conversion_numerator,conversion_denominator:r.conversion_denominator,is_active:r.is_active})),...(editor.record.kind==='GOOD'?(editor.physicalDraft?itemPhysicalPayload(editor):editor.record.physicalData?{physicalData:physicalValues(editor.record.physicalData)}:{}):{})};}
