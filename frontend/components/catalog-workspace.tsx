"use client";
import {useEffect, useRef, useState, type ReactNode} from 'react';
import {useTranslations} from 'next-intl';
import {Plus, Pencil, Eye, Trash2, ArrowRightLeft, RefreshCw, ChevronLeft, ChevronRight} from 'lucide-react';
import {Button} from '@/components/ui/button';
import {Badge} from '@/components/ui/badge';
import {FilterBar} from '@/components/ui/filter-bar';
import {Input} from '@/components/ui/input';
import {Textarea} from '@/components/ui/textarea';
import {Label} from '@/components/ui/label';
import {Switch} from '@/components/ui/switch';
import {Card} from '@/components/ui/card';
import {Alert, AlertDescription} from '@/components/ui/alert';
import {Table, TableHeader, TableBody, TableRow, TableHead, TableCell} from '@/components/ui/table';
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from '@/components/ui/select';
import {Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter} from '@/components/ui/dialog';
import {api, ApiError} from '@/lib/api';
import {can, type Session, type Row} from '@/lib/model';
import {catalogKinds, catalogKey, catalogDefaults, readCatalog, storeCatalog, resetCatalog, categoryParents, categoryPath, catalogValues, catalogInitial, catalogUncertain, type CatalogResource, type CatalogState, type CatalogEditor, type CatalogPending} from '@/lib/catalog';

type Page = {items: Row[]; total: number; page: number; pageSize: number};
type Conversion = {quantity: string; unroundedQuantity: string; rounded: boolean; decimalPlaces: number};
const dimensions = ['COUNT','MASS','LENGTH','VOLUME','TIME','AREA'];
function conversionTargets(rows:Row[], source:Row | undefined) {
  if(!source || source.is_active!==true || source.conversion_scope==='ITEM') return [];
  return rows.filter(row=>row.id!==source.id && row.is_active===true && row.conversion_scope!=='ITEM' && row.dimension===source.dimension);
}
export function resetCatalogRecovery(session: Session, tenant: string, resource: string) {
  try {resetCatalog(sessionStorage,catalogKey(session.id,session.isSuperAdmin ? tenant : session.tenantId || '',resource));} catch { /* Conservare il blocco se lo storage non è disponibile. */ }
}
function restored(key: string, resource: CatalogResource): CatalogState {
  if(typeof sessionStorage==='undefined') return {...catalogDefaults};
  const saved=readCatalog<Partial<CatalogState>>(sessionStorage,key);
  const legacy=resource==='catalog-numbering' && saved?.kindFilterVersion!==1;
  return {...catalogDefaults,...saved,kindFilterVersion:1,search:!legacy && typeof saved?.search==='string' ? saved.search : '',page:!legacy && Number.isSafeInteger(saved?.page) && saved!.page!>0 ? saved!.page! : 1,kind:!legacy&&catalogKinds.some(kind=>kind===saved?.kind)?saved!.kind!:'ALL',editor:saved?.editor && typeof saved.editor.values==='object' && typeof saved.editor.original==='object' && Number.isSafeInteger(saved.editor.version) ? saved.editor : null};
}
export function CatalogWorkspace({session, tenantId, resource, scope, onError, heading}: {session:Session;tenantId:string;resource:CatalogResource;scope:(path:string)=>string;onError:(e:unknown)=>string;heading:ReactNode}) {
  const t=useTranslations('catalog'), a=useTranslations('app'), r=useTranslations('resources');
  const tenant=session.isSuperAdmin ? tenantId : session.tenantId || '';
  const key=catalogKey(session.id,tenant,resource), endpoint='/catalog/'+resource.replace('catalog-','');
  const [state,setState]=useState<CatalogState>(()=>restored(key,resource));
  const [pending,setPending]=useState<CatalogPending|null>(()=>typeof sessionStorage==='undefined'?null:readCatalog(sessionStorage,key+':pending'));
  const [identity,setIdentity]=useState(session), [rows,setRows]=useState<Row[]>([]), [references,setReferences]=useState<Row[]>([]), [total,setTotal]=useState(0);
  const [loading,setLoading]=useState(true), [busy,setBusy]=useState(false), [error,setError]=useState(''), [revision,setRevision]=useState(0), [stale,setStale]=useState(false);
  const [result,setResult]=useState<Conversion|null>(null), [review,setReview]=useState<unknown>(null), [reviewed,setReviewed]=useState(false);
  const [currentRecord,setCurrentRecord]=useState<Record<string,unknown>|null>(null);
  const [typeDeleteChecked,setTypeDeleteChecked]=useState<{id:string;version:number}|null>(null), [typeDeleteBlocked,setTypeDeleteBlocked]=useState(false);
  const context=useRef({key,generation:0});
  if(context.current.key!==key)context.current={key,generation:context.current.generation+1};
  const deletionContext=useRef(context.current);
  const lock=useRef(false), mounted=useRef(true), recoveryChecked=useRef(false), stateRef=useRef(state);
  stateRef.current=state;
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  useEffect(()=>{setIdentity(session);},[session]);
  const readable=!!tenant && can(identity,resource,'read');
  const editor=state.editor;
  const writable=readable && !!editor && !editor.readonly && can(identity,resource,resource==='catalog-numbering'||editor.id?'update':'create');
  const disabled=!writable || busy || loading || stale || !!pending;
  const url=(suffix='')=>scope(endpoint+suffix);
  function change(next:Partial<CatalogState>) {setState(previous=>{const value={...previous,...next};storeCatalog(sessionStorage,key,value);return value;});}
  const deleting=state.deleting;
  function setDeleting(row:Row|null) {deletionContext.current=context.current;change({deleting:row});}
  function fail(e:unknown) {const code=e instanceof ApiError?e.code:'';setError(t.has(code)?t(code):onError(e)+(e instanceof ApiError && e.field ? ` · ${t.has(e.field)?t(e.field):e.field}`:''));}
  async function fresh(action:string) {
    const origin=context.current;
    const current=await api<Session>('/session');
    if(!mounted.current || context.current!==origin)throw new ApiError('forbidden',403);
    setIdentity(current);
    if(current.id!==session.id || current.mustChangePassword || (!current.isSuperAdmin && current.tenantId!==tenant) || !can(current,resource,'read') || !can(current,resource,action)) throw new ApiError('forbidden',403);
    return current;
  }
  async function checkTypeDeletion(row:Row, signal?:AbortSignal) {
    const origin=context.current;
    await fresh('delete');
    if(signal?.aborted||!mounted.current||context.current!==origin)throw new ApiError('forbidden',403);
    const check=await api<{canDelete:boolean}>(url('/'+encodeURIComponent(row.id)+'/deletion-check'),'GET',undefined,{signal});
    if(typeof check?.canDelete!=='boolean')throw new ApiError('write_not_verified',502);
    return check.canDelete;
  }
  async function openTypeDeletion(row:Row) {
    if(resource!=='catalog-types'||lock.current||busy||loading||pending)return;
    const origin=context.current;
    lock.current=true;setBusy(true);setError('');setStale(false);setTypeDeleteChecked(null);setTypeDeleteBlocked(false);
    try {
      const allowed=await checkTypeDeletion(row);
      if(!mounted.current||context.current!==origin)return;
      if(allowed){setTypeDeleteChecked({id:row.id,version:Number(row.version)});setDeleting(row);}
      else {setDeleting(null);setTypeDeleteBlocked(true);}
    }catch(e){if(mounted.current&&context.current===origin){setDeleting(null);fail(e);}}
    finally {lock.current=false;if(mounted.current&&context.current===origin)setBusy(false);}
  }
  async function allUnits(signal?:AbortSignal) {
    const list:Row[]=[]; let page=1, count=1;
    while(list.length<count) {const data=await api<Page>(url(`?page=${page++}&pageSize=100&search=`),'GET',undefined,{signal});list.push(...data.items);count=data.total;if(!data.items.length)break;}
    return list;
  }
  useEffect(()=>{
    if(!readable){setRows([]);setLoading(false);return;}
    let alive=true;const controller=new AbortController();setLoading(true);setError('');
    (async()=>{
      const current=await api<Session>('/session','GET',undefined,{signal:controller.signal});
      if(!alive)return;setIdentity(current);
      if(current.id!==session.id || (!current.isSuperAdmin&&current.tenantId!==tenant) || !can(current,resource,'read'))throw new ApiError('forbidden',403);
      let data:Page;
      if(resource==='catalog-numbering') {
        const kinds=catalogKinds;
        const configs=await Promise.all(kinds.map(kind=>api<Record<string,unknown>>(url(`?kind=${kind}`),'GET',undefined,{signal:controller.signal})));
        const search=state.search.trim().toLocaleLowerCase();
        const items=kinds.map((kind,i): Row=>({...configs[i],id:kind,kind})).filter(row=>(state.kind==='ALL'||row.kind===state.kind)&&(!search||[t(String(row.kind)),t(String(row.mode)),row.prefix,row.nextNumber].some(value=>String(value??'').toLocaleLowerCase().includes(search))));
        data={items,total:items.length,page:1,pageSize:25};
      }
      else data=await api<Page>(url(`?page=${state.page}&pageSize=25&search=${encodeURIComponent(state.search)}${resource==='catalog-types'&&state.kind!=='ALL'?'&kind='+state.kind:''}`),'GET',undefined,{signal:controller.signal});
      let refs:Row[]=[];
      if(resource==='catalog-categories') refs=(await api<{items:Row[]}>(url('/tree'),'GET',undefined,{signal:controller.signal})).items;
      if(resource==='catalog-units' && stateRef.current.conversion) refs=await allUnits(controller.signal);
      if(!alive)return;setRows(data.items);setTotal(data.total);setReferences(refs);
      // Eligibility is authoritative metadata, never the stored draft/baseline.
      // Refresh it even after initial recovery without adopting the server version.
      if(recoveryChecked.current&&resource==='catalog-types'&&stateRef.current.editor?.id) {
        const recovered=stateRef.current.editor;
        const record=await api<Row>(url('/'+encodeURIComponent(recovered.id!)),'GET',undefined,{signal:controller.signal});
        if(alive){setStale(Number(record.version)!==recovered.version);setCurrentRecord(record);}
      }
      if(!recoveryChecked.current) {
        const recovered=stateRef.current.editor;
        if(recovered) {
          const action=resource==='catalog-numbering'||recovered.id?'update':'create';
          if(!recovered.readonly&&!can(current,resource,action)) change({editor:null});
          else if(recovered.id) {
            const record=resource==='catalog-numbering'?await api<Row>(url(`?kind=${encodeURIComponent(recovered.id)}`),'GET',undefined,{signal:controller.signal}):await api<Row>(url('/'+encodeURIComponent(recovered.id)),'GET',undefined,{signal:controller.signal});
            if(alive){setStale(Number(record.version)!==recovered.version);setCurrentRecord(record);}
          }
        }
        if(stateRef.current.deleting) {
          const saved=stateRef.current.deleting;
          if(!['catalog-categories','catalog-types'].includes(resource)||!can(current,resource,'delete'))setDeleting(null);
          else if(!pending) {
            try {
              const actual=await api<Row>(url('/'+encodeURIComponent(saved.id)),'GET',undefined,{signal:controller.signal});
              const allowed=resource!=='catalog-types'||await checkTypeDeletion(saved,controller.signal);
              if(alive) {
                setStale(Number(actual.version)!==Number(saved.version));
                if(resource==='catalog-types') {
                  if(allowed)setTypeDeleteChecked({id:saved.id,version:Number(saved.version)});
                  else {setDeleting(null);setTypeDeleteBlocked(true);}
                }
              }
            }catch(e){if(alive&&resource==='catalog-types'){setDeleting(null);setTypeDeleteChecked(null);}throw e;}
          }
        }
        if(alive)recoveryChecked.current=true;
      }
    })().catch(e=>{if(alive){setStale(!!stateRef.current.editor);fail(e);}}).finally(()=>{if(alive)setLoading(false);});
    return()=>{alive=false;controller.abort();};
  },[key,resource,scope,state.search,state.page,state.kind,revision,readable]);
  async function open(row:Row|null, readOnly=false) {
    if(busy||pending)return;
    setError('');setStale(false);setBusy(true);
    try {
      await fresh(readOnly?'read':row?'update':'create');
      const record=row ? resource==='catalog-numbering' ? await api<Row>(url(`?kind=${encodeURIComponent(row.id)}`)) : await api<Row>(url('/'+encodeURIComponent(row.id))) : catalogInitial(resource);
      if(!mounted.current)return;
      setCurrentRecord(record);
      change({editor:{id:row?.id??null,version:Number(record.version??0),values:{...record},original:{...record},readonly:readOnly}});
    }catch(e){if(mounted.current)fail(e);}finally{if(mounted.current)setBusy(false);}
  }
  function field(name:string,value:unknown) {
    if(disabled||!editor)return;
    const values={...editor.values,[name]:value};
    if(name==='kind' && value!=='GOOD')values.default_track_stock=false;
    if(name==='is_base' && value===true)values.factor_to_base='1';
    if(name==='conversion_scope'){values.factor_to_base=value==='ITEM'?null:'1';values.is_base=false;}
    change({editor:{...editor,values}});
  }
  function pendingWrite(value:CatalogPending|null) {
    if(!storeCatalog(sessionStorage,key+':pending',value))throw new ApiError('storageUnavailable',400);
    setPending(value);
  }
  async function mutate(method:string, record:CatalogEditor) {
    if(lock.current||pending||stale||loading)return;
    if(method==='DELETE'&&(deletionContext.current!==context.current||(resource==='catalog-types'&&(typeDeleteChecked?.id!==record.id||typeDeleteChecked.version!==record.version))))return;
    const origin=context.current, active=()=>mounted.current&&context.current===origin;
    const action=method==='DELETE'?'delete':resource==='catalog-numbering'||record.id?'update':'create';
    lock.current=true;setBusy(true);setError('');let started=false,committed=false;
    const values=resource==='catalog-numbering'?record.values:catalogValues(resource,record.values,!!record.id);
    if(resource==='catalog-types'&&record.id&&(currentRecord?.canChangeKind===true||record.values.kind!==record.original.kind))values.kind=record.values.kind;
    const guard:CatalogPending={method,id:record.id,kind:resource==='catalog-numbering'?record.id!:state.kind,values,version:record.version};
    try {
      await fresh(action);
      if(!active())return;
      pendingWrite(guard);started=true;
      const path=resource==='catalog-numbering'?url(`?kind=${encodeURIComponent(record.id!)}`):url(record.id?'/'+encodeURIComponent(record.id)+(method==='DELETE'?`?expectedVersion=${record.version}`:''):'');
      const body=method==='DELETE'?undefined:resource==='catalog-numbering'?{mode:values.mode,prefix:values.prefix,padding:values.padding,nextNumber:values.nextNumber,version:record.version}:{values,...record.id?{expectedVersion:record.version}:{}};
      const saved=await api<Row|undefined>(path,method,body);committed=true;
      if(!active())return;
      // Il commit è registrato prima della rilettura: nessun reinvio dopo errore di lettura.
      const accepted={...guard,id:saved?.id??guard.id,committed:true};pendingWrite(accepted);
      if(resource==='catalog-numbering')await api(url(`?kind=${encodeURIComponent(record.id!)}`));
      else if(method==='DELETE' && accepted.id) {
        let absent=false;
        try {await api(url('/'+encodeURIComponent(accepted.id)));} catch(e) {if(e instanceof ApiError && e.status===404)absent=true;else throw e;}
        if(!absent)throw new ApiError('write_not_verified',502);
      } else if(accepted.id)await api(url('/'+encodeURIComponent(accepted.id)));
      else throw new ApiError('write_not_verified',502);
      if(!active())return;
      pendingWrite(null);change({editor:null});setDeleting(null);setStale(false);setRevision(v=>v+1);
    }catch(e){
      if(!active())return;
      if(started&&!committed&&!catalogUncertain(e as ApiError)) {
        pendingWrite(null);
        if(resource==='catalog-types'&&method==='DELETE'&&e instanceof ApiError&&e.code==='item_type_in_use') {
          setDeleting(null);setTypeDeleteChecked(null);setTypeDeleteBlocked(true);
        }
        if(e instanceof ApiError && ['stale_version','version_exhausted'].includes(e.code)) {
          setStale(true);
          try {const latest=await api<Record<string,unknown>>(resource==='catalog-numbering'?url(`?kind=${encodeURIComponent(record.id!)}`):url('/'+encodeURIComponent(record.id!)));if(active())setCurrentRecord(latest);} catch { /* La bozza rimane bloccata se il confronto non è disponibile. */ }
        }
      }
      if(active())fail(e);
    }finally{lock.current=false;if(active())setBusy(false);}
  }
  async function reviewPending() {
    if(!pending||lock.current)return;lock.current=true;setBusy(true);setError('');setReviewed(false);
    try {
      await fresh('read');
      let data:unknown;
      if(resource==='catalog-numbering')data=await api(url(`?kind=${pending.kind}`));
      else if(pending.id) {try {data=await api(url('/'+encodeURIComponent(pending.id)));}catch(e){if(e instanceof ApiError&&e.status===404)data=t('notFound');else throw e;}}
      else data=await api(url('?page=1&pageSize=100&search='+encodeURIComponent(String(pending.values.code||pending.values.name||''))));
      setReview(data);setReviewed(true);setRevision(v=>v+1);
    }catch(e){fail(e);}finally{lock.current=false;setBusy(false);}
  }
  async function convert() {
    const input=state.conversion;if(!input||loading||!readable||lock.current||!conversionTargets(references,references.find(row=>row.id===input.sourceId)).some(row=>row.id===input.targetId))return;
    lock.current=true;setBusy(true);setError('');setResult(null);
    try {await fresh('read');const value=await api<Conversion>(url('/'+encodeURIComponent(input.sourceId)+'/convert'),'POST',{targetUnitId:input.targetId,quantity:input.quantity});if(mounted.current)setResult(value);}
    catch(e){if(mounted.current)fail(e);}finally{lock.current=false;if(mounted.current)setBusy(false);}
  }
  async function openConversion(row:Row) {
    setBusy(true);setError('');setResult(null);
    try{await fresh('read');const units=await allUnits();if(mounted.current){const source=units.find(unit=>unit.id===row.id);setReferences(units);change({conversion:{sourceId:row.id,targetId:conversionTargets(units,source)[0]?.id??'',quantity:'1'}});}}catch(e){fail(e);}finally{setBusy(false);}
  }
  const value=editor?.values??{};
  function text(name:string,options:{required?:boolean;type?:string;min?:number;max?:number;readOnly?:boolean}={}) {
    return <div className="space-y-2" key={name}><Label htmlFor={'catalog-'+name} required={options.required}>{t(name)}</Label><Input id={'catalog-'+name} value={String(value[name]??'')} disabled={disabled||options.readOnly} required={options.required} type={options.type??'text'} min={options.min} max={options.max} step={options.type==='number'?1:undefined} onChange={e=>field(name,options.type==='number'?Number(e.target.value):e.target.value)} /></div>;
  }
  function toggle(name:string,readOnly=false) {return <div className="field switch-field" key={name}><Label htmlFor={'catalog-'+name}>{t(name)}</Label><Switch id={'catalog-'+name} checked={!!value[name]} disabled={disabled||readOnly} onCheckedChange={v=>field(name,v)} /></div>;}
  function select(name:string,options:{value:string;label:string}[],readOnly=false,required=false) {return <div className="space-y-2" key={name}><Label htmlFor={'catalog-'+name} required={required}>{t(name)}</Label><Select value={String(value[name]??'__none__')} disabled={disabled||readOnly} onValueChange={v=>field(name,v==='__none__'?null:v)}><SelectTrigger id={'catalog-'+name} className="w-full"><SelectValue /></SelectTrigger><SelectContent>{options.map(o=><SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent></Select></div>;}
  const columns=resource==='catalog-units'?['name','code','dimension','conversion_scope','decimal_places','is_active']:resource==='catalog-categories'?['name','code','parent_id','is_active']:resource==='catalog-types'?['name','code','kind','is_active']:resource==='catalog-brands'?['name','code','is_active']:['kind','mode','prefix','nextNumber'];
  const statusBadge=(active:boolean)=><Badge variant={active?'default':'secondary'}>{t(active?'active':'inactive')}</Badge>;
  function summary(data:unknown):ReactNode {
    if(typeof data==='string')return <p>{data}</p>;
    if(!data||typeof data!=='object')return null;
    const list=Array.isArray((data as Page).items)?(data as Page).items:[data as Record<string,unknown>];
    const names=resource==='catalog-numbering'?['mode','prefix','padding','nextNumber','version']:Object.keys(catalogInitial(resource)).concat('version');
    return <div className="max-h-64 overflow-auto space-y-3">{!list.length?<p>{t('empty')}</p>:list.map((record,index)=><dl key={index} className="grid grid-cols-2 gap-x-3 gap-y-1 rounded border p-3 text-sm">{names.filter(name=>Object.hasOwn(record,name)).map(name=>{
      const raw=record[name];const label=raw==null||raw===''?'—':typeof raw==='boolean'?t(raw?'yes':'no'):name==='parent_id'?categoryPath(references,String(raw))||'—':['dimension','kind','mode','conversion_scope'].includes(name)?t(String(raw)):String(raw);
      return <div key={name} className="contents"><dt className="text-muted-foreground">{t(name)}</dt><dd className="break-words">{name==='is_active'&&typeof raw==='boolean'?statusBadge(raw):label}</dd></div>;
    })}</dl>)}</div>;
  }
  const icon=(label:string,Icon:typeof Eye,fn:()=>void,blocked=false)=><Button type="button" variant="ghost" size="icon" aria-label={label} title={label} disabled={busy||loading||blocked} onClick={fn}><Icon size={16}/></Button>;
  const conversion=state.conversion, source=references.find(row=>row.id===conversion?.sourceId), targets=conversionTargets(references,source);
  return <div data-catalog-workspace={resource}>
    <div className="page-heading mb-4">{heading}{resource!=='catalog-numbering'&&readable&&can(identity,resource,'create')&&<Button id="catalog-new" disabled={busy||loading||!!pending} onClick={()=>void open(null)}><Plus size={16}/>{a('new')}</Button>}</div>
    {error&&<Alert variant="destructive" className="mb-4"><AlertDescription>{error}</AlertDescription></Alert>}
    {pending&&<Alert className="mb-4"><AlertDescription><p>{t('uncertain')}</p><div className="flex flex-wrap gap-2 mt-2"><Button variant="outline" disabled={busy||!readable} onClick={()=>void reviewPending()}>{t('review')}</Button>{reviewed&&<Button variant="outline" disabled={busy} onClick={()=>{pendingWrite(null);change({editor:null});setDeleting(null);setStale(false);setReview(null);setReviewed(false);setRevision(v=>v+1);}}>{t('acknowledge')}</Button>}</div>{review!==null&&summary(review)}</AlertDescription></Alert>}
    {!readable?<p>{a('noAccess')}</p>:<Card className="gap-0 overflow-hidden py-0">
      <div className="flex items-start gap-2 border-b"><div className="min-w-0 flex-1"><FilterBar id="catalog-filters" expanded={state.filtersExpanded===true} onExpandedChange={filtersExpanded=>change({filtersExpanded})} fields={[
        {key:'search',minWidth:200,grow:true,content:<Input id="catalog-search" aria-label={a('search')} placeholder={a('search')} value={state.search} onChange={e=>change({search:e.target.value,page:1})}/>},
        ...((resource==='catalog-numbering'||resource==='catalog-types')?[{key:'kind',minWidth:180,content:<Select value={state.kind} disabled={busy||!!editor} onValueChange={kind=>{setResult(null);change({kind:kind as CatalogState['kind'],page:1});}}><SelectTrigger aria-label={t('kind')} className="w-full"><SelectValue/></SelectTrigger><SelectContent>{['ALL',...catalogKinds].map(kind=><SelectItem key={kind} value={kind}>{kind==='ALL'?t('allKinds'):t(kind)}</SelectItem>)}</SelectContent></Select>}]:[])
       ]}/></div><div className="py-3 pr-3">{icon(a('refresh'),RefreshCw,()=>setRevision(v=>v+1))}</div></div>
      <Table id="catalog-table" className="w-full text-sm"><TableHeader><TableRow>{columns.map(c=><TableHead kind={c==='is_active'?'status':['decimal_places','nextNumber','padding','factor_to_base','sort_order','version'].includes(c)?'number':'text'} key={c}>{t(c)}</TableHead>)}<TableHead kind="actions" className="w-44 min-w-44 max-w-44">{a('actions')}</TableHead></TableRow></TableHeader><TableBody>
        {loading?<TableRow><TableCell colSpan={columns.length+1}>{a('loading')}</TableCell></TableRow>:!rows.length?<TableRow><TableCell colSpan={columns.length+1}>{t('empty')}</TableCell></TableRow>:rows.map(row=><TableRow key={row.id} data-record-id={row.id}>
          {columns.map(c=><TableCell kind={c==='is_active'?'status':['decimal_places','nextNumber','padding','factor_to_base','sort_order','version'].includes(c)?'number':'text'} className="py-2" key={c}>{c==='parent_id'?categoryPath(references,String(row.parent_id??''))||t('root'):c==='is_active'?statusBadge(!!row[c]):['dimension','kind','mode','conversion_scope'].includes(c)?t(String(row[c]??(c==='conversion_scope'?'UNIVERSAL':row.id))):String(row[c]??'—')}</TableCell>)}
          <TableCell kind="actions" className="w-44 min-w-44 max-w-44 py-1 whitespace-nowrap">{icon(`${a('details')} ${row.name??t(row.id)}`,Eye,()=>void open(row,true),!!pending)}{can(identity,resource,'update')&&icon(`${a('edit')} ${row.name??t(row.id)}`,Pencil,()=>void open(row),!!pending)}{resource==='catalog-units'&&row.is_active===true&&row.conversion_scope!=='ITEM'&&icon(t('convert')+' '+row.name,ArrowRightLeft,()=>void openConversion(row))}{resource==='catalog-types'&&can(identity,resource,'delete')&&icon(a('delete')+' '+row.name,Trash2,()=>void openTypeDeletion(row),!!pending)}{resource==='catalog-categories'&&can(identity,resource,'delete')&&icon(a('delete')+' '+row.name,Trash2,()=>{setError('');setStale(false);setDeleting(row);},!!pending||references.some(child=>child.parent_id===row.id))}</TableCell>
        </TableRow>)}
      </TableBody></Table>
      <div className="flex justify-end items-center gap-3 p-3"><span className="table-count">{total} {a('records',{count:total})}</span>{resource!=='catalog-numbering'&&<><Button size="icon" variant="outline" aria-label={t('previous')} disabled={loading||state.page<=1} onClick={()=>change({page:state.page-1})}><ChevronLeft size={16}/></Button><span>{state.page} / {Math.max(1,Math.ceil(total/25))}</span><Button size="icon" variant="outline" aria-label={t('next')} disabled={loading||state.page*25>=total} onClick={()=>change({page:state.page+1})}><ChevronRight size={16}/></Button></>}</div>
    </Card>}
    <Dialog open={!!editor&&readable&&!pending} onOpenChange={open=>{if(!open&&!busy)change({editor:null});}}><DialogContent data-testid="catalog-editor" showCloseButton={!busy} className="sm:max-w-2xl max-h-[90dvh] overflow-auto"><DialogHeader><DialogTitle>{editor?.readonly?a('details'):editor?.id?a('edit'):a('new')} · {r(resource)}</DialogTitle><DialogDescription className="sr-only">{r(resource)}</DialogDescription></DialogHeader>
      {error&&<p role="alert" className="text-destructive">{error}</p>}{stale&&<Alert variant="destructive"><AlertDescription>{t('stale')}<p className="font-medium">{t('original')}</p>{summary(editor?.original)}{currentRecord&&<><p className="font-medium">{t('current')}</p>{summary(currentRecord)}</>}<Button type="button" variant="outline" disabled={busy} onClick={()=>{change({editor:null});setStale(false);setRevision(v=>v+1);}}>{t('discardReload')}</Button></AlertDescription></Alert>}
      <form onSubmit={e=>{e.preventDefault();e.stopPropagation();if(editor&&!disabled)void mutate(resource==='catalog-numbering'||editor.id?'PUT':'POST',editor);}} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          {resource==='catalog-numbering'?<>{select('mode',['AUTO','MANUAL'].map(x=>({value:x,label:t(x)})),false,true)}{text('prefix')}{text('padding',{required:true,type:'number',min:1,max:15})}{text('nextNumber',{required:true,type:'number',min:1,max:1000000000000000})}<output className="sm:col-span-2 break-all font-mono">{value.mode==='MANUAL'?t('MANUAL'):String(value.prefix??'')+String(value.nextNumber??'').padStart(Math.min(15,Math.max(1,Number(value.padding)||1)),'0')}</output></>:<>
            {text('name',{required:true})}{text('code',{required:resource==='catalog-units'})}
            {resource==='catalog-units'&&<>{select('conversion_scope',['UNIVERSAL','ITEM'].map(x=>({value:x,label:t(x)})),!!editor?.id)}{select('dimension',dimensions.map(x=>({value:x,label:t(x)})),!!editor?.id,true)}{value.conversion_scope!=='ITEM'&&text('factor_to_base',{required:true,readOnly:!!editor?.id||!!value.is_base})}{text('decimal_places',{required:true,type:'number',min:0,max:12})}{toggle('is_base',!!editor?.id||value.conversion_scope==='ITEM')}</>}
            {resource==='catalog-brands'&&<div className="space-y-2 sm:col-span-2"><Label htmlFor="catalog-description">{t('description')}</Label><Textarea id="catalog-description" disabled={disabled} value={String(value.description??'')} onChange={e=>field('description',e.target.value)}/></div>}
            {resource==='catalog-categories'&&<>{select('parent_id',[{value:'__none__',label:t('root')},...categoryParents(references,editor?.id??null).map(row=>({value:row.id,label:categoryPath(references,row.id)}))])}{text('sort_order',{required:true,type:'number'})}<div className="space-y-2 sm:col-span-2"><Label htmlFor="catalog-description">{t('description')}</Label><Textarea id="catalog-description" disabled={disabled} value={String(value.description??'')} onChange={e=>field('description',e.target.value)}/></div></>}
            {resource==='catalog-types'&&<>{select('kind',catalogKinds.map(x=>({value:x,label:t(x)})),!!editor?.id&&currentRecord?.canChangeKind!==true,true)}{toggle('default_sellable')}{toggle('default_purchasable')}{toggle('default_track_stock',value.kind!=='GOOD')}</>}{toggle('is_active')}
          </>}
        </div>
        <DialogFooter><Button id="catalog-cancel" type="button" variant="outline" disabled={busy} onClick={()=>change({editor:null})}>{a('cancel')}</Button>{!editor?.readonly&&<Button id="catalog-save" type="submit" disabled={disabled}>{busy?a('loading'):a('save')}</Button>}</DialogFooter>
      </form>
    </DialogContent></Dialog>
    <Dialog open={!!deleting&&deletionContext.current===context.current&&readable&&(!pending||busy)&&(resource!=='catalog-types'||(!loading&&typeDeleteChecked?.id===deleting.id&&typeDeleteChecked.version===Number(deleting.version)&&can(identity,resource,'delete')))} onOpenChange={open=>{if(!open&&!busy)setDeleting(null);}}><DialogContent data-testid="catalog-delete-confirm" showCloseButton={!busy}><DialogHeader><DialogTitle>{a('delete')} · {String(deleting?.name??'')}</DialogTitle><DialogDescription>{t(resource==='catalog-types'?'deleteType':'deleteLeaf')}</DialogDescription></DialogHeader>{error&&<p role="alert">{error}</p>}{stale&&<p role="alert">{t(resource==='catalog-types'?'staleTypeDelete':'staleDelete')}</p>}<DialogFooter><Button id="catalog-delete-cancel" variant="outline" disabled={busy} onClick={()=>setDeleting(null)}>{a('cancel')}</Button><Button id="catalog-delete-confirm" variant="destructive" disabled={busy||loading||!!pending||stale||!can(identity,resource,'delete')} onClick={()=>{if(deleting)void mutate('DELETE',{id:deleting.id,version:Number(deleting.version),values:{...deleting},original:{...deleting}});}}>{a('delete')}</Button></DialogFooter></DialogContent></Dialog>
    <Dialog open={typeDeleteBlocked&&deletionContext.current===context.current&&readable&&resource==='catalog-types'&&!pending} onOpenChange={open=>{if(!open)setTypeDeleteBlocked(false);}}><DialogContent data-testid="catalog-type-delete-blocked" showCloseButton={false}><DialogHeader><DialogTitle>{a('delete')} · {r(resource)}</DialogTitle><DialogDescription>{t('item_type_in_use')}</DialogDescription></DialogHeader><DialogFooter><Button id="catalog-type-delete-close" variant="outline" onClick={()=>setTypeDeleteBlocked(false)}>{a('close')}</Button></DialogFooter></DialogContent></Dialog>
    <Dialog open={!!conversion&&readable} onOpenChange={open=>{if(!open&&!busy){change({conversion:null});setResult(null);}}}><DialogContent showCloseButton={!busy}><DialogHeader><DialogTitle>{t('convert')} · {String(source?.name??'')}</DialogTitle><DialogDescription>{t('roundingPolicy')}</DialogDescription></DialogHeader>
      {error&&<p role="alert" className="text-destructive">{error}</p>}<form className="space-y-4" onSubmit={e=>{e.preventDefault();e.stopPropagation();void convert();}}>
      <div className="space-y-2"><Label htmlFor="catalog-target" required>{t('target')}</Label><Select value={conversion?.targetId||'__none__'} disabled={busy||loading||!targets.length} onValueChange={targetId=>{if(conversion){change({conversion:{...conversion,targetId}});setResult(null);}}}><SelectTrigger id="catalog-target" className="w-full"><SelectValue/></SelectTrigger><SelectContent><SelectItem value="__none__" disabled>{t('chooseUnit')}</SelectItem>{targets.map(row=><SelectItem value={row.id} key={row.id}>{String(row.name)} ({String(row.code)})</SelectItem>)}</SelectContent></Select></div>
      <div className="space-y-2"><Label htmlFor="catalog-quantity" required>{t('quantity')}</Label><Input id="catalog-quantity" required inputMode="decimal" pattern="[+-]?[0-9]+(\.[0-9]+)?" value={conversion?.quantity??''} disabled={busy} onChange={e=>{if(conversion){change({conversion:{...conversion,quantity:e.target.value}});setResult(null);}}}/></div>
      {result&&<div role="status" className="rounded border p-3 space-y-1"><div>{t('result')}: <output>{result.quantity}</output></div><div>{t('unrounded')}: {result.unroundedQuantity}</div><div>{t(result.rounded?'rounded':'exact')} · {t('decimal_places')}: {result.decimalPlaces}</div></div>}
      <DialogFooter><Button type="button" variant="outline" disabled={busy} onClick={()=>{change({conversion:null});setResult(null);}}>{a('close')}</Button><Button type="submit" disabled={busy||loading||!readable||!targets.some(row=>row.id===conversion?.targetId)}>{t('convert')}</Button></DialogFooter></form>
    </DialogContent></Dialog>
  </div>;
}
