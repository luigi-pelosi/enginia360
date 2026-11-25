import type {Row} from './model';
import type {ItemOptions} from './catalog-items';
export const catalogKinds = ['GOOD','INTANGIBLE','SERVICE','CHARGE'] as const;
export type CatalogKind = typeof catalogKinds[number];
export type CatalogResource = 'catalog-units' | 'catalog-categories' | 'catalog-types' | 'catalog-numbering' | 'catalog-brands';
export type CatalogEditor = {id: string | null; version: number; values: Record<string, unknown>; original: Record<string, unknown>; readonly?: boolean};
export type CatalogState = {filtersExpanded?: boolean; search: string; page: number; editor: CatalogEditor | null; deleting: Row | null; kind: 'ALL' | CatalogKind; kindFilterVersion?: number; conversion: {sourceId: string; targetId: string; quantity: string} | null};
export type CatalogPending = {method: string; id: string | null; kind: string; values: Record<string, unknown>; version: number; committed?: boolean};
export const catalogDefaults: CatalogState = {search:'',page:1,editor:null,deleting:null,kind:'ALL',kindFilterVersion:1,conversion:null};
type Storage = Pick<globalThis.Storage, 'getItem' | 'setItem' | 'removeItem'>;
export function catalogKey(user: string, tenant: string, resource: string) {return `catalog:v1:${encodeURIComponent(user)}:${encodeURIComponent(tenant)}:${resource}`;}
export function readCatalog<T>(storage: Storage, key: string): T | null {try {return JSON.parse(storage.getItem(key) || 'null');} catch {return null;}}
export function storeCatalog(storage: Storage, key: string, value: unknown) {try {if(value === null) storage.removeItem(key); else storage.setItem(key,JSON.stringify(value)); return true;} catch {return false;}}
export function resetCatalog(storage: Storage, key: string) {try {if (!storage.getItem(key+':pending')) storeCatalog(storage,key,null);} catch { /* Un guard illeggibile non autorizza il reset. */ }}
export function categoryParents(rows: Row[], id: string | null) {
  const excluded = new Set(id ? [id] : []);
  const children = new Map<string, string[]>();
  for (const r of rows) if (r.parent_id) children.set(String(r.parent_id), [...children.get(String(r.parent_id)) ?? [],r.id]);
  const queue = [...excluded];
  for(let i=0;i<queue.length;i++) for(const child of children.get(queue[i]) ?? []) if(!excluded.has(child)) {excluded.add(child);queue.push(child);}
  return rows.filter(r=>!excluded.has(r.id));
}
export function categoryPath(rows: Row[], id: string) {
  const byId=new Map(rows.map(r=>[r.id,r])), seen=new Set<string>(), path:string[]=[];
  let row=byId.get(id);
  while(row && !seen.has(row.id)) {seen.add(row.id);path.unshift(String(row.name));row=byId.get(String(row.parent_id));}
  return path.join(' / ');
}
export const catalogItemColumns=['code','name','item_type_id','category_id','base_uom_id','brand_id','status'] as const;
export function catalogItemText(row:Row,column:string,options:Pick<ItemOptions,'types'|'categories'|'units'|'brands'>):string {
  if(column==='category_id')return categoryPath(options.categories,String(row.category_id??''))||'—';
  const references=column==='item_type_id'?options.types:column==='base_uom_id'?options.units:column==='brand_id'?options.brands:null;
  return references?String(references.find(reference=>reference.id===row[column])?.name??'—'):String(row[column]??'—');
}
export function catalogValues(resource: CatalogResource, values: Record<string, unknown>, editing: boolean) {
  let fields = resource === 'catalog-units' ? ['name','code','decimal_places','is_active',...editing ? [] : ['dimension','factor_to_base','is_base','conversion_scope']]
    : resource === 'catalog-categories' ? ['name','code','description','parent_id','sort_order','is_active']
    : resource === 'catalog-brands' ? ['name','code','description','is_active']
    : ['name','code','default_sellable','default_purchasable','default_track_stock','is_active',...editing ? [] : ['kind']];
  const result = Object.fromEntries(fields.filter(f=>Object.hasOwn(values,f)).map(f=>[f,values[f] === '' && ['code','description','parent_id'].includes(f) ? null : values[f]]));
  if(resource==='catalog-types' && values.kind !== 'GOOD') result.default_track_stock=false;
  if(resource==='catalog-units' && !editing && values.conversion_scope==='ITEM'){result.factor_to_base=null;result.is_base=false;}
  return result;
}
export function catalogInitial(resource: CatalogResource): Record<string,unknown> {
 return resource === 'catalog-units' ? {name:'',code:'',dimension:'COUNT',conversion_scope:'UNIVERSAL',factor_to_base:'1',decimal_places:0,is_base:false,is_active:true}
 : resource === 'catalog-categories' ? {name:'',code:'',description:'',parent_id:null,sort_order:0,is_active:true}
 : resource === 'catalog-brands' ? {name:'',code:'',description:'',is_active:true}
 : {name:'',code:'',kind:'GOOD',default_sellable:true,default_purchasable:true,default_track_stock:true,is_active:true};
}
export function catalogUncertain(error: {status?: number; code?: string}) {return !error.status || error.status >= 500;}
