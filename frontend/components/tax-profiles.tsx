"use client";
import {useEffect,useRef,useState} from 'react';
import {useTranslations} from 'next-intl';
import {Plus,Pencil,Trash2,RefreshCw,ChevronLeft,ChevronRight} from 'lucide-react';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {Label} from '@/components/ui/label';
import {Badge} from '@/components/ui/badge';
import {FilterBar} from '@/components/ui/filter-bar';
import {Select,SelectContent,SelectItem,SelectTrigger,SelectValue} from '@/components/ui/select';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription,DialogFooter} from '@/components/ui/dialog';
import {Table,TableHeader,TableBody,TableRow,TableHead,TableCell} from '@/components/ui/table';
import {api,ApiError} from '@/lib/api';
import {can,type Session,type Row} from '@/lib/model';
import {readCatalog,storeCatalog} from '@/lib/catalog';
import {emptyTaxProfileLookups,taxProfileToday,taxProfilePath,taxProfileKey,taxProfileInitial,taxProfileOptions,taxProfileValues,taxProfileError,type TaxProfileDraft,type TaxProfileKind,type TaxProfileLookups,type TaxProfilePage,type TaxProfileEditor,type TaxProfilePending} from '@/lib/tax-profiles';
export type TaxProfilesProps={kind:TaxProfileKind;subjectId:string|null;session:Session;tenantId:string;scope:(path:string)=>string;onError:(error:unknown)=>string;staged:TaxProfileDraft[];onStagedChange:(rows:TaxProfileDraft[])=>void;disabled?:boolean};
type Recovery={editor:TaxProfileEditor|null;pending:TaxProfilePending|null};
export function TaxProfiles({kind,subjectId,session,tenantId,scope,onError,staged,onStagedChange,disabled=false}:TaxProfilesProps){
 const t=useTranslations('taxProfiles'),a=useTranslations('app');
 const resource=kind==='item'?'tax-item-profiles':'tax-partner-profiles',baseResource=kind==='item'?'catalog-items':'business-partners';
 const tenant=session.isSuperAdmin?tenantId:session.tenantId||'',key=taxProfileKey(session.id,tenant,kind,subjectId??'new');
 const [editor,setEditor]=useState<TaxProfileEditor|null>(()=>typeof sessionStorage==='undefined'?null:readCatalog<Recovery>(sessionStorage,key)?.editor??null);
 const [pending,setPending]=useState<TaxProfilePending|null>(()=>typeof sessionStorage==='undefined'?null:readCatalog<Recovery>(sessionStorage,key)?.pending??null);
 const [lookups,setLookups]=useState<TaxProfileLookups>(emptyTaxProfileLookups),[result,setResult]=useState<TaxProfilePage>({items:[],total:0,page:1,pageSize:25,version:0});
 const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(''),[page,setPage]=useState(1),[revision,setRevision]=useState(0),[date,setDate]=useState(taxProfileToday),[expanded,setExpanded]=useState(false),[reviewed,setReviewed]=useState(false);
 const lock=useRef(false),mounted=useRef(true);useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 const readable=!!tenant&&can(session,resource,'read')&&can(session,baseResource,'read');
 const assignable=can(session,resource,'assign'),schedulable=!!subjectId&&can(session,resource,'schedule');
 const available=subjectId?readable:!!tenant&&assignable;
 const blocked=disabled||loading||busy||!!pending;
 function persist(nextEditor:TaxProfileEditor|null,nextPending:TaxProfilePending|null){if(!storeCatalog(sessionStorage,key,{editor:nextEditor,pending:nextPending}))throw new ApiError('storageUnavailable',400);setEditor(nextEditor);setPending(nextPending);}
 function fail(e:unknown){if(!mounted.current)return;const code=e instanceof ApiError?e.code:'';setError(t.has(code)?t(code):onError(e));}
 async function readPage(target=page){return api<TaxProfilePage>(scope(taxProfilePath(kind,subjectId!)+`?page=${target}&pageSize=25`));}
 useEffect(()=>{
  if(!available){setLoading(false);return;}
  let alive=true;const controller=new AbortController();setLoading(true);
  Promise.all([api<TaxProfileLookups>(scope(`/tax/classification-lookups?kind=${kind}`),'GET',undefined,{signal:controller.signal}),subjectId?api<TaxProfilePage>(scope(taxProfilePath(kind,subjectId)+`?page=${page}&pageSize=25`),'GET',undefined,{signal:controller.signal}):Promise.resolve({items:[],total:0,page:1,pageSize:25,version:0})]).then(([refs,rows])=>{if(alive){setLookups(refs);setResult(rows);}}).catch(e=>{if(alive)fail(e);}).finally(()=>{if(alive)setLoading(false);});
  return()=>{alive=false;controller.abort();};
 },[key,available,page,revision,scope,kind,subjectId]);
 function open(operation:'assign'|'schedule',index?:number){
  if(blocked||operation==='assign'&&!assignable||operation==='schedule'&&!schedulable)return;
  const values=index===undefined?taxProfileInitial(kind,lookups):{...staged[index]};
  try{persist({values,operation,expectedVersion:result.version,...(index===undefined?{}:{index})},null);setError('');}catch(e){fail(e);}
 }
 function field(name:keyof TaxProfileDraft,value:string){
  if(blocked||!editor)return;
  let values={...editor.values,[name]:value||null} as TaxProfileDraft;
  if(name==='country_id'||name==='tax_type_id'){
   const options=taxProfileOptions(lookups,values);
   if(name==='country_id'&&!options.types.some(row=>row.id===values.tax_type_id))values.tax_type_id=options.types[0]?.id??'';
   const field=kind==='item'?'item_tax_classification_id':'partner_tax_classification_id';
   const classes=taxProfileOptions(lookups,values).classifications;
   if(!classes.some(row=>row.id===values[field]))values[field]=classes[0]?.id??'';
  }
  try{persist({...editor,values},null);setError('');}catch(e){fail(e);}
 }
 async function save(event:React.FormEvent){
  event.preventDefault();event.stopPropagation();if(!editor||blocked||lock.current)return;
  const before=editor,code=taxProfileError(kind,before.values,lookups);if(code){setError(t(code));return;}
  if(!subjectId){if(!assignable)return;const values=taxProfileValues(kind,before.values),next=staged.slice();if(before.index===undefined)next.push(values);else next[before.index]=values;onStagedChange(next);persist(null,null);return;}
  lock.current=true;setBusy(true);setError('');let started=false,accepted=false;
  const marker:TaxProfilePending={operation:before.operation,body:{values:taxProfileValues(kind,before.values),expectedVersion:before.expectedVersion}};
  try{
   const authority=await api<Session>('/session');
   if(authority.id!==session.id||authority.mustChangePassword||(!authority.isSuperAdmin&&authority.tenantId!==tenant)||!can(authority,baseResource,'read')||!can(authority,resource,before.operation))throw new ApiError('forbidden',403);
   persist(before,marker);started=true;
   const saved=await api<TaxProfilePage>(scope(taxProfilePath(kind,subjectId)+(before.operation==='schedule'?'/schedule':'')),'POST',marker.body);accepted=true;
   persist(before,{...marker,committedVersion:saved.version});
   const actual=await readPage(1);
   if(!mounted.current)return;
   setResult(actual);setPage(1);
   if(actual.version!==saved.version)throw new ApiError('stale_version',409);
   persist(null,null);setReviewed(false);
  }catch(e){if(started&&!accepted&&e instanceof ApiError&&e.status>=400&&e.status<500&&e.status!==408)persist(before,null);fail(e);}
  finally{lock.current=false;if(mounted.current)setBusy(false);}
 }
 async function review(){if(!subjectId||busy||lock.current)return;lock.current=true;setBusy(true);setReviewed(false);try{const actual=await readPage();if(mounted.current){setResult(actual);setReviewed(true);}}catch(e){fail(e);}finally{lock.current=false;if(mounted.current)setBusy(false);}}
 const refs=editor?taxProfileOptions(lookups,editor.values):emptyTaxProfileLookups;
 const classificationField=kind==='item'?'item_tax_classification_id':'partner_tax_classification_id';
 function select(name:'country_id'|'tax_type_id'|typeof classificationField,rows:Row[]){return <div className="space-y-2"><Label htmlFor={`tax-profile-${name}`} required>{t(name)}</Label><Select required value={String(editor?.values[name]??'')} disabled={blocked} onValueChange={value=>field(name,value)}><SelectTrigger id={`tax-profile-${name}`} className="w-full"><SelectValue/></SelectTrigger><SelectContent>{rows.map(row=><SelectItem key={row.id} value={row.id}>{String(row.code??row.iso_code??'')} {String(row.name??'')}</SelectItem>)}</SelectContent></Select></div>;}
 const rows=subjectId?result.items:staged;
 function name(collection:Row[],id:string|undefined){const row=collection.find(row=>row.id===id);return row?`${row.code??row.iso_code??''} ${row.name??''}`.trim():id||'—';}
 if(!available)return null;
 return <section data-testid="tax-profiles" data-subject-kind={kind} className="space-y-3" aria-busy={loading||busy}>
  <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">{t('title')}</h3><div className="flex gap-2">{assignable&&<Button type="button" id="tax-profile-assign" variant="outline" size="sm" disabled={blocked} onClick={()=>open('assign')}><Plus size={16}/>{t('assign')}</Button>}{schedulable&&<Button type="button" id="tax-profile-schedule" variant="outline" size="sm" disabled={blocked} onClick={()=>open('schedule')}>{t('schedule')}</Button>}{subjectId&&<Button type="button" size="icon" variant="ghost" aria-label={a('refresh')} disabled={busy} onClick={()=>setRevision(v=>v+1)}><RefreshCw size={16}/></Button>}</div></div>
  <p className="text-sm text-muted-foreground">{t(subjectId?'independentHint':'stagingHint')}</p>
  {error&&<p role="alert" className="text-destructive">{error}</p>}
  {pending&&<div role="alert" className="space-y-2 rounded border p-3"><p>{t('uncertain')}</p><Button type="button" id="tax-profile-review" disabled={busy} onClick={()=>void review()}>{t('review')}</Button>{reviewed&&<Button type="button" id="tax-profile-acknowledge" disabled={busy} onClick={()=>{persist(null,null);setReviewed(false);setError('');}}>{t('acknowledge')}</Button>}</div>}
  <FilterBar id="tax-profile-filters" expanded={expanded} onExpandedChange={setExpanded} fields={[{key:'date',minWidth:180,content:<div><Label htmlFor="tax-profile-preview-date">{t('previewDate')}</Label><Input id="tax-profile-preview-date" type="date" value={date} onChange={e=>setDate(e.target.value)}/></div>}]}/>
  <div className="overflow-x-auto"><Table id="tax-profile-history"><TableHeader><TableRow>{['country_id','tax_type_id','classification','valid_from','valid_to','atDate'].map(key=><TableHead key={key}>{t(key)}</TableHead>)}{!subjectId&&<TableHead kind="actions" className="w-24 min-w-24 max-w-24">{a('actions')}</TableHead>}</TableRow></TableHeader><TableBody>
   {!rows.length&&<TableRow><TableCell colSpan={subjectId?6:7}>{loading?a('loading'):t('empty')}</TableCell></TableRow>}
   {rows.map((row,index)=>{const stored=row as Partial<import('@/lib/tax-profiles').TaxProfile>,classification=lookups.classifications.find(ref=>ref.id===row[classificationField]);return <TableRow key={stored.id??index} data-profile-id={stored.id}><TableCell>{stored.country_name??name(lookups.countries,row.country_id)}</TableCell><TableCell>{stored.tax_type_name??name(lookups.types,row.tax_type_id)}</TableCell><TableCell>{stored.classification_code?`${stored.classification_code} ${stored.classification_name??''}`:name(lookups.classifications,row[classificationField])}{(stored.classification_is_active===false||classification?.is_active===false)&&<Badge variant="secondary">{t('inactiveClassification')}</Badge>}</TableCell><TableCell>{row.valid_from}</TableCell><TableCell>{row.valid_to??'—'}</TableCell><TableCell>{date&&row.valid_from<=date&&(!row.valid_to||date<=row.valid_to)?<Badge variant="secondary">{t('effective')}</Badge>:'—'}</TableCell>{!subjectId&&<TableCell kind="actions" className="w-24 min-w-24 max-w-24"><Button type="button" size="icon" variant="ghost" aria-label={a('edit')} disabled={blocked||!assignable} onClick={()=>open('assign',index)}><Pencil size={16}/></Button><Button type="button" size="icon" variant="ghost" aria-label={a('remove')} disabled={blocked||!assignable} onClick={()=>onStagedChange(staged.filter((_,i)=>i!==index))}><Trash2 size={16}/></Button></TableCell>}</TableRow>;})}
  </TableBody></Table></div>
  {subjectId&&<div className="flex items-center justify-end gap-2"><span>{result.total} · {result.page} / {Math.max(1,Math.ceil(result.total/result.pageSize))}</span><Button type="button" size="icon" variant="outline" aria-label={a('previous')} disabled={loading||busy||page<=1} onClick={()=>setPage(p=>p-1)}><ChevronLeft size={16}/></Button><Button type="button" size="icon" variant="outline" aria-label={a('next')} disabled={loading||busy||page*result.pageSize>=result.total} onClick={()=>setPage(p=>p+1)}><ChevronRight size={16}/></Button></div>}
  <Dialog open={!!editor&&(!pending||busy)} onOpenChange={open=>{if(!open&&!busy&&!pending)persist(null,null);}}><DialogContent data-testid="tax-profile-editor" className="sm:max-w-2xl"><DialogHeader><DialogTitle>{t(editor?.operation??'assign')}</DialogTitle><DialogDescription>{t(editor?.operation==='schedule'?'scheduleHint':'assignHint')}</DialogDescription></DialogHeader><form onSubmit={save} data-testid="tax-profile-form" className="space-y-4"><div className="grid gap-4 sm:grid-cols-2">{select('country_id',refs.countries)}{select('tax_type_id',refs.types)}{select(classificationField,refs.classifications)}{(['valid_from','valid_to'] as const).map(fieldName=><div key={fieldName} className="space-y-2"><Label htmlFor={`tax-profile-${fieldName}`} required={fieldName==='valid_from'}>{t(fieldName)}</Label><Input id={`tax-profile-${fieldName}`} required={fieldName==='valid_from'} type="date" min={fieldName==='valid_to'?editor?.values.valid_from:undefined} value={editor?.values[fieldName]??''} disabled={blocked} onChange={e=>field(fieldName,e.target.value)}/></div>)}</div><DialogFooter><Button type="button" variant="outline" disabled={busy} onClick={()=>persist(null,null)}>{a('cancel')}</Button><Button type="submit" id="tax-profile-save" disabled={blocked}>{subjectId?a('save'):t('stage')}</Button></DialogFooter></form></DialogContent></Dialog>
 </section>;
}
