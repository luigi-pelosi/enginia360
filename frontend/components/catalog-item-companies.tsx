"use client";
import {useEffect,useRef,useState,type ReactNode} from 'react';
import {useLocale,useTranslations} from 'next-intl';
import {Plus,Pencil,Eye,RefreshCw,ChevronLeft,ChevronRight,Check,X} from 'lucide-react';
import {api,ApiError} from '@/lib/api';
import {can,siteAddress,type Session,type Row} from '@/lib/model';
import {catalogKey,readCatalog,storeCatalog,catalogUncertain,catalogItemColumns,catalogItemText} from '@/lib/catalog';
import type {ItemOptions} from '@/lib/catalog-items';
import {catalogCompanyResource as resource,catalogCompanyCapabilities,catalogCompanyInitial,catalogCompanyValues,companyAuthority,companyItemId,companyItemPath,type CatalogCompanyCapabilityFilter,type CatalogCompanyOption,type CatalogCompanyRow,type CatalogCompanyContext,type CatalogCompanyState,type CatalogCompanyPending,type CatalogCompanyEditor} from '@/lib/catalog-companies';
import {FilterBar} from '@/components/ui/filter-bar';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {Label} from '@/components/ui/label';
import {Switch} from '@/components/ui/switch';
import {Checkbox} from '@/components/ui/checkbox';
import {Badge} from '@/components/ui/badge';
import {Card} from '@/components/ui/card';
import {Alert,AlertDescription} from '@/components/ui/alert';
import {Select,SelectContent,SelectItem,SelectTrigger,SelectValue} from '@/components/ui/select';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription,DialogFooter} from '@/components/ui/dialog';
import {Table,TableHeader,TableBody,TableRow,TableHead,TableCell} from '@/components/ui/table';
export type CatalogCompaniesProps={session:Session;tenantId:string;scope:(path:string)=>string;onError:(e:unknown)=>string;heading?:ReactNode;itemId?:string;itemStatus?:string;renderToolbar?:(actions:ReactNode)=>ReactNode};
type Page={items:CatalogCompanyRow[];total:number;page:number;pageSize:number};
type ItemPage={items:Row[];total:number;page:number;pageSize:number};
function restore(key:string):CatalogCompanyState{
 const saved=typeof sessionStorage==='undefined'?null:readCatalog<Omit<Partial<CatalogCompanyState>,'filterVersion'>&{filterVersion?:number}>(sessionStorage,key);
 const migrate=saved?.filterVersion!==1&&saved?.filterVersion!==2&&saved?.enabled==='ALL';
 const capability=(value:unknown):CatalogCompanyCapabilityFilter=>value==='YES'||value==='NO'?value:'ALL';
 const restored:CatalogCompanyState={filtersExpanded:saved?.filtersExpanded===true,filterVersion:2,companyId:typeof saved?.companyId==='string'?saved.companyId:'',search:typeof saved?.search==='string'?saved.search.slice(0,200):'',enabled:!migrate&&['ALL','ENABLED','DISABLED'].includes(saved?.enabled??'')?saved!.enabled!:'ENABLED',canSell:capability(saved?.canSell),canPurchase:capability(saved?.canPurchase),canTrackStock:capability(saved?.canTrackStock),page:saved?.filterVersion===2&&Number.isSafeInteger(saved?.page)&&saved!.page!>0?saved!.page!:1,editor:saved?.editor&&Number.isSafeInteger(saved.editor.version)&&saved.editor.values?saved.editor:null,bulk:saved?.bulk&&Array.isArray(saved.bulk.itemIds)&&Array.isArray(saved.bulk.companyIds)?{...saved.bulk,...(saved.bulk.companyPage===undefined?{}:{companyPage:Number.isSafeInteger(saved.bulk.companyPage)&&saved.bulk.companyPage!>0?saved.bulk.companyPage:1})}:null};
 if(saved)storeCatalog(sessionStorage,key,restored);
 return restored;
}
export function CatalogItemCompanies({session,tenantId,scope,onError,itemId,itemStatus,heading,renderToolbar}:CatalogCompaniesProps){
 const locale=useLocale(),t=useTranslations('catalogCompanies'),a=useTranslations('app'),c=useTranslations('catalog'),i=useTranslations('catalogItems');
 const itemLabel=(name:string)=>i.has(name)?i(name):c.has(name)?c(name):name;
 const tenant=session.isSuperAdmin?tenantId:session.tenantId||'',key=catalogKey(session.id,tenant,resource)+(itemId?':item:'+encodeURIComponent(itemId):'');
 const [state,setState]=useState<CatalogCompanyState>(()=>restore(key));
 const [pending,setPending]=useState<CatalogCompanyPending|null>(()=>typeof sessionStorage==='undefined'?null:readCatalog(sessionStorage,key+':pending'));
 const [options,setOptions]=useState<CatalogCompanyOption[]>([]),[result,setResult]=useState<Page>({items:[],total:0,page:1,pageSize:25});
 const [context,setContext]=useState<CatalogCompanyContext|null>(null),[current,setCurrent]=useState<CatalogCompanyRow|null>(null);
 const [chooserLoading,setChooserLoading]=useState(false);
 const [chooser,setChooser]=useState<ItemPage>({items:[],total:0,page:1,pageSize:25});
 const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(''),[revision,setRevision]=useState(0),[review,setReview]=useState<CatalogCompanyRow[]|null>(null),[notice,setNotice]=useState('');
 const [chooserReferences,setChooserReferences]=useState<ItemOptions|null>(null);
 const lock=useRef(false),live=useRef(true),keyRef=useRef(key),callbacks=useRef({scope,onError}),stateRef=useRef(state);keyRef.current=key;callbacks.current={scope,onError};stateRef.current=state;
 const readable=!!tenant&&can(session,resource,'read')&&(!itemId||can(session,'catalog-items','read'));
 const accessible=!!tenant&&(readable||!!itemId&&can(session,'catalog-items','read')&&['create','update'].some(action=>can(session,resource,action)));
 const url=(path:string)=>callbacks.current.scope(path);
 const editor=state.editor,bulk=state.bulk;
 const authority=(id:string,action:string)=>companyAuthority(options,id,action);
 const creatable=options.filter(o=>o.is_enabled&&o.permissions.includes('create')&&o.permissions.includes('read'));
 const restricted=!!editor&&!!context&&(context.item.status==='ARCHIVED'||options.find(o=>o.id===editor.companyId)?.is_enabled===false);
 const disabled=loading||busy||!!pending||!!editor?.blocked;
 const writable=!!editor&&!editor.readonly&&authority(editor.companyId,'read')&&authority(editor.companyId,editor.version?'update':'create');
 const canBulk=can(session,'catalog-items','read')&&creatable.length>0&&(!itemId||itemStatus!=='ARCHIVED');
 const companyPages=Math.max(1,Math.ceil(creatable.length/25)),companyPage=Math.min(companyPages,bulk?.companyPage??1);
 const visibleCompanies=creatable.slice((companyPage-1)*25,companyPage*25),visibleItems=chooser.items.filter(row=>row.status!=='ARCHIVED');
 const bulkDisabled=disabled||chooserLoading;
 const bulkTooLarge=!!bulk&&(bulk.itemIds.length>100||bulk.companyIds.length>100||bulk.itemIds.length*bulk.companyIds.length>500);
 function change(value:Partial<CatalogCompanyState>){setState(previous=>{const next={...previous,...value};storeCatalog(sessionStorage,key,next);return next;});}
 function fail(e:unknown){const code=e instanceof ApiError?e.code:'';setError(t.has(code)?t(code):callbacks.current.onError(e));}
 function guard(marker:CatalogCompanyPending|null){if(!storeCatalog(sessionStorage,key+':pending',marker))throw new ApiError('storageUnavailable',400);setPending(marker);}
 useEffect(()=>{live.current=true;return()=>{live.current=false;};},[]);
 // I callback inline del padre non ricaricano la bozza aziendale.
 useEffect(()=>{
  if(!accessible){setLoading(false);return;}
  let alive=true;const controller=new AbortController();setLoading(true);setError('');
  (async()=>{
   const meta=await api<{items:CatalogCompanyOption[]}>(url('/catalog/item-companies/options'),'GET',undefined,{signal:controller.signal});
   if(!alive)return;setOptions(meta.items);
   const selected=stateRef.current.companyId;
   if(selected&&!companyAuthority(meta.items,selected,'read')){change({companyId:'',page:1});return;}
   if(readable){const response=await api<Page>(url(itemId?`/catalog/items/${encodeURIComponent(itemId)}/companies`:`/catalog/item-companies?companyId=${encodeURIComponent(state.companyId)}&page=${state.page}&pageSize=25&search=${encodeURIComponent(state.search)}&enabled=${state.enabled}&canSell=${state.canSell}&canPurchase=${state.canPurchase}&canTrackStock=${state.canTrackStock}`),'GET',undefined,{signal:controller.signal});if(alive)setResult({...response,total:response.total??response.items.length});}
   const recovered=stateRef.current.editor;
   if(recovered){const refs=await api<CatalogCompanyContext>(url('/catalog/item-companies/item-options/'+encodeURIComponent(recovered.itemId)),'GET',undefined,{signal:controller.signal});if(!alive)return;setContext(refs);if(recovered.version){const actual=await api<CatalogCompanyRow>(url(companyItemPath(recovered.companyId,recovered.itemId)),'GET',undefined,{signal:controller.signal});if(alive){setCurrent(actual);if(actual.version!==recovered.version&&!recovered.blocked)change({editor:{...recovered,blocked:true}});}}}
  })().catch(e=>{if(alive){setResult({items:[],total:0,page:1,pageSize:25});fail(e);if(stateRef.current.editor)change({editor:{...stateRef.current.editor,blocked:true}});}}).finally(()=>{if(alive)setLoading(false);});
  return()=>{alive=false;controller.abort();};
 },[key,accessible,readable,state.companyId,state.search,state.enabled,state.canSell,state.canPurchase,state.canTrackStock,state.page,revision]);
 useEffect(()=>{if(bulk&&!loading&&bulk.companyPage!==undefined&&bulk.companyPage!==companyPage)change({bulk:{...bulk,companyPage}});},[loading,bulk?.companyPage,companyPage]);
 useEffect(()=>{
  if(!bulk||itemId||!canBulk)return;
  let alive=true;const controller=new AbortController();setChooserLoading(true);
  Promise.all([api<ItemPage>(url(`/catalog/items?page=${bulk.page}&pageSize=25&search=${encodeURIComponent(bulk.search)}&status=&kind=`),'GET',undefined,{signal:controller.signal}),api<ItemOptions>(url('/catalog/item-options'),'GET',undefined,{signal:controller.signal})]).then(([data,references])=>{if(alive){setChooser(data);setChooserReferences(references);}}).catch(e=>{if(alive){setChooser({items:[],total:0,page:1,pageSize:25});setChooserReferences(null);fail(e);}}).finally(()=>{if(alive)setChooserLoading(false);});
  return()=>{alive=false;controller.abort();};
 },[key,!!bulk,bulk?.search,bulk?.page,canBulk,itemId]);
 async function open(row?:CatalogCompanyRow,readonly=false){
  if(disabled||lock.current)return;lock.current=true;setBusy(true);setError('');setNotice('');const startKey=key;
  try{
   const id=itemId??(row?companyItemId(row):'');if(!id)return;
   const [refs,meta]=await Promise.all([api<CatalogCompanyContext>(url('/catalog/item-companies/item-options/'+encodeURIComponent(id))),api<{items:CatalogCompanyOption[]}>(url('/catalog/item-companies/options'))]);
   if(!live.current||keyRef.current!==startKey)return;setOptions(meta.items);setContext(refs);
   const companyId=row?.company_id??meta.items.find(o=>o.is_enabled&&o.permissions.includes('create')&&o.permissions.includes('read')&&!result.items.some(r=>r.company_id===o.id))?.id??'';
   if(!companyId)return;
   const actual=row?await api<CatalogCompanyRow>(url(companyItemPath(companyId,id))):null;
   if(!live.current||keyRef.current!==startKey)return;setCurrent(actual);
   change({editor:{itemId:id,companyId,version:actual?.version??0,values:actual?catalogCompanyValues(actual):catalogCompanyInitial(refs),readonly:readonly||!companyAuthority(meta.items,companyId,actual?'update':'create')}});
  }catch(e){if(live.current&&keyRef.current===startKey)fail(e);}finally{lock.current=false;if(live.current)setBusy(false);}
 }
 function field(name:keyof CatalogCompanyEditor['values'],value:unknown){if(!editor||!writable||disabled||restricted&&name!=='is_enabled'||restricted&&value===true)return;change({editor:{...editor,values:{...editor.values,[name]:value}}});}
 async function mutate(path:string,method:string,body:unknown,itemIds:string[],companyIds:string[]){
  if(disabled||lock.current)return;lock.current=true;setBusy(true);setError('');setNotice('');let started=false,accepted=false;const startKey=key;
  const marker:CatalogCompanyPending={path,method,body,itemIds,companyIds};
  try{
   const meta=await api<{items:CatalogCompanyOption[]}>(url('/catalog/item-companies/options'));
   if(!live.current||keyRef.current!==startKey)return;setOptions(meta.items);
   const action=method==='PATCH'?'update':'create';
   if(!companyIds.every(id=>companyAuthority(meta.items,id,action)&&companyAuthority(meta.items,id,'read')))throw new ApiError('forbidden',403);
   guard(marker);started=true;
   const saved=await api<{created?:number;unchanged?:number}>(url(path),method,body);accepted=true;
   if(!live.current||keyRef.current!==startKey)return;guard({...marker,committed:true});
   await Promise.all(companyIds.flatMap(cid=>itemIds.map(iid=>api<CatalogCompanyRow>(url(companyItemPath(cid,iid))))));
   if(!live.current||keyRef.current!==startKey)return;
   guard(null);change({editor:null,bulk:null});setContext(null);setCurrent(null);setRevision(v=>v+1);
   if(method==='POST')setNotice(t('bulkResult',{created:saved.created??0,unchanged:saved.unchanged??0}));
  }catch(e){
   if(live.current&&keyRef.current===startKey){if(started&&!accepted&&!catalogUncertain(e as ApiError)){guard(null);if(e instanceof ApiError&&(e.status===409||e.code==='stale_version')){const old=stateRef.current.editor;if(old){change({editor:{...old,blocked:true}});try{setCurrent(await api<CatalogCompanyRow>(url(companyItemPath(old.companyId,old.itemId))));}catch{/* Conservare la bozza e il token, senza retry. */}}}}fail(e);}
  }finally{lock.current=false;if(live.current&&keyRef.current===startKey)setBusy(false);}
 }
 async function save(event:{preventDefault:()=>void;stopPropagation:()=>void}){event.preventDefault();event.stopPropagation();if(!editor||!writable||disabled||restricted&&(!editor.version||editor.values.is_enabled))return;await mutate(companyItemPath(editor.companyId,editor.itemId),editor.version?'PATCH':'PUT',{values:catalogCompanyValues(editor.values),expectedVersion:editor.version},[editor.itemId],[editor.companyId]);}
 async function saveBulk(event:{preventDefault:()=>void;stopPropagation:()=>void}){event.preventDefault();event.stopPropagation();if(!bulk||bulkDisabled||!canBulk||!bulk.itemIds.length||!bulk.companyIds.length||bulkTooLarge)return;await mutate('/catalog/item-companies/bulk-enable','POST',{itemIds:bulk.itemIds,companyIds:bulk.companyIds},bulk.itemIds,bulk.companyIds);}
 async function reviewPending(){
  if(!pending||busy||lock.current)return;lock.current=true;setBusy(true);setError('');setReview(null);const startKey=key;
  try{const rows=await Promise.all(pending.companyIds.flatMap(cid=>pending.itemIds.map(async iid=>{try{return await api<CatalogCompanyRow>(url(companyItemPath(cid,iid)));}catch(e){if(e instanceof ApiError&&e.status===404)return null;throw e;}})));if(live.current&&keyRef.current===startKey)setReview(rows.filter((r):r is CatalogCompanyRow=>r!==null));}catch(e){if(live.current&&keyRef.current===startKey)fail(e);}finally{lock.current=false;if(live.current)setBusy(false);}
 }
 function selectControl(id:string,label:string,value:string,choices:{value:string;label:string;disabled?:boolean}[],update:(v:string)=>void,blocked=false,title?:string){const entries=choices.some(o=>o.value===value)?choices:[...choices,{value,label:t('unavailableUnit'),disabled:true}];return <div className="space-y-2 min-w-0" title={title}><Label htmlFor={id}>{label}</Label><Select value={value} disabled={blocked} onValueChange={update}><SelectTrigger id={id} className="w-full"><SelectValue/></SelectTrigger><SelectContent>{entries.map(o=><SelectItem key={o.value} value={o.value} disabled={o.disabled}>{o.label}</SelectItem>)}</SelectContent></Select></div>;}
 function capabilityIcon(value:boolean){const label=c(value?'yes':'no');return <span role="img" aria-label={label} title={label} className={value?'inline-flex text-green-600':'inline-flex text-red-600'}>{value?<Check size={18} aria-hidden="true"/>:<X size={18} aria-hidden="true"/>}</span>;}
 function effective(row:CatalogCompanyRow){return <div className="flex flex-wrap gap-1">{(['canSell','canPurchase','canTrackStock'] as const).map(name=><Badge key={name} variant={row[name]?'default':'secondary'}>{t(name)}: {c(row[name]?'yes':'no')}</Badge>)}</div>;}
 function selectBulk(kind:'company'|'item',ids:string[],checked:boolean){if(!bulk||bulkDisabled)return;const field=kind==='company'?'companyIds':'itemIds';change({bulk:{...bulk,[field]:checked?[...new Set([...bulk[field],...ids])]:bulk[field].filter(id=>!ids.includes(id))}});}
 function pageCheckbox(kind:'company'|'item',ids:string[],selected:string[]){const count=ids.filter(id=>selected.includes(id)).length;return <Checkbox id={'catalog-bulk-'+kind+'-all'} aria-label={t(kind==='company'?'selectPageCompanies':'selectPageItems')} checked={count===0?false:count===ids.length?true:'indeterminate'} disabled={bulkDisabled||!ids.length} onCheckedChange={v=>selectBulk(kind,ids,v===true)}/>;}
 function startBulk(){if(disabled||!canBulk)return;change({bulk:{itemIds:itemId?[itemId]:[],companyIds:creatable[0]?[creatable[0].id]:[],search:'',page:1,companyPage:1}});setError('');}
 if(!accessible)return null;
 const actions=<div className="flex flex-wrap items-center gap-2"><Button id="catalog-company-refresh" type="button" variant="ghost" size="icon" aria-label={a('refresh')} title={a('refresh')} disabled={loading||busy} onClick={()=>{setRevision(v=>v+1);setError('');}}><RefreshCw size={16}/></Button>{itemId&&itemStatus!=='ARCHIVED'&&creatable.some(o=>!result.items.some(r=>r.company_id===o.id))&&<Button id="catalog-company-associate" type="button" variant="outline" size="sm" disabled={disabled} onClick={()=>void open()}><Plus size={16}/>{t('associate')}</Button>}{canBulk&&<Button id="catalog-company-bulk" type="button" variant="outline" size="sm" disabled={disabled} onClick={startBulk}><Plus size={16}/>{t('bulkEnable')}</Button>}</div>;
 return <div data-testid={itemId?'catalog-item-companies':'company-catalog-items'} data-catalog-companies={itemId?'item':'list'}>
  {renderToolbar?renderToolbar(actions):<div className="flex flex-wrap items-center justify-between gap-3 mb-3">{heading??<h3 className="font-semibold">{t(itemId?'companies':'title')}</h3>}{actions}</div>}
  {error&&<Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}{notice&&<p role="status">{notice}</p>}
  {pending&&<Alert><AlertDescription><p>{c('uncertain')}</p><Button id="catalog-company-review" type="button" variant="outline" disabled={busy} onClick={()=>void reviewPending()}>{c('review')}</Button>{review!==null&&<><div className="space-y-2 my-2">{review.length?review.map(row=><div key={row.id}>{row.company_name} · {row.item_code} · <Badge variant={row.is_enabled?'default':'secondary'}>{t(row.is_enabled?'ENABLED':'DISABLED')}</Badge>{effective(row)}</div>):<p>{t('noAssociations')}</p>}</div><Button id="catalog-company-acknowledge" type="button" variant="outline" disabled={busy} onClick={()=>{guard(null);change({editor:null,bulk:null});setReview(null);setRevision(v=>v+1);}}>{c('acknowledge')}</Button></>}</AlertDescription></Alert>}
  <Card className="gap-0 overflow-hidden py-0">
   {!itemId&&<FilterBar id="company-catalog-filters" expanded={state.filtersExpanded??false} onExpandedChange={filtersExpanded=>change({filtersExpanded})} fields={[
    {key:'search',minWidth:200,grow:true,content:<div className="space-y-2 min-w-0"><Label htmlFor="company-catalog-search">{a('search')}</Label><Input id="company-catalog-search" maxLength={200} value={state.search} onChange={e=>change({search:e.target.value,page:1})}/></div>},
    {key:'company',minWidth:180,content:selectControl('company-catalog-company',t('company'),state.companyId||'ALL',[{value:'ALL',label:t('allCompanies')},...options.filter(o=>o.permissions.includes('read')).map(o=>({value:o.id,label:o.name}))],v=>change({companyId:v==='ALL'?'':v,page:1}),loading||busy)},
    {key:'enabled',minWidth:130,content:selectControl('company-catalog-enabled',t('filterEnabled'),state.enabled,['ALL','ENABLED','DISABLED'].map(value=>({value,label:t(value)})),v=>change({enabled:v as CatalogCompanyState['enabled'],page:1}),false,t('enabled'))},
    ...catalogCompanyCapabilities.map(name=>({key:name,minWidth:128,content:selectControl('company-catalog-'+name,t('filter'+name[0].toUpperCase()+name.slice(1)),state[name],['ALL','YES','NO'].map(value=>({value,label:value==='ALL'?t('ALL'):c(value==='YES'?'yes':'no')})),v=>change({[name]:v as CatalogCompanyCapabilityFilter,page:1}),false,t(name))}))
   ]}/>}
   <div className="table-scroll" aria-busy={loading}><Table id="company-catalog-table"><TableHeader><TableRow><TableHead>{t('company')}</TableHead>{!itemId&&<><TableHead>{t('item')}</TableHead><TableHead kind="status">{t('itemStatus')}</TableHead></>}<TableHead kind="status">{t('enabled')}</TableHead>{catalogCompanyCapabilities.map(name=><TableHead key={name} kind="status">{t(name)}</TableHead>)}<TableHead kind="actions" className="w-24 min-w-24 max-w-24">{a('actions')}</TableHead></TableRow></TableHeader><TableBody>{!result.items.length&&<TableRow><TableCell colSpan={itemId?6:8}>{a(loading?'loading':'empty')}</TableCell></TableRow>}{result.items.map(row=><TableRow key={row.id} data-company-id={row.company_id} data-item-id={companyItemId(row)||itemId}><TableCell className="whitespace-normal">{row.company_name}{!row.company_is_enabled&&<Badge variant="secondary">{a('disabled')}</Badge>}</TableCell>{!itemId&&<><TableCell className="whitespace-normal">{row.item_code} · {row.item_name}</TableCell><TableCell kind="status"><Badge variant={row.item_status==='ACTIVE'?'default':'secondary'}>{t(row.item_status)}</Badge></TableCell></>}<TableCell kind="status"><Badge variant={row.is_enabled?'default':'secondary'}>{t(row.is_enabled?'ENABLED':'DISABLED')}</Badge></TableCell>{catalogCompanyCapabilities.map(name=><TableCell key={name} kind="status" data-capability={name}>{capabilityIcon(row[name])}</TableCell>)}<TableCell kind="actions" className="w-24 min-w-24 max-w-24 whitespace-nowrap">{authority(row.company_id,'read')&&<Button id={`catalog-company-view-${row.company_id}-${companyItemId(row)||itemId}`} type="button" variant="ghost" size="icon" className="size-8" aria-label={a('details')+' '+row.company_name} title={a('details')} disabled={disabled} onClick={()=>void open(row,true)}><Eye size={16}/></Button>}{authority(row.company_id,'update')&&<Button id={`catalog-company-edit-${row.company_id}-${companyItemId(row)||itemId}`} type="button" variant="ghost" size="icon" className="size-8" aria-label={a('edit')+' '+row.company_name} title={a('edit')} disabled={disabled} onClick={()=>void open(row)}><Pencil size={16}/></Button>}</TableCell></TableRow>)}</TableBody></Table></div>
   {!itemId&&<div className="flex items-center justify-end gap-3 p-3"><span>{result.total} · {state.page} / {Math.max(1,Math.ceil(result.total/25))}</span><Button id="company-catalog-previous" type="button" variant="outline" size="icon" aria-label={a('previous')} disabled={loading||state.page<=1} onClick={()=>change({page:state.page-1})}><ChevronLeft size={16}/></Button><Button id="company-catalog-next" type="button" variant="outline" size="icon" aria-label={a('next')} disabled={loading||state.page*25>=result.total} onClick={()=>change({page:state.page+1})}><ChevronRight size={16}/></Button></div>}
  </Card>
  {editor&&context&&(!pending||busy)&&<Dialog open onOpenChange={v=>{if(!v&&!busy&&!pending){change({editor:null});setContext(null);}}}><DialogContent data-testid="catalog-company-editor" className="sm:max-w-xl max-h-[85dvh] overflow-auto"><DialogHeader><DialogTitle>{t(editor.version?'configuration':'associate')}</DialogTitle><DialogDescription>{context.item.code} · {context.item.name}</DialogDescription></DialogHeader><form data-catalog-company-form className="space-y-4" onSubmit={save}>
   {error&&<p role="alert" className="text-destructive">{error}</p>}{editor.blocked&&<Alert variant="destructive"><AlertDescription>{c('stale')}{current&&<p>{t('currentVersion',{version:current.version})}</p>}</AlertDescription></Alert>}
   {editor.version?<p className="font-medium">{options.find(o=>o.id===editor.companyId)?.name}</p>:<div className="space-y-2"><Label htmlFor="catalog-company-company" required>{t('company')}</Label><Select value={editor.companyId} disabled={disabled} onValueChange={companyId=>{if(creatable.some(o=>o.id===companyId))change({editor:{...editor,companyId}});}}><SelectTrigger id="catalog-company-company" className="w-full"><SelectValue/></SelectTrigger><SelectContent>{creatable.filter(o=>!result.items.some(r=>r.company_id===o.id)).map(o=><SelectItem key={o.id} value={o.id}>{o.name}</SelectItem>)}</SelectContent></Select></div>}
   {restricted&&<p>{t('disableOnly')}</p>}
   {(['is_enabled','is_sellable','is_purchasable','track_stock'] as const).map(name=><div className="flex items-center justify-between gap-3" key={name}><Label htmlFor={'catalog-company-'+name.replaceAll('_','-')}>{t(name)}</Label><Switch id={'catalog-company-'+name.replaceAll('_','-')} checked={editor.values[name]} disabled={disabled||!writable||restricted&&(name!=='is_enabled'||!current?.is_enabled)||name==='track_stock'&&context.item.kind!=='GOOD'} onCheckedChange={v=>field(name,v)}/></div>)}
   {context.item.kind!=='GOOD'&&<p className="text-sm text-muted-foreground">{t('stockGoodsOnly')}</p>}
   {(['default_sales_uom_id','default_purchase_uom_id'] as const).map(name=>selectControl('catalog-company-'+name,t(name),editor.values[name]??'BASE',[{value:'BASE',label:`${t('baseUom')} · ${context.units.find(u=>u.id===context.item.base_uom_id)?.name??context.item.base_uom_id}`},...context.units.filter(u=>u.is_active||u.id===editor.values[name]).map(u=>({value:u.id,label:u.name+' · '+u.code}))],v=>field(name,v==='BASE'?null:v),disabled||!writable||restricted))}
   {current&&<div>{effective(current)}</div>}
   <DialogFooter><Button id="catalog-company-cancel" type="button" variant="outline" disabled={busy} onClick={()=>{change({editor:null});setContext(null);setError('');}}>{a('cancel')}</Button>{writable&&<Button id="catalog-company-save" type="submit" disabled={disabled||restricted&&(!editor.version||editor.values.is_enabled)}>{a('save')}</Button>}</DialogFooter>
  </form></DialogContent></Dialog>}
  {bulk&&canBulk&&(!pending||busy)&&<Dialog open onOpenChange={v=>{if(!v&&!busy&&!pending)change({bulk:null});}}><DialogContent data-testid="catalog-company-bulk-editor" className="sm:max-w-6xl min-w-0 max-h-[85dvh] overflow-auto"><DialogHeader><DialogTitle>{t('bulkEnable')}</DialogTitle><DialogDescription>{t('bulkDescription')}</DialogDescription></DialogHeader><form data-catalog-company-bulk-form className="min-w-0 space-y-4" onSubmit={saveBulk}>{error&&<p role="alert" className="text-destructive">{error}</p>}
   <fieldset className="min-w-0"><legend className="font-medium mb-2">{t('companies')} *</legend><div className="min-w-0 max-w-full overflow-x-auto" aria-busy={loading}><Table id="catalog-bulk-companies-table"><TableHeader><TableRow><TableHead kind="status" className="w-10 min-w-10 max-w-10">{pageCheckbox('company',visibleCompanies.map(o=>o.id),bulk.companyIds)}</TableHead><TableHead>{t('company')}</TableHead><TableHead>{t('legalAddress')}</TableHead></TableRow></TableHeader><TableBody>{!visibleCompanies.length&&<TableRow><TableCell colSpan={3}>{a(loading?'loading':'empty')}</TableCell></TableRow>}{visibleCompanies.map(o=><TableRow key={o.id}><TableCell kind="status" className="w-10 min-w-10 max-w-10"><Checkbox id={'catalog-bulk-company-'+o.id} aria-label={o.name} checked={bulk.companyIds.includes(o.id)} disabled={bulkDisabled} onCheckedChange={v=>selectBulk('company',[o.id],v===true)}/></TableCell><TableCell className="whitespace-normal">{o.name}</TableCell><TableCell className="whitespace-normal">{o.legal_address?siteAddress({...o.legal_address,id:o.id},locale):''}</TableCell></TableRow>)}</TableBody></Table></div><div className="flex items-center justify-end gap-2 mt-2"><Button id="catalog-bulk-company-previous" type="button" variant="outline" size="icon" aria-label={a('previous')} disabled={bulkDisabled||companyPage<=1} onClick={()=>change({bulk:{...bulk,companyPage:companyPage-1}})}><ChevronLeft size={16}/></Button><span>{companyPage} / {companyPages}</span><Button id="catalog-bulk-company-next" type="button" variant="outline" size="icon" aria-label={a('next')} disabled={bulkDisabled||companyPage>=companyPages} onClick={()=>change({bulk:{...bulk,companyPage:companyPage+1}})}><ChevronRight size={16}/></Button></div></fieldset>
   {!itemId&&<fieldset className="min-w-0"><legend className="font-medium mb-2">{t('items')} *</legend><Input id="catalog-bulk-search" aria-label={a('search')} value={bulk.search} maxLength={200} disabled={bulkDisabled} onChange={e=>change({bulk:{...bulk,search:e.target.value,page:1}})}/><div className="min-w-0 max-w-full overflow-x-auto py-3" aria-busy={chooserLoading}><Table id="catalog-bulk-items-table"><TableHeader><TableRow><TableHead kind="status" className="w-10 min-w-10 max-w-10">{pageCheckbox('item',visibleItems.map(row=>row.id),bulk.itemIds)}</TableHead>{catalogItemColumns.map(name=><TableHead key={name} kind={name==='status'?'status':'text'}>{name==='base_uom_id'?i('baseUnitList'):itemLabel(name)}</TableHead>)}</TableRow></TableHeader><TableBody>{!visibleItems.length&&<TableRow><TableCell colSpan={8}>{a(chooserLoading?'loading':'empty')}</TableCell></TableRow>}{visibleItems.map(row=><TableRow key={row.id}><TableCell kind="status" className="w-10 min-w-10 max-w-10"><Checkbox id={'catalog-bulk-item-'+row.id} aria-label={String(row.code)+' · '+String(row.name)} checked={bulk.itemIds.includes(row.id)} disabled={bulkDisabled} onCheckedChange={v=>selectBulk('item',[row.id],v===true)}/></TableCell>{catalogItemColumns.map(name=><TableCell key={name} kind={name==='status'?'status':'text'} className={name==='name'?'py-2 min-w-48 whitespace-normal':'py-2'}>{name==='status'?<Badge variant={row.status==='ACTIVE'?'default':'secondary'}>{itemLabel(String(row.status))}</Badge>:chooserReferences?catalogItemText(row,name,chooserReferences):'—'}</TableCell>)}</TableRow>)}</TableBody></Table></div><div className="flex items-center justify-end gap-2"><Button id="catalog-bulk-previous" type="button" variant="outline" size="icon" aria-label={a('previous')} disabled={bulkDisabled||bulk.page<=1} onClick={()=>change({bulk:{...bulk,page:bulk.page-1}})}><ChevronLeft size={16}/></Button><span>{bulk.page} / {Math.max(1,Math.ceil(chooser.total/25))}</span><Button id="catalog-bulk-next" type="button" variant="outline" size="icon" aria-label={a('next')} disabled={bulkDisabled||bulk.page*25>=chooser.total} onClick={()=>change({bulk:{...bulk,page:bulk.page+1}})}><ChevronRight size={16}/></Button></div></fieldset>}

   <p>{t('selection',{items:bulk.itemIds.length,companies:bulk.companyIds.length})}</p>{bulkTooLarge&&<p role="alert">{t('bulkLimit')}</p>}
   <DialogFooter><Button id="catalog-bulk-cancel" type="button" variant="outline" disabled={bulkDisabled} onClick={()=>change({bulk:null})}>{a('cancel')}</Button><Button id="catalog-bulk-save" type="submit" disabled={bulkDisabled||!canBulk||!bulk.companyIds.length||!bulk.itemIds.length||bulkTooLarge}>{a('save')}</Button></DialogFooter>
  </form></DialogContent></Dialog>}
 </div>;
}
