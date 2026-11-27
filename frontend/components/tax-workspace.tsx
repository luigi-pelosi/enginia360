"use client";
import {useEffect, useRef, useState, type ReactNode} from 'react';
import {useTranslations} from 'next-intl';
import {Eye, Pencil, Plus, RefreshCw, CalendarPlus, Power, Trash2, Download} from 'lucide-react';
import {api, ApiError} from '@/lib/api';
import {TaxClassifications} from '@/components/tax-classifications';
import {TaxRegimes} from '@/components/tax-regimes';
import {TaxRules} from '@/components/tax-rules';
import {TaxSimulator} from '@/components/tax-simulator';
import {resetTaxRuleRecovery,resetTaxSimulatorRecovery} from '@/lib/tax-rules';
import {clearTaxRegimeDraft} from '@/lib/company-tax';
import {resetClassificationState} from '@/lib/tax-classifications';
import {can, type Session} from '@/lib/model';
import {taxSections, taxTreatments, taxNatureChoices, taxKey, taxDefaults, readTaxState, resetTaxState, blankTaxVersion, taxDateValid, taxNatureRequired, validateTaxVersion, validateTaxVersions, taxCreatePayload, taxMetadataPayload, advanceTaxEditor, type TaxState, type TaxPending, type TaxCode, type TaxEditor, type TaxVersion, type TaxNature, type TaxType, type TaxCountry, type TaxSection, type TaxTreatment} from '@/lib/tax';
import {Badge} from '@/components/ui/badge';
import {Button} from '@/components/ui/button';
import {Card} from '@/components/ui/card';
import {FilterBar} from '@/components/ui/filter-bar';
import {Input} from '@/components/ui/input';
import {Textarea} from '@/components/ui/textarea';
import {Label} from '@/components/ui/label';
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from '@/components/ui/table';
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from '@/components/ui/select';
import {Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter} from '@/components/ui/dialog';

type Page<T>={items:T[];total:number;page:number;pageSize:number};
type Audit={id:string;action:string;created_at:string;actor_id:string|null;details:unknown};
type Nature=TaxNature & {country_iso_code?:string;valid_from?:string;valid_to?:string|null;scheme?:string};
export function resetTaxRecovery(session:Session,tenant:string) {
  try {const effectiveTenant=session.isSuperAdmin?tenant:session.tenantId||'';const key=taxKey(session.id,effectiveTenant);resetTaxState(sessionStorage,key);resetClassificationState(sessionStorage,key);clearTaxRegimeDraft(sessionStorage,session.id,effectiveTenant);resetTaxRuleRecovery(sessionStorage,session.id,effectiveTenant);resetTaxSimulatorRecovery(sessionStorage,session.id,effectiveTenant);}catch { /* Non eliminare comandi di esito incerto. */ }
}
function recovery(key:string,initialSection?:string):TaxState {
  const state=typeof sessionStorage==='undefined'?taxDefaults():readTaxState(sessionStorage,key);
  if(taxSections.includes(initialSection as TaxSection))state.section=initialSection as TaxSection;
  return state;
}
export function TaxManagement({session,tenantId,initialSection,scope,onError,heading}:{session:Session;tenantId:string;initialSection?:string;scope:(path:string)=>string;onError:(e:unknown)=>string;heading:ReactNode}) {
  const t=useTranslations('tax'),a=useTranslations('app'),r=useTranslations('resources');
  const tenant=session.isSuperAdmin?tenantId:session.tenantId||'',key=taxKey(session.id,tenant);
  const [state,setState]=useState<TaxState>(()=>recovery(key,initialSection));
  const [identity,setIdentity]=useState(session),[codes,setCodes]=useState<TaxCode[]>([]),[types,setTypes]=useState<TaxType[]>([]),[natures,setNatures]=useState<Nature[]>([]),[countries,setCountries]=useState<TaxCountry[]>([]),[total,setTotal]=useState(0);
  const [typeRows,setTypeRows]=useState<TaxType[]>([]),[natureRows,setNatureRows]=useState<Nature[]>([]);
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(''),[notice,setNotice]=useState(''),[revision,setRevision]=useState(0),[stale,setStale]=useState(false),[verified,setVerified]=useState(false),[referencesReady,setReferencesReady]=useState(false);
  const [pending,setPending]=useState<TaxPending|null>(()=>{try {const saved=sessionStorage.getItem(key+':pending');return saved?JSON.parse(saved):null;}catch{return {path:'',method:'',body:null,recordId:null,action:'unknown'};}});
  const [review,setReview]=useState<unknown>(null),[current,setCurrent]=useState<TaxCode|null>(null),[audit,setAudit]=useState<Audit[]>([]),[auditPage,setAuditPage]=useState(1),[auditTotal,setAuditTotal]=useState(0);
  const lock=useRef(false),mounted=useRef(true),stateRef=useRef(state),restored=useRef(false);
  stateRef.current=state;
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  const available=taxSections.filter(section=>can(identity,section,'read'));
  const section=available.includes(state.section)?state.section:available[0];
  const classification=section==='tax-item-classifications'||section==='tax-partner-classifications';
  const regimes=section==='tax-regimes';
  const rules=section==='tax-rules',simulator=section==='tax-determination';
  const specialized=classification||regimes||rules||simulator;
  const codeRead=!!tenant && can(identity,'tax-codes','read');
  const editor=state.editor;
  const editable=!!editor && !editor.readonly && can(identity,'tax-codes',editor.id?'update':'create');
  const disabled=busy||loading||!verified||stale||!!pending;
  const countryCode=countries.find(c=>c.id===editor?.values.country_id)?.iso_code || editor?.original?.country_iso_code || editor?.original?.country_code || '';
  function change(next:Partial<TaxState>) {setState(previous=>{const value={...previous,...next};try {sessionStorage.setItem(key,JSON.stringify(value));}catch { /* La bozza resta in memoria, le scritture richiedono storage funzionante. */ }return value;});}
  function fail(e:unknown) {
    const code=e instanceof ApiError?e.code:'';
    const names:Record<string,string>={name:'name',code:'code',tax_type_id:'type',country_id:'country',rate:'rate',treatment:'treatment',tax_nature_code_id:'nature',valid_from:'valid_from',valid_to:'valid_to',legal_reference:'legal_reference',description:'description'};
    const field=e instanceof ApiError&&e.field?names[e.field]:null;
    setError((t.has(code)?t(code):onError(e))+(field?` · ${t(field)}`:''));
    if(e instanceof ApiError && ['stale_version','tax_stale_version'].includes(code))setStale(true);
  }
  const url=(path:string)=>scope('/tax'+path);
  async function fresh(action:string) {
    const actual=await api<Session>('/session');
    if(!mounted.current || actual.id!==session.id || actual.mustChangePassword || !actual.isSuperAdmin && actual.tenantId!==tenant || !can(actual,'tax-codes','read') || !can(actual,'tax-codes',action))throw new ApiError('forbidden',403);
    setIdentity(actual);return actual;
  }
  useEffect(()=>{setIdentity(session);},[session]);
  useEffect(()=>{
    if(!tenant || !section || specialized){setLoading(false);setVerified(false);return;}
    let alive=true;const controller=new AbortController();setLoading(true);setError('');setVerified(false);
    (async()=>{
      const actual=await api<Session>('/session','GET',undefined,{signal:controller.signal});
      if(!alive)return;
      if(actual.id!==session.id || actual.mustChangePassword || !actual.isSuperAdmin && actual.tenantId!==tenant || !can(actual,section,'read'))throw new ApiError('forbidden',403);
      setIdentity(actual);
      const params=new URLSearchParams({page:String(state.page),pageSize:'25',search:state.search});
      if(state.date && taxDateValid(state.date) && section!=='tax-types')params.set('date',state.date);
      if(state.country && section!=='tax-types')params.set('country_id',state.country);
      const endpoint=section==='tax-codes'?'codes':section==='tax-types'?'types':'nature-codes';
      const result=await api<Page<TaxCode & TaxType & Nature>>(url(`/${endpoint}?${params}`),'GET',undefined,{signal:controller.signal});
      if(!alive)return;
      setTotal(result.total);
      if(section==='tax-codes')setCodes(result.items);else if(section==='tax-types')setTypeRows(result.items);else setNatureRows(result.items);
      if(!result.items.length && state.page>1){change({page:state.page-1});return;}
      if(!restored.current && stateRef.current.editor) {
        const saved=stateRef.current.editor;
        if(!can(actual,'tax-codes','read') || !saved.readonly && !can(actual,'tax-codes',saved.id?'update':'create'))change({editor:null,versionDraft:null});
        else if(saved.id) {
          const record=await api<TaxCode>(url('/codes/'+encodeURIComponent(saved.id)),'GET',undefined,{signal:controller.signal});
          if(!alive)return;setCurrent(record);setStale(record.version!==saved.expectedVersion);
        }
      }
      if(alive){restored.current=true;setVerified(true);}
    })().catch(e=>{if(alive)fail(e);}).finally(()=>{if(alive)setLoading(false);});
    return()=>{alive=false;controller.abort();};
  },[key,tenant,section,state.search,state.page,state.date,state.country,scope,revision]);
  // Lookup del dominio fiscale: nessun permesso countries.read e nessuna CRUD generica.
  useEffect(()=>{
    if(!codeRead||specialized)return;
    let alive=true;const controller=new AbortController();setReferencesReady(false);
    api<{countries:TaxCountry[];types:TaxType[];natureCodes:Nature[]}>(url('/lookups'),'GET',undefined,{signal:controller.signal}).then(data=>{if(alive){setCountries(data.countries);setTypes(data.types);setNatures(data.natureCodes);setReferencesReady(true);}}).catch(e=>{if(alive)fail(e);});
    return()=>{alive=false;controller.abort();};
  },[key,codeRead,scope,revision,specialized]);
  useEffect(()=>{
    if(section!=='tax-codes' || !editor?.id || state.tab!=='audit' || !codeRead)return;
    let alive=true;const controller=new AbortController();setAudit([]);
    api<Page<Audit>>(url(`/codes/${encodeURIComponent(editor.id)}/audit?page=${auditPage}&pageSize=25`),'GET',undefined,{signal:controller.signal}).then(data=>{if(alive){setAudit(data.items);setAuditTotal(data.total);}}).catch(e=>{if(alive)fail(e);});
    return()=>{alive=false;controller.abort();};
  },[editor?.id,state.tab,auditPage,revision,scope,codeRead,section]);
  async function open(row:TaxCode|null,readonly=false) {
    if(lock.current||pending||loading)return;
    lock.current=true;setBusy(true);setError('');setNotice('');
    try {
      await fresh(readonly?'read':row?'update':'create');
      const record=row?await api<TaxCode>(url('/codes/'+encodeURIComponent(row.id))):null;
      if(!mounted.current)return;
      setCurrent(record);setStale(false);setAuditPage(1);
      const firstType=types.find(type=>type.is_active && type.code==='VAT'),firstCountry=countries[0];
      if(!row && (!referencesReady || !firstType || !firstCountry))throw new ApiError('referencesRequired',400);
      const draft:TaxEditor=record?{id:record.id,expectedVersion:record.version,original:record,values:{name:record.name,code:record.code,description:record.description||'',country_id:record.country_id,tax_type_id:record.tax_type_id},versions:record.versions||[],readonly}:{id:null,expectedVersion:0,original:null,values:{name:'',code:'',description:'',country_id:firstCountry!.id,tax_type_id:firstType!.id},versions:[],readonly:false};
      change({editor:draft,tab:'general',versionDraft:null,versionIndex:null});
    }catch(e){if(mounted.current)fail(e);}finally{lock.current=false;if(mounted.current)setBusy(false);}
  }
  function field(name:keyof TaxEditor['values'],value:string) {
    if(!editor||!editable||disabled)return;
    change({editor:{...editor,values:{...editor.values,[name]:value},versions:name==='country_id'?[]:editor.versions},versionDraft:name==='country_id'?null:state.versionDraft});
  }
  async function mutate(path:string,method:string,body:unknown,action:string,recordId:string|null,keepDraft=false) {
    if(lock.current||disabled||!tenant)return;
    lock.current=true;setBusy(true);setError('');setNotice('');setReview(null);
    let marked=false,committed=false;
    const command:TaxPending={path,method,body,recordId,action};
    try {
      await fresh(action);
      if(!mounted.current)return;
      if(sessionStorage.getItem(key+':pending')){setPending(command);return;}
      sessionStorage.setItem(key,JSON.stringify(stateRef.current));
      const marker=JSON.stringify(command);sessionStorage.setItem(key+':pending',marker);
      if(sessionStorage.getItem(key+':pending')!==marker)throw new ApiError('storageUnavailable',0);
      marked=true;
      const response=await api<TaxCode & {installed:number;skipped:number}>(url(path),method,body);
      committed=true;
      const id=recordId||response.id;
      let record:TaxCode|null=null;
      if(id) {
        record=await api<TaxCode>(url('/codes/'+encodeURIComponent(id)));
        if(!Number.isSafeInteger(record.version)||record.id!==id||!Array.isArray(record.versions)||record.version!==response.version)throw new ApiError('write_not_verified',502);
      }else if(action==='install_templates') {
        if(!Number.isSafeInteger(response.installed)||!Number.isSafeInteger(response.skipped))throw new ApiError('write_not_verified',502);
        await api<Page<TaxCode>>(url('/codes?page=1&pageSize=100&search=VAT_'));
      }else throw new ApiError('write_not_verified',502);
      sessionStorage.removeItem(key+':pending');
      if(!mounted.current)return;
      setPending(null);setCurrent(record);setStale(false);
      if(keepDraft && record && stateRef.current.editor) {
        const used=(body as {expectedVersion:number}).expectedVersion;
        change({editor:advanceTaxEditor(stateRef.current.editor,record,used),versionDraft:null,versionIndex:null,transition:null});
      }else change({editor:null,versionDraft:null,versionIndex:null,transition:null,installDate:null});
      setNotice(action==='install_templates'?t('installed',{installed:response.installed,skipped:response.skipped}):a('saved'));setRevision(v=>v+1);
    }catch(e){
      if(marked && !committed && e instanceof ApiError && e.status>=400 && e.status<500 && e.code!=='write_not_verified') {
        try {sessionStorage.removeItem(key+':pending');}catch {if(mounted.current)setPending(command);}
      }else if(marked || !(e instanceof ApiError) || e.code==='storageUnavailable') {if(mounted.current)setPending(command);}
      if(mounted.current) {
        fail(e);
        if(e instanceof ApiError && ['tax_stale_version','stale_version'].includes(e.code) && recordId) {
          try {const record=await api<TaxCode>(url('/codes/'+encodeURIComponent(recordId)));if(mounted.current)setCurrent(record);}catch { /* La versione originale resta invariata e il reinvio resta bloccato. */ }
        }
      }
    }finally{lock.current=false;if(mounted.current)setBusy(false);}
  }
  function save() {
    if(!editor||!editable||disabled)return;
    if(!editor.values.name.trim() || !editor.values.code.trim() || !editor.values.country_id || !editor.values.tax_type_id){setError(t('requiredFields'));change({tab:'general'});return;}
    if(!editor.id) {
      const invalid=validateTaxVersions(editor.versions,countryCode,natures);
      if(invalid){setError(t(invalid));change({tab:'versions'});return;}
    }
    void mutate('/codes'+(editor.id?'/'+encodeURIComponent(editor.id):''),editor.id?'PUT':'POST',editor.id?taxMetadataPayload(editor):taxCreatePayload(editor),editor.id?'update':'create',editor.id);
  }
  function beginVersion(index:number|null=null) {
    if(!editor||disabled||!referencesReady||editor.id && (!can(identity,'tax-codes','schedule') || editor.original?.is_active===false))return;
    change({versionDraft:index===null?blankTaxVersion():{...editor.versions[index]},versionIndex:index});
  }
  function confirmVersion() {
    const row=state.versionDraft;if(!row||!editor||disabled)return;
    const countryNatures=natures.filter(n=>n.country_id===editor.values.country_id);
    const invalid=validateTaxVersion(row,countryCode,countryNatures);
    if(invalid){setError(t(invalid));return;}
    if(editor.id) {
      void mutate(`/codes/${encodeURIComponent(editor.id)}/versions`,'POST',{values:row,expectedVersion:editor.expectedVersion},'schedule',editor.id,true);
    }else {
      const versions=[...editor.versions];if(state.versionIndex===null)versions.push(row);else versions[state.versionIndex]=row;
      const error=validateTaxVersions(versions,countryCode,countryNatures);if(error){setError(t(error));return;}
      change({editor:{...editor,versions},versionDraft:null,versionIndex:null});setError('');
    }
  }
  function changeTreatment(treatment:TaxTreatment) {
    if(!editor||!state.versionDraft)return;
    const first=taxNatureChoices(natures,editor.values.country_id,countryCode,treatment)[0];
    change({versionDraft:{...state.versionDraft,treatment,rate:treatment==='TAXABLE'?(state.versionDraft.rate==='0'?'22':state.versionDraft.rate):'0',tax_nature_code_id:taxNatureRequired(treatment,countryCode)?first?.id||null:null}});
  }
  async function reviewPending() {
    if(!pending||busy)return;
    setBusy(true);setError('');setReview(null);
    try {
      await fresh('read');
      const result=pending.recordId?await api<TaxCode>(url('/codes/'+encodeURIComponent(pending.recordId))):await api<Page<TaxCode>>(url('/codes?page=1&pageSize=100&search='+encodeURIComponent(String((pending.body as {values?:{code?:string}})?.values?.code||'VAT_'))));
      if(mounted.current){setReview(result);setRevision(v=>v+1);}
    }catch(e){if(mounted.current)fail(e);}finally{if(mounted.current)setBusy(false);}
  }
  function acknowledgePending() {
    if(!pending||!review||busy)return;
    try {sessionStorage.removeItem(key+':pending');setPending(null);setReview(null);change({editor:null,versionDraft:null,transition:null,installDate:null});setStale(false);setRevision(v=>v+1);}catch(e){fail(e);}
  }
  const stableId=(id:string)=>(({'tax-country':'tax-country_id','tax-type':'tax-tax_type_id','tax-version-rate':'tax-rate','tax-nature':'tax-tax_nature_code_id','tax-valid-from':'tax-valid_from','tax-valid-to':'tax-valid_to','tax-legal':'tax-legal_reference'} as Record<string,string>)[id]||id);
  const select=(id:string,value:string,choices:{value:string;label:string}[],onChange:(v:string)=>void,optional=false,off=false)=><Select value={value||'__none__'} disabled={off||busy} onValueChange={v=>onChange(v==='__none__'?'':v)}><SelectTrigger id={stableId(id)} className="w-full"><SelectValue/></SelectTrigger><SelectContent>{(optional||!value)&&<SelectItem value="__none__">{a('none')}</SelectItem>}{choices.map(x=><SelectItem key={x.value} value={x.value}>{x.label}</SelectItem>)}</SelectContent></Select>;
  const status=(active:boolean)=><Badge variant={active?'default':'secondary'}>{t(active?'active':'inactive')}</Badge>;
  const icon=(label:string,Icon:typeof Eye,onClick:()=>void,off=false)=><Button type="button" variant="ghost" size="icon" className="size-8" aria-label={label} title={label} onClick={onClick} disabled={off||busy}><Icon className="size-4" aria-hidden="true"/></Button>;
  const input=(id:string,label:string,value:string,onChange:(v:string)=>void,required=false,off=false,type='text',maxLength?:number)=><div className="space-y-2"><Label htmlFor={stableId(id)} required={required}>{label}</Label><Input id={stableId(id)} value={value} type={type} maxLength={maxLength} required={required} disabled={off||busy} onChange={e=>onChange(e.target.value)}/></div>;
  const natureLabel=(version:TaxVersion)=>natures.find(n=>n.id===version.tax_nature_code_id)?.code || version.tax_nature_code || '—';
  const pages=Math.max(1,Math.ceil(total/25));
  const countryOptions=countries.map(c=>({value:c.id,label:`${c.name} (${c.iso_code})`}));
  const visibleNatures=section==='tax-nature-codes'?natureRows:[];
  const natureCountryOptions=[...new Map(visibleNatures.map(n=>[n.country_id,{value:n.country_id,label:n.country_iso_code||'—'}])).values()];
  const fiscalTable=(versions:TaxVersion[],staged=false)=><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>{t('valid_from')}</TableHead><TableHead>{t('valid_to')}</TableHead><TableHead kind="number">{t('rate')}</TableHead><TableHead>{t('treatment')}</TableHead><TableHead>{t('nature')}</TableHead><TableHead>{t('legal_reference')}</TableHead>{staged&&<TableHead kind="actions" className="w-24">{a('actions')}</TableHead>}</TableRow></TableHeader><TableBody>{versions.length?versions.map((v,i)=><TableRow key={v.id||i}><TableCell>{v.valid_from}</TableCell><TableCell>{v.valid_to||'—'}</TableCell><TableCell kind="number">{v.rate}%</TableCell><TableCell>{t(v.treatment)}</TableCell><TableCell>{natureLabel(v)}</TableCell><TableCell className="max-w-64 whitespace-normal">{v.legal_reference||'—'}</TableCell>{staged&&<TableCell kind="actions" className="w-24"><div className="flex justify-center">{icon(a('edit'),Pencil,()=>beginVersion(i),!editable||disabled)}{icon(t('removeVersion'),Trash2,()=>editor&&change({editor:{...editor,versions:editor.versions.filter((_,index)=>index!==i)}}),!editable||disabled)}</div></TableCell>}</TableRow>):<TableRow><TableCell colSpan={staged?7:6} className="text-center">{a('empty')}</TableCell></TableRow>}</TableBody></Table></div>;
  const navigation=available.map((item,index)=><Button key={item} data-testid={`tax-tab-${item.replace('tax-','')}`} type="button" role="tab" aria-selected={section===item} tabIndex={section===item?0:-1} variant={section===item?'default':'ghost'} disabled={busy} onClick={()=>{change({section:item,search:'',page:1,country:'',editor:null,versionDraft:null});setStale(false);}} onKeyDown={e=>{if(['ArrowRight','ArrowLeft','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?available.length-1:(index+(e.key==='ArrowRight'?1:-1)+available.length)%available.length;change({section:available[next],page:1,search:'',country:'',editor:null,versionDraft:null});e.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();}}}>{r(item)}</Button>);
  return <div className="space-y-4 min-w-0" data-tax-management>
    <div className="page-heading">{heading}</div>
    {rules?<TaxRules key={key+section} session={session} tenantId={tenantId} scope={scope} onError={onError} navigation={navigation} onBusyChange={setBusy}/>:simulator?<TaxSimulator key={key+section} session={session} tenantId={tenantId} scope={scope} onError={onError} navigation={navigation} onBusyChange={setBusy}/>:regimes?<><div className="flex flex-wrap items-center gap-2 border-b pb-3" role="tablist" aria-label={r('tax-management')}>{navigation}</div><TaxRegimes key={key+section} session={session} tenantId={tenantId} scope={scope} onError={onError}/></>:classification?<TaxClassifications key={key+section} kind={section==='tax-item-classifications'?'item':'partner'} session={session} tenantId={tenantId} scope={scope} onError={onError} navigation={navigation} onBusyChange={setBusy}/>:<>
    <div className="flex flex-wrap items-center gap-2 border-b pb-3" role="tablist" aria-label={r('tax-management')}>
      {navigation}
      <div className="ml-auto flex flex-wrap gap-2" role="group" aria-label={a('actions')}>{section==='tax-codes'&&codeRead&&!editor&&<>{can(identity,'tax-codes','install_templates')&&<Button type="button" variant="outline" disabled={disabled} onClick={()=>change({installDate:''})}><Download size={16}/>{t('installTemplates')}</Button>}{can(identity,'tax-codes','create')&&<Button id="tax-new" type="button" disabled={disabled||!referencesReady} onClick={()=>void open(null)}><Plus size={16}/>{a('new')}</Button>}</>}</div>
    </div>
    {error&&<p role="alert" className="text-sm text-destructive">{error}</p>}{notice&&<p role="status" className="text-sm">{notice}</p>}
    {pending&&<Card className="p-4 space-y-3"><p role="alert" className="text-destructive">{t('uncertain')}</p><div className="flex gap-2"><Button variant="outline" disabled={busy||!codeRead} onClick={()=>void reviewPending()}>{t('review')}</Button>{review!==null&&<Button disabled={busy} onClick={acknowledgePending}>{t('acknowledge')}</Button>}</div>{review!==null&&<div className="grid gap-4 md:grid-cols-2"><div><h3>{t('attempted')}</h3><pre className="max-h-72 overflow-auto text-xs whitespace-pre-wrap">{JSON.stringify(pending.body,null,2)}</pre></div><div><h3>{t('authoritative')}</h3><pre className="max-h-72 overflow-auto text-xs whitespace-pre-wrap">{JSON.stringify(review,null,2)}</pre></div></div>}</Card>}
    {!tenant?<Card className="p-6">{a('selectTenant')}</Card>:!section?<Card className="p-6">{a('noAccess')}</Card>:<Card className="gap-0 overflow-hidden py-0">
      <div className="flex items-start gap-2 border-b"><div className="min-w-0 flex-1"><FilterBar id="tax-filters" expanded={state.filtersExpanded} onExpandedChange={filtersExpanded=>change({filtersExpanded})} fields={[
        {key:'search',grow:true,minWidth:200,content:input('tax-search',a('search'),state.search,search=>change({search,page:1}),false,false,'text',200)},
        ...(section==='tax-types'?[]:[{key:'date',minWidth:160,content:input('tax-date',t('atDate'),state.date,date=>{if(!date||taxDateValid(date))change({date,page:1});},false,false,'date')}]),
        ...(section==='tax-types'?[]:[{key:'country',minWidth:180,content:<div className="space-y-2"><Label htmlFor="tax-country-filter">{t('country')}</Label>{select('tax-country-filter',state.country,codeRead?countryOptions:natureCountryOptions,country=>change({country,page:1}),true)}</div>}]),
      ]}/></div><div className="flex shrink-0 items-center gap-2 p-4 pt-10"><span className="text-sm tabular-nums">{total}</span>{icon(a('refresh'),RefreshCw,()=>setRevision(v=>v+1),busy)}</div></div>
      <div className="table-scroll"><Table id="tax-table"><TableHeader><TableRow><TableHead>{t('code')}</TableHead><TableHead>{t('name')}</TableHead>{section==='tax-codes'?<><TableHead kind="number">{t('rate')}</TableHead><TableHead>{t('nature')}</TableHead><TableHead kind="status">{t('status')}</TableHead><TableHead kind="actions" className="w-32">{a('actions')}</TableHead></>:section==='tax-types'?<TableHead kind="status">{t('status')}</TableHead>:<><TableHead>{t('country')}</TableHead><TableHead>{t('valid_from')}</TableHead><TableHead>{t('valid_to')}</TableHead></>}</TableRow></TableHeader><TableBody>
        {loading?<TableRow><TableCell colSpan={section==='tax-codes'?6:section==='tax-types'?3:5}>{t('loading')}</TableCell></TableRow>:total===0?<TableRow><TableCell colSpan={section==='tax-codes'?6:section==='tax-types'?3:5}><p className="table-empty">{a('empty')}</p></TableCell></TableRow>:section==='tax-codes'?codes.map(row=><TableRow key={row.id}><TableCell>{row.code}</TableCell><TableCell className="min-w-48 whitespace-normal font-medium">{row.name}</TableCell><TableCell kind="number">{row.rate==null?'—':`${row.rate}%`}</TableCell><TableCell>{row.tax_nature_code||'—'}</TableCell><TableCell kind="status">{status(row.is_active)}</TableCell><TableCell kind="actions" className="w-32"><div className="flex justify-center">{icon(`${a('details')} ${row.name}`,Eye,()=>void open(row,true),!!pending)}{can(identity,'tax-codes','update')&&icon(`${a('edit')} ${row.name}`,Pencil,()=>void open(row),disabled)}{can(identity,'tax-codes',row.is_active?'deactivate':'reactivate')&&icon(`${t(row.is_active?'deactivate':'reactivate')} ${row.name}`,Power,()=>change({transition:row}),disabled)}</div></TableCell></TableRow>):section==='tax-types'?typeRows.map(row=><TableRow key={row.id}><TableCell>{row.code}</TableCell><TableCell className="whitespace-normal">{row.name}</TableCell><TableCell kind="status">{status(row.is_active)}</TableCell></TableRow>):visibleNatures.map(row=><TableRow key={row.id}><TableCell>{row.code}</TableCell><TableCell className="whitespace-normal">{row.description||row.name}</TableCell><TableCell>{row.country_iso_code||'—'}</TableCell><TableCell>{row.valid_from||'—'}</TableCell><TableCell>{row.valid_to||'—'}</TableCell></TableRow>)}
      </TableBody></Table></div><div className="pagination"><span>{a('page')} {state.page} {a('of')} {pages}</span><div><Button variant="outline" disabled={busy||state.page<=1} onClick={()=>change({page:state.page-1})}>{a('previous')}</Button><Button variant="outline" disabled={busy||state.page>=pages} onClick={()=>change({page:state.page+1})}>{a('next')}</Button></div></div>
    </Card>}
    {editor&&!pending&&section==='tax-codes'&&<Dialog open onOpenChange={open=>{if(!open&&!busy)change({editor:null,versionDraft:null});}}><DialogContent id="tax-editor" data-tax-editor aria-describedby={undefined} className="max-h-[90vh] overflow-y-auto sm:max-w-5xl min-w-0"><DialogHeader><DialogTitle>{a(editor.id?(editor.readonly?'details':'edit'):'new')} · {r('tax-codes')}</DialogTitle></DialogHeader>
      <div className="flex flex-wrap items-center gap-2 border-b pb-2" role="tablist" aria-label={r('tax-codes')}>{(['general','versions','audit'] as const).filter(tab=>tab!=='audit'||editor.id).map((tab,index,tabs)=><Button key={tab} data-testid={`tax-editor-${tab}`} type="button" role="tab" tabIndex={state.tab===tab?0:-1} aria-selected={state.tab===tab} variant={state.tab===tab?'default':'ghost'} onClick={()=>change({tab})} onKeyDown={e=>{if(['ArrowRight','ArrowLeft','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?tabs.length-1:(index+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;change({tab:tabs[next]});e.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();}}}>{t(tab)}</Button>)}<div className="ml-auto flex gap-2"><Button type="button" variant="outline" disabled={busy} onClick={()=>change({editor:null,versionDraft:null})}>{a('cancel')}</Button>{editable&&<Button type="submit" form="tax-editor-form" disabled={disabled}>{a('save')}</Button>}</div></div>
      {stale&&<p role="alert" className="text-destructive">{t('tax_stale_version')}</p>}{error&&<p role="alert" className="text-destructive">{error}</p>}
      <form id="tax-editor-form" onSubmit={e=>{e.preventDefault();save();}} className="min-w-0" noValidate>
        {state.tab==='general'&&<div role="tabpanel" className="grid gap-4 sm:grid-cols-2">{input('tax-name',t('name'),editor.values.name,v=>field('name',v),true,!editable||disabled,'text',150)}{input('tax-code',t('code'),editor.values.code,v=>field('code',v),true,!editable||disabled||!!editor.id,'text',50)}<div className="space-y-2"><Label htmlFor="tax-tax_type_id" required>{t('type')}</Label>{select('tax-type',editor.values.tax_type_id,types.filter(row=>row.code==='VAT'&&row.is_active||row.id===editor.values.tax_type_id).map(row=>({value:row.id,label:row.name})),v=>field('tax_type_id',v),false,!editable||disabled||!!editor.id)}</div><div className="space-y-2"><Label htmlFor="tax-country_id" required>{t('country')}</Label>{select('tax-country',editor.values.country_id,countryOptions.length?countryOptions:[{value:editor.values.country_id,label:countryCode||'—'}],v=>field('country_id',v),false,!editable||disabled||!!editor.id)}</div><div className="space-y-2 sm:col-span-2"><Label htmlFor="tax-description">{t('description')}</Label><Textarea id="tax-description" value={editor.values.description} maxLength={10000} disabled={!editable||disabled} onChange={e=>field('description',e.target.value)}/></div>{editor.original&&<div className="sm:col-span-2 flex flex-wrap items-center gap-4">{status(editor.original.is_active)}<span className="text-sm">{t('revision')}: {editor.expectedVersion}</span><span className="text-sm">{t('updated_at')}: {editor.original.updated_at}</span></div>}</div>}
        {state.tab==='versions'&&<div role="tabpanel" className="min-w-0 space-y-3"><div className="flex items-center justify-between gap-2"><h3 className="font-medium">{t('versions')}</h3>{((!editor.id&&editable)||editor.id&&can(identity,'tax-codes','schedule')&&editor.original?.is_active)&&<Button id="tax-add-version" type="button" variant="outline" disabled={disabled||!referencesReady||!editor.id&&editor.versions.length>=100} onClick={()=>beginVersion()}><CalendarPlus size={16}/>{t(editor.id?'schedule':'addVersion')}</Button>}</div>{fiscalTable(editor.versions,!editor.id)}{!editor.id&&!editor.versions.length&&<p className="text-sm text-destructive">{t('initialVersionRequired')}</p>}</div>}
        {state.tab==='audit'&&editor.id&&<div role="tabpanel" className="space-y-3 min-w-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>{t('created_at')}</TableHead><TableHead>{t('action')}</TableHead><TableHead>{t('actor')}</TableHead><TableHead>{a('details')}</TableHead></TableRow></TableHeader><TableBody>{audit.map(row=><TableRow key={row.id}><TableCell>{row.created_at}</TableCell><TableCell>{t.has('actions.'+row.action)?t('actions.'+row.action):row.action}</TableCell><TableCell>{row.actor_id||'—'}</TableCell><TableCell><details><summary className="cursor-pointer">{a('details')}</summary><pre className="max-h-48 max-w-lg overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(row.details,null,2)}</pre></details></TableCell></TableRow>)}</TableBody></Table></div><div className="pagination"><span>{a('page')} {auditPage} {a('of')} {Math.max(1,Math.ceil(auditTotal/25))}</span><div><Button type="button" variant="outline" disabled={auditPage<=1} onClick={()=>setAuditPage(v=>v-1)}>{a('previous')}</Button><Button type="button" variant="outline" disabled={auditPage*25>=auditTotal} onClick={()=>setAuditPage(v=>v+1)}>{a('next')}</Button></div></div></div>}
      </form>
      {stale&&current&&<details><summary>{t('authoritative')}</summary><pre className="max-h-48 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(current,null,2)}</pre></details>}
    </DialogContent></Dialog>}
    {state.versionDraft && editor && !pending && <Dialog open onOpenChange={open=>{
      if(!open && !busy)change({versionDraft:null,versionIndex:null});
    }}>
      <DialogContent aria-describedby={undefined} className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader><DialogTitle>{t(editor.id?'schedule':'addVersion')}</DialogTitle></DialogHeader>
        <form className="space-y-4" onSubmit={e=>{
          e.preventDefault();e.stopPropagation();confirmVersion();
        }}>
          <div className="grid gap-4 sm:grid-cols-2">
            {input('tax-version-rate',t('rate'),state.versionDraft.rate,
              rate=>change({versionDraft:{...state.versionDraft!,rate}}),true,disabled,'text',20)}
            <div className="space-y-2">
              <Label htmlFor="tax-treatment" required>{t('treatment')}</Label>
              {select('tax-treatment',state.versionDraft.treatment,
                taxTreatments.filter(v=>v!=='ZERO_RATED'||countryCode!=='IT').map(value=>({value,label:t(value)})),
                value=>changeTreatment(value as TaxTreatment),false,disabled)}
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="tax-tax_nature_code_id" required={taxNatureRequired(state.versionDraft.treatment,countryCode)}>{t('nature')}</Label>
              {select('tax-nature',state.versionDraft.tax_nature_code_id||'',
                taxNatureChoices(natures,editor.values.country_id,countryCode,state.versionDraft.treatment)
                  .map(n=>({value:n.id,label:`${n.code} · ${n.description||n.name||''}`})),
                value=>change({versionDraft:{...state.versionDraft!,tax_nature_code_id:value||null}}),
                true,disabled||['TAXABLE','ZERO_RATED'].includes(state.versionDraft.treatment))}
            </div>
            {input('tax-valid-from',t('valid_from'),state.versionDraft.valid_from,
              valid_from=>change({versionDraft:{...state.versionDraft!,valid_from}}),true,disabled,'date')}
            {input('tax-valid-to',t('valid_to'),state.versionDraft.valid_to||'',
              valid_to=>change({versionDraft:{...state.versionDraft!,valid_to:valid_to||null}}),false,disabled,'date')}
            {input('tax-legal',t('legal_reference'),state.versionDraft.legal_reference||'',
              legal_reference=>change({versionDraft:{...state.versionDraft!,legal_reference:legal_reference||null}}),
              false,disabled,'text',255)}
          </div>
          {editor.id&&<p className="text-sm">{t('scheduleConfirmation')}</p>}
          {error&&<p role="alert" className="text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" disabled={busy} onClick={()=>change({versionDraft:null,versionIndex:null})}>{a('cancel')}</Button>
            <Button disabled={disabled}>{a('save')}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>}
    {state.installDate!==null&&!pending&&<Dialog open onOpenChange={open=>{if(!open&&!busy)change({installDate:null});}}><DialogContent aria-describedby={undefined}><DialogHeader><DialogTitle>{t('installTemplates')}</DialogTitle></DialogHeader><form className="space-y-4" onSubmit={e=>{e.preventDefault();if(taxDateValid(state.installDate||''))void mutate('/codes/templates/install','POST',{validFrom:state.installDate},'install_templates',null);else setError(t('tax_invalid_period'));}}>{input('tax-install-date',t('valid_from'),state.installDate,installDate=>change({installDate}),true,disabled,'date')}<p className="text-sm">{t('installConfirmation')}</p>{error&&<p role="alert" className="text-destructive">{error}</p>}<DialogFooter><Button type="button" variant="outline" disabled={busy} onClick={()=>change({installDate:null})}>{a('cancel')}</Button><Button disabled={disabled||!taxDateValid(state.installDate)}>{t('install')}</Button></DialogFooter></form></DialogContent></Dialog>}
    {state.transition&&!pending&&<Dialog open onOpenChange={open=>{if(!open&&!busy)change({transition:null});}}><DialogContent aria-describedby={undefined}><DialogHeader><DialogTitle>{t(state.transition.is_active?'deactivate':'reactivate')} · {state.transition.name}</DialogTitle></DialogHeader><p>{t(state.transition.is_active?'deactivateConfirmation':'reactivateConfirmation')}</p>{error&&<p role="alert" className="text-destructive">{error}</p>}<DialogFooter><Button type="button" variant="outline" disabled={busy} onClick={()=>change({transition:null})}>{a('cancel')}</Button><Button disabled={disabled} onClick={()=>{const row=state.transition!;void mutate(`/codes/${encodeURIComponent(row.id)}/${row.is_active?'deactivate':'reactivate'}`,'POST',{expectedVersion:row.version},row.is_active?'deactivate':'reactivate',row.id);}}>{t(state.transition.is_active?'deactivate':'reactivate')}</Button></DialogFooter></DialogContent></Dialog>}
    </>}
  </div>;
}
