import type {CatalogKind} from './catalog';
export const catalogCompanyResource='catalog-item-companies';
export type CatalogCompanyOption={id:string;name:string;code:string|null;is_enabled:boolean;permissions:string[];legal_address?:{address:string|null;postal_code:string|null;city:string|null;province:string|null;country_code:string|null}|null};
export type CatalogCompanyValues={is_enabled:boolean;is_sellable:boolean;is_purchasable:boolean;track_stock:boolean;default_sales_uom_id:string|null;default_purchase_uom_id:string|null};
export type CatalogCompanyRow=CatalogCompanyValues & {id:string;company_id:string;item_id?:string;catalog_item_id?:string;company_name:string;company_is_enabled:boolean;item_code:string;item_name:string;item_status:string;kind:CatalogKind;base_uom_id:string;effective_sales_uom_id:string;effective_purchase_uom_id:string;canSell:boolean;canPurchase:boolean;canTrackStock:boolean;version:number};
export type CatalogCompanyContext={item:{id:string;code:string;name:string;status:string;kind:CatalogKind;base_uom_id:string};defaults:{is_sellable:boolean;is_purchasable:boolean;track_stock:boolean};units:{id:string;name:string;code:string;is_active:boolean}[]};
export type CatalogCompanyEditor={itemId:string;companyId:string;version:number;values:CatalogCompanyValues;readonly:boolean;blocked?:boolean};
export type CatalogCompanyBulk={itemIds:string[];companyIds:string[];search:string;page:number;companyPage?:number};
export const catalogCompanyCapabilities=['canSell','canPurchase','canTrackStock'] as const;
export type CatalogCompanyCapabilityFilter='ALL'|'YES'|'NO';
export type CatalogCompanyState={filterVersion:2;companyId:string;search:string;enabled:'ALL'|'ENABLED'|'DISABLED';canSell:CatalogCompanyCapabilityFilter;canPurchase:CatalogCompanyCapabilityFilter;canTrackStock:CatalogCompanyCapabilityFilter;page:number;filtersExpanded?:boolean;editor:CatalogCompanyEditor|null;bulk:CatalogCompanyBulk|null};
export type CatalogCompanyPending={path:string;method:string;body:unknown;itemIds:string[];companyIds:string[];committed?:boolean};
export const catalogCompanyDefaults:CatalogCompanyState={filterVersion:2,companyId:'',search:'',enabled:'ENABLED',canSell:'ALL',canPurchase:'ALL',canTrackStock:'ALL',page:1,editor:null,bulk:null};
export function catalogCompanyValues(value:CatalogCompanyValues):CatalogCompanyValues{return {is_enabled:!!value.is_enabled,is_sellable:!!value.is_sellable,is_purchasable:!!value.is_purchasable,track_stock:!!value.track_stock,default_sales_uom_id:value.default_sales_uom_id||null,default_purchase_uom_id:value.default_purchase_uom_id||null};}
export function catalogCompanyInitial(context:CatalogCompanyContext):CatalogCompanyValues{return {is_enabled:true,is_sellable:context.defaults.is_sellable,is_purchasable:context.defaults.is_purchasable,track_stock:context.item.kind==='GOOD'&&context.defaults.track_stock,default_sales_uom_id:null,default_purchase_uom_id:null};}
export function companyAuthority(options:CatalogCompanyOption[],id:string,action:string){return options.some(c=>c.id===id&&c.permissions.includes(action));}
export function companyItemId(row:CatalogCompanyRow){return row.item_id??row.catalog_item_id??'';}
export function companyItemPath(companyId:string,itemId:string){return `/companies/${encodeURIComponent(companyId)}/catalog/items/${encodeURIComponent(itemId)}`;}
