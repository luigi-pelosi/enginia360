"use client";
import {useEffect,useRef,useState,lazy,Suspense,type ReactNode} from 'react';
import {useTranslations} from 'next-intl';
import {Plus,Pencil,Eye,Trash2,RefreshCw,ChevronLeft,ChevronRight,ArrowRightLeft} from 'lucide-react';
import {Button} from '@/components/ui/button';
import {FilterBar} from '@/components/ui/filter-bar';
import {Input} from '@/components/ui/input';
import {Textarea} from '@/components/ui/textarea';
import {Label} from '@/components/ui/label';
import {Switch} from '@/components/ui/switch';
import {Card} from '@/components/ui/card';
import {Badge} from '@/components/ui/badge';
import {Alert,AlertDescription} from '@/components/ui/alert';
import {Table,TableHeader,TableBody,TableRow,TableHead,TableCell} from '@/components/ui/table';
import {Select,SelectContent,SelectItem,SelectTrigger,SelectValue} from '@/components/ui/select';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription,DialogFooter} from '@/components/ui/dialog';
import {api,ApiError} from '@/lib/api';
import {can,type Session,type Row} from '@/lib/model';
import {catalogKinds,catalogKey,readCatalog,storeCatalog,catalogUncertain,categoryPath,catalogItemColumns,catalogItemText} from '@/lib/catalog';
import type {CatalogCompanyOption} from '@/lib/catalog-companies';
import {itemManualCodeInvalid,itemManualCodePattern,itemManualCodeMaxLength,itemManualCodeError,itemCompanyDraftError,itemDefaults,itemInitial,itemEditor,itemValues,itemCreation,adoptItemChildren,itemCanChangeBase,itemCodeEditable,itemTransitions,itemUnitValues,identifierValues,physicalValues,physicalPresent,invalidPhysicalField,itemPhysicalPayload,localItemRow,type ItemState,type ItemRecord,type ItemEditor,type ItemOptions,type ItemPending,type ItemRowEditor,type ItemStatus,type ItemKind} from '@/lib/catalog-items';

const CatalogItemCompanyDrafts=lazy(()=>import('@/components/catalog-item-company-drafts').then(module=>({default:module.CatalogItemCompanyDrafts})));
const CatalogItemCompanies=lazy(()=>import('@/components/catalog-item-companies').then(module=>({default:module.CatalogItemCompanies})));
type Page={items:Row[];total:number;page:number;pageSize:number};
type Conversion={quantity:string;unroundedQuantity:string;rounded:boolean;decimalPlaces:number};
const resource='catalog-items';
const identifierTypes=['GTIN','OEM','MPN','BARCODE','LEGACY'];
const emptyOptions:ItemOptions={types:[],categories:[],units:[],brands:[],numbering:{GOOD:{mode:'AUTO'},INTANGIBLE:{mode:'AUTO'},SERVICE:{mode:'AUTO'},CHARGE:{mode:'AUTO'}}};
function restore(key:string):ItemState {
 if(typeof sessionStorage==='undefined')return {...itemDefaults};
 const saved=readCatalog<Omit<Partial<ItemState>,'filterVersion'> & {filterVersion?:number;kind?:string}>(sessionStorage,key);
 if(saved?.editor&&saved.rowEditor?.collection==='physical-data'){saved.editor={...saved.editor,physicalDraft:saved.removing?{}:saved.rowEditor.values};saved.rowEditor=null;saved.removing=false;saved.tab='physical';}
 // I vecchi stati locali non sono comandi: conservare sempre il token originale.
 if(saved?.editor?.record){const editor=saved.editor;const normalize=(value:unknown):ItemStatus=>value==='INACTIVE'||value==='DRAFT'&&!!editor.id?'SUSPENDED':value==='DRAFT'||value==='ARCHIVED'&&!editor.id?'ACTIVE':value as ItemStatus;saved.editor={...editor,record:{...editor.record,status:normalize(editor.record.status)},statusDraft:editor.statusDraft===undefined?undefined:normalize(editor.statusDraft)};}
 if(saved&&(saved.status==='DRAFT'||saved.status==='INACTIVE'))saved.status='SUSPENDED';
 if(saved&&saved.filterVersion!==1&&saved.filterVersion!==2&&saved.status==='ALL'){saved.status='ACTIVE';saved.page=1;}
 if(saved&&saved.filterVersion!==2){saved.itemTypeId='ALL';saved.page=1;}
 if(saved)saved.filterVersion=2;
 return {...itemDefaults,...saved,filterVersion:2,transition:null,search:typeof saved?.search==='string'?saved.search:'',page:Number.isSafeInteger(saved?.page)&&saved!.page!>0?saved!.page!:1,status:['ALL','ACTIVE','SUSPENDED','ARCHIVED'].includes(saved?.status??'')?saved!.status!:'ACTIVE',itemTypeId:typeof saved?.itemTypeId==='string'&&saved.itemTypeId?saved.itemTypeId:'ALL',tab:['general','identifiers','units','physical','companies'].includes(saved?.tab??'')?saved!.tab!:'general',editor:saved?.editor?.record&&typeof saved.editor.values==='object'&&typeof saved.editor.original==='object'&&Number.isSafeInteger(saved.editor.version)?saved.editor:null};
}
export function CatalogItemWorkspace({session,tenantId,scope,onError,heading,renderToolbar}:{session:Session;tenantId:string;scope:(path:string)=>string;onError:(e:unknown)=>string;heading:ReactNode;renderToolbar?:(actions:ReactNode)=>ReactNode}) {
 const t=useTranslations('catalogItems'),c=useTranslations('catalog'),a=useTranslations('app'),companies=useTranslations('catalogCompanies');
 const tenant=session.isSuperAdmin?tenantId:session.tenantId||'',key=catalogKey(session.id,tenant,resource);
 const [state,setState]=useState<ItemState>(()=>restore(key));
 const [pending,setPending]=useState<ItemPending|null>(()=>typeof sessionStorage==='undefined'?null:readCatalog(sessionStorage,key+':pending'));
 const [identity,setIdentity]=useState(session),[rows,setRows]=useState<Row[]>([]),[total,setTotal]=useState(0),[options,setOptions]=useState<ItemOptions>(emptyOptions);
 const [companyOptions,setCompanyOptions]=useState<CatalogCompanyOption[]>([]),[companyLoading,setCompanyLoading]=useState(false);
 const [busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[stale,setStale]=useState(false),[error,setError]=useState(''),[fieldError,setFieldError]=useState(''),[revision,setRevision]=useState(0);
 const [current,setCurrent]=useState<ItemRecord|null>(null),[review,setReview]=useState<unknown>(null),[reviewed,setReviewed]=useState(false),[result,setResult]=useState<Conversion|null>(null);
 const [confirmation,setConfirmation]=useState<'ACTIVE'|'ARCHIVED'|null>(null);
 const lock=useRef(false),mounted=useRef(true),checked=useRef(false),stateRef=useRef(state),contextRef=useRef(key);stateRef.current=state;contextRef.current=key;
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 useEffect(()=>{setIdentity(session);},[session]);
 const readable=!!tenant&&can(identity,resource,'read'),editor=state.editor,rowEditor=state.rowEditor;
 const writable=readable&&!!editor&&!editor.readonly&&editor.record.status!=='ARCHIVED'&&can(identity,resource,editor.id?'update':'create');
 const disabled=!writable||busy||loading||stale||!!pending;
 // Conservare i portali durante l'invio; chiuderli solo se l'esito resta da verificare.
 const dialogReady=!pending||busy;
 const childDisabled=disabled||!!rowEditor?.readonly;
 const childBaseId=editor?.id?editor.record.base_uom_id:editor?.values.base_uom_id;
 const url=(suffix='')=>scope('/catalog/items'+suffix);
 function change(next:Partial<ItemState>){setState(previous=>{const value={...previous,...next};storeCatalog(sessionStorage,key,value);return value;});}
 const transition=state.transition,removing=state.removing;
 function setTransition(transition:ItemStatus|null){change({transition});}
 function setRemoving(removing:boolean){change({removing});}
 function fail(e:unknown){const code=e instanceof ApiError?e.code:'',field=e instanceof ApiError?e.field:'';setFieldError(field??'');setError((t.has(code)?t(code):companies.has(code)?companies(code):c.has(code)?c(code):onError(e))+(field?` · ${field.split(',').map(name=>label(name)).join(', ')}`:''));}
 async function fresh(action:string){const currentSession=await api<Session>('/session');if(mounted.current)setIdentity(currentSession);if(!mounted.current||currentSession.id!==session.id||currentSession.mustChangePassword||(!currentSession.isSuperAdmin&&currentSession.tenantId!==tenant)||!can(currentSession,resource,'read')||!can(currentSession,resource,action))throw new ApiError('forbidden',403);return currentSession;}
 function guard(value:ItemPending|null){if(!storeCatalog(sessionStorage,key+':pending',value))throw new ApiError('storageUnavailable',400);setPending(value);}
 useEffect(()=>{
  if(!readable){setRows([]);setLoading(false);return;}
  let alive=true;const controller=new AbortController();setLoading(true);
  (async()=>{
   const currentSession=await api<Session>('/session','GET',undefined,{signal:controller.signal});
   if(!alive)return;setIdentity(currentSession);
   if(currentSession.id!==session.id||(!currentSession.isSuperAdmin&&currentSession.tenantId!==tenant)||!can(currentSession,resource,'read'))throw new ApiError('forbidden',403);
   const [page,refs]=await Promise.all([api<Page>(url(`?page=${state.page}&pageSize=25&search=${encodeURIComponent(state.search)}&status=${state.status==='ALL'?'':state.status}&itemTypeId=${encodeURIComponent(state.itemTypeId==='ALL'?'':state.itemTypeId)}`),'GET',undefined,{signal:controller.signal}),api<ItemOptions>(scope('/catalog/item-options'),'GET',undefined,{signal:controller.signal})]);
   if(!alive)return;setRows(page.items);setTotal(page.total);setOptions(refs);
   if(!checked.current){
    const recovered=stateRef.current.editor;
    if(recovered){
     if(!recovered.id)setStale(false);
     else if(recovered.id){const actual=await api<ItemRecord>(url('/'+encodeURIComponent(recovered.id)),'GET',undefined,{signal:controller.signal});if(alive){setStale(actual.version!==recovered.version);setCurrent(actual);}}
    }
    if(alive)checked.current=true;
   }
  })().catch(e=>{if(alive){if(stateRef.current.editor)setStale(true);fail(e);}}).finally(()=>{if(alive)setLoading(false);});
  return()=>{alive=false;controller.abort();};
 },[key,state.search,state.page,state.status,state.itemTypeId,revision,readable,scope]);
 const companyCreatable=readable&&can(identity,'catalog-item-companies','read')&&can(identity,'catalog-item-companies','create');
 useEffect(()=>{
  setCompanyOptions([]);
  if(!editor||editor.id||!companyCreatable){setCompanyLoading(false);return;}
  let alive=true;const controller=new AbortController();setCompanyLoading(true);
  api<{items:CatalogCompanyOption[]}>(scope('/catalog/item-companies/options'),'GET',undefined,{signal:controller.signal}).then(meta=>{if(alive)setCompanyOptions(meta.items);}).catch(e=>{if(alive)fail(e);}).finally(()=>{if(alive)setCompanyLoading(false);});
  return()=>{alive=false;controller.abort();};
 },[key,!!editor,editor?.id,companyCreatable,revision,scope]);
 async function open(row:Row|null,readonly=false){
  if(lock.current||pending)return;lock.current=true;setBusy(true);setError('');setFieldError('');setStale(false);
  try{await fresh(readonly?'read':row?'update':'create');const [record,refs]=await Promise.all([row?api<ItemRecord>(url('/'+encodeURIComponent(row.id))):Promise.resolve({...itemInitial(),id:'',version:0,kind:'GOOD' as const,status:'ACTIVE' as const,activated_at:null,identifiers:[],units:[],physicalData:null}),api<ItemOptions>(scope('/catalog/item-options'))]);if(mounted.current&&contextRef.current===key){const first=!row?refs.types.find(type=>type.is_active===true&&typeof type.id==='string'&&type.id.trim()!==''&&type.id!=='__none__'&&catalogKinds.some(kind=>kind===type.kind)):undefined;const initial=first?{...record,item_type_id:first.id,kind:first.kind as ItemKind}:record;setOptions(refs);setCurrent(row?record as ItemRecord:null);change({editor:{...itemEditor(initial,readonly||record.status==='ARCHIVED'),statusDraft:row?record.status:'ACTIVE'},rowEditor:null,tab:'general',conversion:null,transition:null,removing:false});}}
  catch(e){if(mounted.current)fail(e);}finally{lock.current=false;if(mounted.current)setBusy(false);}
 }
 // Ogni mutazione è inviata una sola volta. Le riletture non autorizzano mai un retry.
 async function write(path:string,method:string,body:unknown,action:string,main=false){
  const before=stateRef.current.editor;if(!before||lock.current||pending||stale||loading)return;
  lock.current=true;setBusy(true);setError('');setFieldError('');let started=false,committed=false;
  const marker:ItemPending={id:before.id,path,method,body,version:before.version};
  try{
   const authority=await fresh(action);if(contextRef.current!==key)return;
   if(main){const status=before.statusDraft??before.record.status;if(!['ACTIVE','SUSPENDED','ARCHIVED'].includes(status)||!before.id&&status==='ARCHIVED')throw new ApiError('invalid_item_status',400);if(!before.id){if(status==='ACTIVE'&&!can(authority,resource,'activate'))throw new ApiError('forbidden',403);}else if(status!==before.record.status){const statusAction=status==='ACTIVE'?'activate':status==='SUSPENDED'?'deactivate':'archive';if(!itemTransitions(before.record.status).includes(status)||!can(authority,resource,statusAction))throw new ApiError('forbidden',403);}}
   if(main&&!before.id&&before.companyDrafts?.length){
    if(!can(authority,'catalog-item-companies','read')||!can(authority,'catalog-item-companies','create'))throw new ApiError('draftCompanyUnavailable',403);
    const meta=await api<{items:CatalogCompanyOption[]}>(scope('/catalog/item-companies/options'));
    if(!mounted.current||contextRef.current!==key)return;setCompanyOptions(meta.items);
    const invalid=itemCompanyDraftError(before,options,meta.items);if(invalid){change({tab:'companies'});throw new ApiError(invalid,400);}
   }
   guard(marker);started=true;
   const saved=await api<ItemRecord>(scope(path),method,body);committed=true;guard({...marker,id:saved.id,committed:true});
   const actual=await api<ItemRecord>(url('/'+encodeURIComponent(saved.id)));
   if(!mounted.current)return;
   if(main){setConfirmation(null);change({editor:null,rowEditor:null,conversion:null,transition:null,removing:false});}
   else change({editor:adoptItemChildren(before,saved),rowEditor:null,conversion:null});
   setCurrent(actual);setStale(actual.version!==saved.version);guard(null);setTransition(null);setRemoving(false);setResult(null);setRevision(v=>v+1);
  }catch(e){
   if(started&&!committed&&!catalogUncertain(e as ApiError)){
    guard(null);
    if(e instanceof ApiError&&['stale_version','version_exhausted'].includes(e.code)){setStale(true);if(before.id)try{const actual=await api<ItemRecord>(url('/'+encodeURIComponent(before.id)));if(mounted.current)setCurrent(actual);}catch{/* La bozza resta bloccata. */}}
   }
   if(mounted.current)fail(e);
  }finally{lock.current=false;if(mounted.current)setBusy(false);}
 }
 const kind=editor?.id?editor.record.kind:(options.types.find(row=>row.id===editor?.values.item_type_id)?.kind??editor?.record.kind??'GOOD') as ItemKind;
 const mode=options.numbering?.[kind]?.mode;
 function field(name:string,value:unknown){
  if(disabled||!editor)return;setFieldError('');setError('');
  const values={...editor.values,[name]:value};let record=editor.record,companyDrafts=editor.companyDrafts;
  if(name==='item_type_id'){
   const selected=options.types.find(row=>row.id===value);if(!selected)return;
   if(editor.id&&selected.kind!==editor.record.kind)return;
   if(!editor.id){if(selected.kind!=='GOOD'&&(record.physicalData||physicalPresent(editor.physicalDraft))){setError(t('removePhysicalFirst'));return;}if(selected.kind!==record.kind&&selected.kind!=='GOOD')companyDrafts=companyDrafts?.map(row=>({...row,values:{...row.values,track_stock:false}}));record={...record,kind:selected.kind as ItemKind};if(options.numbering?.[record.kind]?.mode==='AUTO')values.code='';}
  }
  if(name==='base_uom_id'&&!itemCanChangeBase(editor))return;
  if(name==='code'&&!itemCodeEditable(editor,mode??''))return;
  change({editor:{...editor,values,record,companyDrafts}});
 }
 async function saveMain(confirmed=false){
  if(disabled||!editor||rowEditor)return;
  for(const name of ['name','item_type_id','category_id','base_uom_id'])if(!String(editor.values[name]??'').trim()){setFieldError(name);setError(t('requiredField',{field:t(name)}));change({tab:'general'});return;}
  if(itemManualCodeInvalid(editor,mode)){setFieldError('code');setError(t(itemManualCodeError));setConfirmation(null);change({tab:'general'});return;}
  if(kind==='GOOD'){const invalid=invalidPhysicalField(editor.physicalDraft??editor.record.physicalData);if(invalid){setFieldError(invalid);setError(t('invalid_physical_decimal')+' · '+t(invalid));change({tab:'physical'});return;}}
  if(!editor.id){const invalid=itemCompanyDraftError(editor,options);if(invalid){setError(companies(invalid));change({tab:'companies'});return;}}
  if(!mode){setError(t('optionsUnavailable'));return;}
  const status=editor.statusDraft??editor.record.status;
  if((status==='ACTIVE'&&(!editor.id||!editor.record.activated_at)||editor.id&&status==='ARCHIVED')&&(!confirmed||confirmation!==status)){setConfirmation(status);return;}
  await write('/catalog/items'+(editor.id?'/'+encodeURIComponent(editor.id):''),editor.id?'PUT':'POST',editor.id?{values:itemValues(editor.values),expectedVersion:editor.version,...(editor.statusDraft!==undefined&&editor.statusDraft!==editor.record.status?{status:editor.statusDraft}:{}),...itemPhysicalPayload(editor)}:{...itemCreation(editor),status:editor.statusDraft??'ACTIVE'},editor.id?'update':'create',true);
 }
 function physicalField(name:string,value:unknown){if(disabled||!editor)return;change({editor:{...editor,physicalDraft:{...(editor.physicalDraft??physicalValues(editor.record.physicalData??{})),[name]:value}}});setFieldError('');setError('');}
 function close(){if(!busy&&!pending){setConfirmation(null);change({editor:null,rowEditor:null,conversion:null,transition:null,removing:false});setStale(false);setError('');setFieldError('');}}
 function openChild(collection:ItemRowEditor['collection'],row:Row|null,readonly=false){
  if(!editor||busy||pending||stale)return;
  let values:Record<string,unknown>=row?structuredClone(row):collection==='identifiers'?{identifier_type:'GTIN',value:'',uom_id:null,is_primary:false}:collection==='units'?{uom_id:null,conversion_numerator:'1',conversion_denominator:'1',is_active:true}:physicalValues(editor.record.physicalData??{});
  if(!row&&collection==='units'&&!readonly&&writable){const base=options.units.find(u=>u.id===childBaseId);const first=options.units.find(u=>u.is_active===true&&typeof u.id==='string'&&!!u.id.trim()&&u.id!=='__none__'&&u.id!==childBaseId&&(u.conversion_scope==='ITEM'||u.dimension===base?.dimension)&&!editor.record.units.some(r=>r.uom_id===u.id));if(first)values=unitFieldValues(values,first.id);}
  change({rowEditor:{collection,id:row?.id??null,values,readonly:readonly||!writable,version:editor.version}});setError('');setFieldError('');setRemoving(false);
 }
 function unitFieldValues(values:Record<string,unknown>,value:unknown){return itemUnitValues({...values,uom_id:value},options.units.find(u=>u.id===value),options.units.find(u=>u.id===childBaseId));}
 function rowField(name:string,value:unknown){
  if(childDisabled||!rowEditor||!editor)return;let values={...rowEditor.values,[name]:value};
  if(rowEditor.collection==='units'&&name==='uom_id')values=unitFieldValues(values,value);
  change({rowEditor:{...rowEditor,values}});setError('');setFieldError('');
 }
 async function saveChild(remove=false){
  if(!editor||!rowEditor||childDisabled||lock.current)return;
  if(rowEditor.version!==editor.version){setStale(true);return;}
  if(editor.id&&editor.values.base_uom_id!==editor.record.base_uom_id){setError(t('saveBaseFirst'));setFieldError('base_uom_id');return;}
  if(!remove&&rowEditor.collection==='physical-data'){const invalid=invalidPhysicalField(rowEditor.values);if(invalid){setFieldError(invalid);setError(t('invalid_physical_decimal')+' · '+t(invalid));return;}}
  let values:Record<string,unknown>|null=rowEditor.collection==='identifiers'?identifierValues(rowEditor.values):rowEditor.collection==='units'?itemUnitValues(rowEditor.values,options.units.find(u=>u.id===rowEditor.values.uom_id),options.units.find(u=>u.id===childBaseId)):remove?null:physicalValues(rowEditor.values);
  const required=rowEditor.collection==='identifiers'?['identifier_type','value']:rowEditor.collection==='units'?['uom_id','conversion_numerator','conversion_denominator']:[];
  if(!remove)for(const name of required)if(!String(values?.[name]??'').trim()){setFieldError(name);setError(t('requiredField',{field:t(name)}));return;}
  if(!editor.id){const normalized={...rowEditor,values:values??{}};change({editor:localItemRow(editor,normalized,remove),rowEditor:null});setRemoving(false);return;}
  const path='/catalog/items/'+encodeURIComponent(editor.id)+'/'+rowEditor.collection+(rowEditor.collection!=='physical-data'&&rowEditor.id?'/'+encodeURIComponent(rowEditor.id):'');
  await write(path+(remove&&rowEditor.collection!=='physical-data'?`?expectedVersion=${rowEditor.version}`:''),rowEditor.collection==='physical-data'?'PUT':remove?'DELETE':rowEditor.id?'PUT':'POST',remove&&rowEditor.collection!=='physical-data'?undefined:{values,expectedVersion:rowEditor.version},'update');
 }
 async function reviewPending(){if(!pending||lock.current)return;lock.current=true;setBusy(true);setError('');setReviewed(false);try{await fresh('read');let data:unknown;if(pending.id)data=await api<ItemRecord>(url('/'+encodeURIComponent(pending.id)));else {const page=await api<Page>(url('?page=1&pageSize=100&search='+encodeURIComponent(String((pending.body as {values?:Record<string,unknown>})?.values?.code||(pending.body as {values?:Record<string,unknown>})?.values?.name||''))));data={...page,items:await Promise.all(page.items.map(row=>api<ItemRecord>(url('/'+encodeURIComponent(row.id)))))};}setReview(data);setReviewed(true);}catch(e){fail(e);}finally{lock.current=false;setBusy(false);}}
 async function convert(){if(!editor?.id||!state.conversion||lock.current||pending)return;lock.current=true;setBusy(true);setResult(null);setError('');try{await fresh('read');const answer=await api<Conversion>(url('/'+encodeURIComponent(editor.id)+'/convert'),'POST',state.conversion);if(mounted.current)setResult(answer);}catch(e){fail(e);}finally{lock.current=false;setBusy(false);}}
 const label=(name:string)=>t.has(name)?t(name):c.has(name)?c(name):name;
 const id=(name:string)=>name==='item_type_id'?'item-type':name==='base_uom_id'?'item-base-uom':name==='sourceUnitId'?'item-source-unit':name==='targetUnitId'?'item-target-unit':'item-'+name.replaceAll('_','-');
 function input(name:string,values:Record<string,unknown>,update:(name:string,value:unknown)=>void,blocked:boolean,required=false,decimal=false){const manualCode=name==='code'&&!blocked&&mode==='MANUAL';return <div className="space-y-2 min-w-0" key={name}><Label htmlFor={id(name)} required={required}>{label(name)}</Label><Input id={id(name)} value={String(values[name]??'')} disabled={blocked} required={required} maxLength={manualCode?itemManualCodeMaxLength:undefined} pattern={manualCode?itemManualCodePattern:undefined} inputMode={decimal?'decimal':undefined} aria-invalid={fieldError===name} aria-describedby={fieldError===name?'item-field-error':undefined} onChange={e=>update(name,e.target.value)}/></div>;}
 function select(name:string,values:Record<string,unknown>,update:(name:string,value:unknown)=>void,choices:{value:string;label:string;disabled?:boolean}[],blocked:boolean,required=false){
  const selected=String(values[name]??'__none__');const items=[...choices];if(selected!=='__none__'&&!items.some(o=>o.value===selected))items.push({value:selected,label:selected,disabled:true});
  return <div className="space-y-2 min-w-0" key={name}><Label htmlFor={id(name)} required={required}>{label(name)}</Label><Select value={selected} disabled={blocked} required={required} onValueChange={value=>update(name,value==='__none__'?null:value)}><SelectTrigger id={id(name)} className="w-full" aria-invalid={fieldError===name} aria-describedby={fieldError===name?'item-field-error':undefined}><SelectValue/></SelectTrigger><SelectContent><SelectItem value="__none__">{t('none')}</SelectItem>{items.map(o=><SelectItem key={o.value} value={o.value} disabled={o.disabled}>{o.label}</SelectItem>)}</SelectContent></Select></div>;
 }
 function toggle(name:string,values:Record<string,unknown>,update:(name:string,value:unknown)=>void,blocked:boolean){return <div className="flex items-center justify-between gap-3"><Label htmlFor={id(name)}>{label(name)}</Label><Switch id={id(name)} checked={!!values[name]} disabled={blocked} onCheckedChange={value=>update(name,value)}/></div>;}
 const refs=(list:Row[],selected:unknown)=>list.filter(r=>r.is_active||r.id===selected).map(r=>({value:r.id,label:String(r.name)+(r.code?` (${r.code})`:''),disabled:!r.is_active&&r.id!==selected}));
 const unitLabel=(unitId:unknown)=>options.units.find(u=>u.id===unitId)?.name??unitId??t('baseUnit');
 const icon=(text:string,Icon:typeof Eye,fn:()=>void,blocked=false)=><Button type="button" variant="ghost" size="icon" aria-label={text} title={text} disabled={busy||loading||!!pending||blocked} onClick={fn}><Icon size={16}/></Button>;
 const base=options.units.find(u=>u.id===childBaseId);
 const associated=options.units.filter(u=>u.id===childBaseId||editor?.record.units.some(row=>row.uom_id===u.id&&row.is_active));
 function summary(value:unknown):ReactNode {
  if(!value||typeof value!=='object')return null;const list=Array.isArray((value as Page).items)?(value as Page).items:[value as Row];
  return <div className="max-h-64 overflow-auto space-y-2">{!list.length?<p>{c('empty')}</p>:list.map((row,i)=><dl className="grid grid-cols-2 gap-2 border rounded p-2 text-sm" key={i}>{['name','code','kind','status','version','item_type_id','category_id','base_uom_id','brand_id'].filter(name=>Object.hasOwn(row,name)).map(name=><div className="contents" key={name}><dt>{label(name)}</dt><dd className="break-all">{name==='kind'?label(String(row.kind)):name==='status'?<Badge variant={row.status==='ACTIVE'?'default':'secondary'}>{label(String(row.status))}</Badge>:name==='item_type_id'?options.types.find(r=>r.id===row[name])?.name as ReactNode??String(row[name]??'—'):name==='category_id'?categoryPath(options.categories,String(row[name]??''))||'—':name==='base_uom_id'?String(unitLabel(row[name])):name==='brand_id'?String(options.brands.find(r=>r.id===row[name])?.name??'—'):String(row[name]??'—')}</dd></div>)}{'identifiers' in row&&<><dt>{t('identifiers')}</dt><dd>{(row.identifiers as Row[]).map(r=>`${r.identifier_type}: ${r.value} · ${unitLabel(r.uom_id)} · ${t('is_primary')}: ${c(r.is_primary?'yes':'no')}`).join(', ')||'—'}</dd><dt>{t('units')}</dt><dd>{(row.units as Row[]).map(r=>`${unitLabel(r.uom_id)} ${r.conversion_numerator}/${r.conversion_denominator} · ${c(r.is_active?'active':'inactive')}`).join(', ')||'—'}</dd>{row.kind==='GOOD'&&<><dt>{t('physical')}</dt><dd>{row.physicalData?Object.entries(physicalValues(row.physicalData as Record<string,unknown>)).map(([name,value])=>`${label(name)}: ${name.endsWith('uom_id')?(value?unitLabel(value):'—'):value??'—'}`).join(' · '):'—'}</dd></>}</>}</dl>)}</div>;
 }
 const tabs=['general','identifiers','units',...(kind==='GOOD'?['physical']:[]),...((editor?.id?['read','create','update'].some(action=>can(identity,'catalog-item-companies',action)):can(identity,'catalog-item-companies','read')&&can(identity,'catalog-item-companies','create'))?['companies']:[])];
 const values=editor?.values??{};
 const statusChoices:ItemStatus[]=!editor?.id?['ACTIVE','SUSPENDED']:[editor.record.status,...itemTransitions(editor.record.status).filter(status=>can(identity,resource,status==='ACTIVE'?'activate':status==='SUSPENDED'?'deactivate':'archive'))];
 const statusOptions=editor?.id&&editor.statusDraft&&!statusChoices.includes(editor.statusDraft)?[...statusChoices,editor.statusDraft]:statusChoices;
 const newAction=readable&&can(identity,resource,'create')&&<Button id="catalog-item-new" disabled={busy||loading||!!pending} onClick={()=>void open(null)}><Plus size={16}/>{a('new')}</Button>;
 return <div data-catalog-workspace="catalog-items">
  {renderToolbar?renderToolbar(<>{icon(a('refresh'),RefreshCw,()=>setRevision(v=>v+1))}{newAction}</>):<div className="page-heading mb-4">{heading}{newAction}</div>}
  {error&&(!editor||!!pending)&&<Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
  {pending&&<Alert className="mb-4"><AlertDescription><p>{c('uncertain')}</p><div className="flex flex-wrap gap-2 mt-2"><Button id="item-review" disabled={busy||!readable} variant="outline" onClick={()=>void reviewPending()}>{c('review')}</Button>{reviewed&&<Button id="item-acknowledge" disabled={busy} variant="outline" onClick={()=>{guard(null);change({editor:null,rowEditor:null,conversion:null,transition:null,removing:false});setStale(false);setReview(null);setReviewed(false);setRevision(v=>v+1);}}>{c('acknowledge')}</Button>}</div>{review!==null&&summary(review)}</AlertDescription></Alert>}
  {!readable?<p>{a('noAccess')}</p>:<Card className="gap-0 overflow-hidden py-0"><div className="flex items-start gap-2 border-b"><div className="min-w-0 flex-1"><FilterBar id="catalog-item-filters" expanded={state.filtersExpanded===true} onExpandedChange={filtersExpanded=>change({filtersExpanded})} fields={[
    {key:'search',minWidth:200,grow:true,content:<Input id="catalog-item-search" aria-label={a('search')} placeholder={a('search')} value={state.search} onChange={e=>change({search:e.target.value,page:1})}/>},
    {key:'status',minWidth:130,content:<Select value={state.status} onValueChange={value=>change({status:value,page:1})}><SelectTrigger id="catalog-item-filter-status" className="w-full" aria-label={t('status')}><SelectValue/></SelectTrigger><SelectContent>{['ALL','ACTIVE','SUSPENDED','ARCHIVED'].map(value=><SelectItem value={value} key={value}>{label(value)}</SelectItem>)}</SelectContent></Select>},
    {key:'itemTypeId',minWidth:180,content:<Select value={state.itemTypeId} onValueChange={value=>change({itemTypeId:value,page:1})}><SelectTrigger id="catalog-item-filter-itemTypeId" className="w-full" aria-label={t('item_type_id')}><SelectValue/></SelectTrigger><SelectContent><SelectItem value="ALL">{label('ALL')}</SelectItem>{options.types.filter(type=>typeof type.id==='string'&&!!type.id&&type.id!=='ALL').map(type=><SelectItem value={String(type.id)} key={String(type.id)}>{String(type.name)}</SelectItem>)}</SelectContent></Select>}
   ]}/></div>{!renderToolbar&&<div className="py-3 pr-3">{icon(a('refresh'),RefreshCw,()=>setRevision(v=>v+1))}</div>}</div>
   <Table id="catalog-item-table" className="w-full text-sm"><TableHeader><TableRow>{catalogItemColumns.map(name=><TableHead kind={name==='status'?'status':'text'} key={name}>{name==='base_uom_id'?t('baseUnitList'):label(name)}</TableHead>)}<TableHead kind="actions" className="w-28 min-w-28 max-w-28">{a('actions')}</TableHead></TableRow></TableHeader><TableBody>{loading?<TableRow><TableCell colSpan={8}>{a('loading')}</TableCell></TableRow>:!rows.length?<TableRow><TableCell colSpan={8}>{c('empty')}</TableCell></TableRow>:rows.map(row=><TableRow key={row.id} data-record-id={row.id}>{catalogItemColumns.map(name=><TableCell kind={name==='status'?'status':'text'} className={name==='name'?'py-2 min-w-48 whitespace-normal':'py-2'} key={name}>{name==='status'?<Badge variant={row.status==='ACTIVE'?'default':'secondary'}>{label(String(row.status))}</Badge>:catalogItemText(row,name,options)}</TableCell>)}<TableCell kind="actions" className="w-28 min-w-28 max-w-28 py-1 whitespace-nowrap">{icon(a('details')+' '+row.name,Eye,()=>void open(row,true))}{can(identity,resource,'update')&&row.status!=='ARCHIVED'&&icon(a('edit')+' '+row.name,Pencil,()=>void open(row))}</TableCell></TableRow>)}</TableBody></Table><div className="flex justify-end items-center gap-3 p-3"><span className="table-count">{total} {a('records',{count:total})}</span><Button variant="outline" size="icon" aria-label={c('previous')} disabled={loading||state.page<=1} onClick={()=>change({page:state.page-1})}><ChevronLeft size={16}/></Button><span>{state.page} / {Math.max(1,Math.ceil(total/25))}</span><Button variant="outline" size="icon" aria-label={c('next')} disabled={loading||state.page*25>=total} onClick={()=>change({page:state.page+1})}><ChevronRight size={16}/></Button></div>
  </Card>}
  <Dialog open={!!editor&&readable&&dialogReady} onOpenChange={open=>{if(!open&&!rowEditor&&!transition&&!confirmation)close();}}><DialogContent data-testid="catalog-item-editor" showCloseButton={!busy} className="sm:max-w-4xl max-h-[90dvh] overflow-auto min-w-0"><DialogHeader><DialogTitle>{editor?.readonly?a('details'):editor?.id?a('edit'):a('new')} · {t('title')}</DialogTitle><DialogDescription className="sr-only">{t('title')}</DialogDescription></DialogHeader>
   {error&&!rowEditor&&<p id="item-field-error" role="alert" className="text-destructive">{error}</p>}{stale&&<Alert variant="destructive"><AlertDescription><p>{c('stale')}</p><p className="font-medium">{c('original')}</p>{summary(editor?.original)}{current&&<><p className="font-medium">{c('current')}</p>{summary(current)}</>}<Button variant="outline" disabled={busy} onClick={close}>{c('discardReload')}</Button></AlertDescription></Alert>}
   <div role="tablist" aria-label={t('title')} className="flex flex-wrap gap-2 border-b pb-2">{tabs.map(tab=><Button key={tab} type="button" variant={state.tab===tab?'default':'ghost'} role="tab" id={'item-tab-'+tab} data-testid={'item-tab-'+tab} aria-selected={state.tab===tab} aria-controls={'item-panel-'+tab} disabled={busy||!!rowEditor} onClick={()=>change({tab:tab as ItemState['tab']})}>{tab==='companies'?companies('companies'):t(tab)}</Button>)}</div>
   {state.tab==='companies'&&editor?.id&&<div role="tabpanel" id="item-panel-companies" aria-labelledby="item-tab-companies"><Suspense fallback={<p>{a('loading')}</p>}><CatalogItemCompanies key={`${key}:companies:${editor.id}`} itemId={editor.id} itemStatus={editor.record.status} session={identity} tenantId={tenant} scope={scope} onError={onError}/></Suspense></div>}
   {state.tab==='companies'&&editor&&!editor.id&&<div role="tabpanel" id="item-panel-companies" aria-labelledby="item-tab-companies"><Suspense fallback={<p>{a('loading')}</p>}><CatalogItemCompanyDrafts companyDrafts={editor.companyDrafts??[]} companyOptions={companyOptions} types={options.types} units={options.units} record={editor.record} selectedTypeId={editor.values.item_type_id} kind={kind} baseId={editor.values.base_uom_id} disabled={disabled} loading={companyLoading} onChange={companyDrafts=>{if(!disabled)change({editor:{...editor,companyDrafts}});}}/></Suspense></div>}
   <form noValidate onSubmit={e=>{e.preventDefault();e.stopPropagation();void saveMain();}} className="space-y-5 min-w-0">
   <div role={state.tab==='companies'?undefined:'tabpanel'} id={state.tab==='companies'?undefined:'item-panel-'+state.tab} aria-labelledby={state.tab==='companies'?undefined:'item-tab-'+state.tab} className="min-w-0">
    {state.tab==='general'&&<div className="grid gap-4 sm:grid-cols-2">{input('name',values,field,disabled,true)}{select('item_type_id',values,field,refs(options.types.filter(row=>!editor?.id||row.kind===editor.record.kind),values.item_type_id),disabled,true)}{(mode==='MANUAL'||!!values.code)&&input('code',values,field,disabled||!editor||!itemCodeEditable(editor,mode??''),mode==='MANUAL')}{select('category_id',values,field,refs(options.categories,values.category_id).map(row=>({...row,label:categoryPath(options.categories,row.value)})),disabled,true)}{select('base_uom_id',values,field,refs(options.units.filter(row=>row.conversion_scope==='UNIVERSAL'),values.base_uom_id),disabled||!!editor&&!itemCanChangeBase(editor),true)}{select('brand_id',values,field,refs(options.brands,values.brand_id),disabled)}<div className="space-y-2 sm:col-span-2"><Label htmlFor="item-description">{t('description')}</Label><Textarea id="item-description" disabled={disabled} value={String(values.description??'')} onChange={e=>field('description',e.target.value)}/></div><div className="space-y-2"><Label htmlFor="item-status">{t('status')}</Label><Select value={editor?.statusDraft??editor?.record.status??'ACTIVE'} disabled={disabled} onValueChange={value=>{if(!editor||disabled)return;const status=value as ItemStatus;if(!statusChoices.includes(status))return;change({editor:{...editor,statusDraft:status}});setError('');setFieldError('');}}><SelectTrigger id="item-status" className="w-full"><SelectValue/></SelectTrigger><SelectContent>{statusOptions.map(status=><SelectItem key={status} value={status} disabled={!statusChoices.includes(status)}>{label(status)}</SelectItem>)}</SelectContent></Select></div></div>}
    {(state.tab==='identifiers'||state.tab==='units')&&<div className="min-w-0 space-y-2"><div className="flex justify-end gap-2">{state.tab==='units'&&editor?.id&&icon(c('convert'),ArrowRightLeft,()=>{change({conversion:{sourceUnitId:String(childBaseId??''),targetUnitId:associated.find(u=>u.is_active===true&&typeof u.id==='string'&&!!u.id.trim()&&u.id!=='__none__'&&u.id!==childBaseId)?.id??'',quantity:'1'}});setResult(null);},!childBaseId)}{writable&&<Button id={'item-add-'+state.tab} type="button" variant="outline" size="sm" disabled={disabled||state.tab==='units'&&!childBaseId} onClick={()=>openChild(state.tab as 'identifiers'|'units',null)}><Plus size={16}/>{a('new')}</Button>}</div><Table id={'item-'+state.tab+'-table'} className="w-full text-sm"><TableHeader><TableRow>{(state.tab==='identifiers'?['identifier_type','value','uom_id','is_primary']:['uom_id','conversion_numerator','conversion_denominator','is_active']).map(name=><TableHead kind={name==='status'||name==='is_primary'||name==='is_active'?'status':name==='conversion_numerator'||name==='conversion_denominator'?'number':'text'} key={name}>{label(name)}</TableHead>)}<TableHead kind="actions" className="w-32 min-w-32 max-w-32">{a('actions')}</TableHead></TableRow></TableHeader><TableBody>{!editor?.record[state.tab].length?<TableRow><TableCell colSpan={6}>{c('empty')}</TableCell></TableRow>:editor.record[state.tab].map(row=><TableRow data-record-id={row.id} key={row.id}>{(state.tab==='identifiers'?['identifier_type','value','uom_id','is_primary']:['uom_id','conversion_numerator','conversion_denominator','is_active']).map(name=><TableCell kind={name==='status'||name==='is_primary'||name==='is_active'?'status':name==='conversion_numerator'||name==='conversion_denominator'?'number':'text'} className="py-2" key={name}>{name==='uom_id'?String(unitLabel(row[name])):typeof row[name]==='boolean'?c(row[name]?'yes':'no'):String(row[name]??'—')}</TableCell>)}<TableCell kind="actions" className="w-32 min-w-32 max-w-32 py-1 whitespace-nowrap">{icon(a('details')+' '+String(row.value??unitLabel(row.uom_id)),Eye,()=>openChild(state.tab as 'identifiers'|'units',row,true))}{writable&&<>{icon(a('edit')+' '+String(row.value??unitLabel(row.uom_id)),Pencil,()=>openChild(state.tab as 'identifiers'|'units',row),disabled)}{icon(a('delete')+' '+String(row.value??unitLabel(row.uom_id)),Trash2,()=>{openChild(state.tab as 'identifiers'|'units',row);setRemoving(true);},disabled)}</>}</TableCell></TableRow>)}</TableBody></Table></div>}
    {state.tab==='physical'&&kind==='GOOD'&&<div className="grid gap-4">{(()=>{const physical=editor?.physicalDraft??physicalValues(editor?.record.physicalData??{});return <><div className="grid gap-4 sm:grid-cols-3">{['net_weight','gross_weight'].map(name=>input(name,physical,physicalField,disabled,false,true))}{select('weight_uom_id',physical,physicalField,refs(options.units.filter(u=>u.conversion_scope==='UNIVERSAL'&&u.dimension==='MASS'),physical.weight_uom_id),disabled)}</div><div className="grid gap-4 sm:grid-cols-[repeat(3,minmax(0,1fr))_calc((100%_-_2rem)/3)]">{['length','width','height'].map(name=>input(name,physical,physicalField,disabled,false,true))}{select('dimension_uom_id',physical,physicalField,refs(options.units.filter(u=>u.conversion_scope==='UNIVERSAL'&&u.dimension==='LENGTH'),physical.dimension_uom_id),disabled)}</div></>;})()}</div>}
   </div>
   <DialogFooter className="flex-wrap"><Button id="item-cancel" type="button" variant="outline" disabled={busy||!!rowEditor} onClick={close}>{a('cancel')}</Button>{!editor?.readonly&&editor?.record.status!=='ARCHIVED'&&can(identity,resource,editor?.id?'update':'create')&&<Button id="item-save" type="submit" disabled={disabled||!!rowEditor}>{busy?a('loading'):a('save')}</Button>}</DialogFooter>
   </form>
  </DialogContent></Dialog>
  {confirmation&&<Dialog open={!!editor&&readable&&dialogReady} onOpenChange={open=>{if(!open&&!busy)setConfirmation(null);}}><DialogContent data-testid={`catalog-item-${confirmation==='ACTIVE'?'activation':'archive'}-confirm`} showCloseButton={!busy}><DialogHeader><DialogTitle>{t(confirmation==='ACTIVE'?'activationConfirmation':'archive')}</DialogTitle><DialogDescription>{t(confirmation==='ACTIVE'?'confirmActivate':'confirmArchive')}</DialogDescription></DialogHeader>{error&&<p role="alert" className="text-destructive">{error}</p>}<DialogFooter><Button id={`item-${confirmation==='ACTIVE'?'activation':'archive'}-cancel`} type="button" variant="outline" disabled={busy} onClick={()=>setConfirmation(null)}>{a('cancel')}</Button><Button id={`item-${confirmation==='ACTIVE'?'activation':'archive'}-confirm`} type="button" variant={confirmation==='ACTIVE'?'default':'destructive'} disabled={disabled} onClick={()=>void saveMain(true)}>{busy?a('loading'):t(confirmation==='ACTIVE'?'confirmSave':'archive')}</Button></DialogFooter></DialogContent></Dialog>}
  <Dialog open={!!rowEditor&&!!editor&&readable&&dialogReady} onOpenChange={open=>{if(!open&&!busy){change({rowEditor:null});setRemoving(false);setError('');}}}><DialogContent data-testid="catalog-item-row-editor" showCloseButton={!busy} className="sm:max-w-xl max-h-[90dvh] overflow-auto"><DialogHeader><DialogTitle>{removing?a('delete'):rowEditor?.readonly?a('details'):rowEditor?.id?a('edit'):a('new')} · {label(rowEditor?.collection??'identifiers')}</DialogTitle><DialogDescription className={removing?'':'sr-only'}>{removing?t('confirmDelete'):label(rowEditor?.collection??'identifiers')}</DialogDescription></DialogHeader>
   {error&&<p id="item-field-error" role="alert" className="text-destructive">{error}</p>}{stale&&<p role="alert" className="text-destructive">{c('stale')}</p>}
   <form onSubmit={e=>{e.preventDefault();e.stopPropagation();void saveChild(removing);}} className="space-y-4"><div className="grid gap-4 sm:grid-cols-2">
    {!removing&&rowEditor?.collection==='identifiers'&&<>{select('identifier_type',rowEditor.values,rowField,identifierTypes.map(value=>({value,label:value})),childDisabled,true)}{input('value',rowEditor.values,rowField,childDisabled,true)}{select('uom_id',rowEditor.values,rowField,refs(associated,rowEditor.values.uom_id),childDisabled)}{toggle('is_primary',rowEditor.values,rowField,childDisabled)}</>}
    {!removing&&rowEditor?.collection==='units'&&<>{select('uom_id',rowEditor.values,rowField,refs(options.units.filter(u=>u.id!==childBaseId&&(u.conversion_scope==='ITEM'||u.dimension===base?.dimension)&&(!editor?.record.units.some(row=>row.uom_id===u.id&&row.id!==rowEditor.id)||u.id===rowEditor.values.uom_id)),rowEditor.values.uom_id),childDisabled,true)}{input('conversion_numerator',rowEditor.values,rowField,childDisabled||options.units.find(u=>u.id===rowEditor.values.uom_id)?.conversion_scope==='UNIVERSAL',true,true)}{input('conversion_denominator',rowEditor.values,rowField,childDisabled||options.units.find(u=>u.id===rowEditor.values.uom_id)?.conversion_scope==='UNIVERSAL',true,true)}{toggle('is_active',rowEditor.values,rowField,childDisabled)}</>}
    {!removing&&rowEditor?.collection==='physical-data'&&<>{['net_weight','gross_weight'].map(name=>input(name,rowEditor.values,rowField,childDisabled,false,true))}{select('weight_uom_id',rowEditor.values,rowField,refs(options.units.filter(u=>u.conversion_scope==='UNIVERSAL'&&u.dimension==='MASS'),rowEditor.values.weight_uom_id),childDisabled)}{['length','width','height'].map(name=>input(name,rowEditor.values,rowField,childDisabled,false,true))}{select('dimension_uom_id',rowEditor.values,rowField,refs(options.units.filter(u=>u.conversion_scope==='UNIVERSAL'&&u.dimension==='LENGTH'),rowEditor.values.dimension_uom_id),childDisabled)}</>}
   </div><DialogFooter><Button id="item-row-cancel" type="button" variant="outline" disabled={busy} onClick={()=>{change({rowEditor:null});setRemoving(false);setError('');}}>{a('cancel')}</Button>{!rowEditor?.readonly&&<Button id="item-row-save" variant={removing?'destructive':'default'} type="submit" disabled={childDisabled}>{busy?a('loading'):removing?a('delete'):a('save')}</Button>}</DialogFooter></form>
  </DialogContent></Dialog>
  <Dialog open={!!state.conversion&&readable&&dialogReady} onOpenChange={open=>{if(!open&&!busy){change({conversion:null});setResult(null);}}}><DialogContent showCloseButton={!busy}><DialogHeader><DialogTitle>{c('convert')}</DialogTitle><DialogDescription className="sr-only">{c('convert')}</DialogDescription></DialogHeader>{error&&<p role="alert" className="text-destructive">{error}</p>}<form className="space-y-4" onSubmit={e=>{e.preventDefault();e.stopPropagation();void convert();}}>{state.conversion&&<>{(['sourceUnitId','targetUnitId'] as const).map(name=>select(name,state.conversion!,(_,value)=>{change({conversion:{...state.conversion!,[name]:String(value??'')}});setResult(null);},refs(associated,state.conversion![name]),busy,true))}{input('quantity',state.conversion,(_,value)=>{change({conversion:{...state.conversion!,quantity:String(value)}});setResult(null);},busy,true,true)}</>}{result&&<div role="status" className="rounded border p-3"><p>{c('result')}: <output>{result.quantity}</output></p><p>{c('unrounded')}: {result.unroundedQuantity}</p><p>{c(result.rounded?'rounded':'exact')} · {c('decimal_places')}: {result.decimalPlaces}</p></div>}<DialogFooter><Button type="button" variant="outline" disabled={busy} onClick={()=>{change({conversion:null});setResult(null);}}>{a('close')}</Button><Button type="submit" disabled={busy||!state.conversion?.sourceUnitId||!state.conversion?.targetUnitId}>{c('convert')}</Button></DialogFooter></form></DialogContent></Dialog>
 </div>;
}
