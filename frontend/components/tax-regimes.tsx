"use client";
import {useEffect,useState} from 'react';
import {useTranslations} from 'next-intl';
import {RefreshCw} from 'lucide-react';
import {api,ApiError} from '@/lib/api';
import {can,type Session} from '@/lib/model';
import {taxRegimeKey,emptyCompanyTaxLookups,type CompanyTaxLookups,type CompanyTaxRegime} from '@/lib/company-tax';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {Label} from '@/components/ui/label';
import {Badge} from '@/components/ui/badge';
import {Card} from '@/components/ui/card';
import {FilterBar} from '@/components/ui/filter-bar';
import {Select,SelectContent,SelectItem,SelectTrigger,SelectValue} from '@/components/ui/select';
import {Table,TableBody,TableCell,TableHead,TableHeader,TableRow} from '@/components/ui/table';
type Filters={search:string;country:string;type:string;active:string;page:number;expanded:boolean};
const defaults:Filters={search:'',country:'',type:'',active:'',page:1,expanded:false};
function recovered(key:string):Filters{try{const value=JSON.parse(sessionStorage.getItem(key)||'null');return value?{search:typeof value.search==='string'?value.search.slice(0,200):'',country:typeof value.country==='string'?value.country:'',type:typeof value.type==='string'?value.type:'',active:['true','false'].includes(value.active)?value.active:'',page:Number.isSafeInteger(value.page)&&value.page>=1?value.page:1,expanded:value.expanded===true}:defaults;}catch{return defaults;}}
export function TaxRegimes({session,tenantId,scope,onError}:{session:Session;tenantId:string;scope:(path:string)=>string;onError:(error:unknown)=>string}){
 const t=useTranslations('taxRegimes'),a=useTranslations('app'),tenant=session.isSuperAdmin?tenantId:session.tenantId||'',key=taxRegimeKey(session.id,tenant);
 const [filters,setFilters]=useState<Filters>(()=>typeof sessionStorage==='undefined'?defaults:recovered(key)),[refs,setRefs]=useState<CompanyTaxLookups>(emptyCompanyTaxLookups),[rows,setRows]=useState<CompanyTaxRegime[]>([]),[total,setTotal]=useState(0),[loading,setLoading]=useState(true),[error,setError]=useState(''),[revision,setRevision]=useState(0);
 const readable=!!tenant&&can(session,'tax-regimes','read');
 function change(next:Partial<Filters>){setFilters(old=>{const value={...old,...next};try{sessionStorage.setItem(key,JSON.stringify(value));}catch{}return value;});}
 useEffect(()=>{setFilters(recovered(key));},[key]);
 useEffect(()=>{
  if(!readable){setLoading(false);return;}
  let alive=true;const controller=new AbortController();setLoading(true);setError('');
  (async()=>{const identity=await api<Session>('/session');if(identity.id!==session.id||identity.mustChangePassword||!identity.isSuperAdmin&&identity.tenantId!==tenant||!can(identity,'tax-regimes','read'))throw new ApiError('forbidden',403);
   const query=new URLSearchParams({search:filters.search,page:String(filters.page),pageSize:'25'});if(filters.country)query.set('country_id',filters.country);if(filters.type)query.set('tax_type_id',filters.type);if(filters.active)query.set('is_active',filters.active);
   const [result,lookups]=await Promise.all([api<{items:CompanyTaxRegime[];total:number;page:number;pageSize:number}>(scope('/tax/regimes?'+query),'GET',undefined,{signal:controller.signal}),api<CompanyTaxLookups>(scope('/tax/company-lookups'),'GET',undefined,{signal:controller.signal})]);if(!alive)return;
   setRows(result.items);setTotal(result.total);setRefs(lookups);if(!result.items.length&&filters.page>1)change({page:filters.page-1});
  })().catch(e=>{if(alive)setError(e instanceof ApiError&&t.has(e.code)?t(e.code):onError(e));}).finally(()=>{if(alive)setLoading(false);});return()=>{alive=false;controller.abort();};
 },[key,readable,scope,filters.search,filters.country,filters.type,filters.active,filters.page,revision]);
 function select(id:string,value:string,items:{value:string;label:string}[],field:'country'|'type'|'active'){return <div className="space-y-2"><Label htmlFor={`tax-regime-${id}`}>{t(id)}</Label><Select value={value||'__all__'} onValueChange={value=>change({[field]:value==='__all__'?'':value,page:1})}><SelectTrigger id={`tax-regime-${id}`} className="w-full"><SelectValue/></SelectTrigger><SelectContent><SelectItem value="__all__">{t('all')}</SelectItem>{items.map(x=><SelectItem key={x.value} value={x.value}>{x.label}</SelectItem>)}</SelectContent></Select></div>;}
 if(!tenant)return <p>{a('selectTenant')}</p>;
 if(!readable)return null;
 return <section id="tax-regimes-section" className="space-y-3" aria-busy={loading}><p className="text-sm text-muted-foreground">{t('readonlyHint')}</p>{error&&<p role="alert" className="text-destructive">{error}</p>}<Card className="gap-0 overflow-hidden py-0"><div className="flex items-start border-b"><div className="min-w-0 flex-1"><FilterBar id="tax-regime-filters" expanded={filters.expanded} onExpandedChange={expanded=>change({expanded})} fields={[
  {key:'search',grow:true,minWidth:200,content:<div className="space-y-2"><Label htmlFor="tax-regime-search">{a('search')}</Label><Input id="tax-regime-search" maxLength={200} value={filters.search} onChange={e=>change({search:e.target.value,page:1})}/></div>},
  {key:'country',minWidth:180,content:select('country',filters.country,refs.countries.map(x=>({value:x.id,label:`${x.iso_code??''} ${x.name??''}`})),'country')},
  {key:'type',minWidth:160,content:select('type',filters.type,refs.types.map(x=>({value:x.id,label:`${x.code??''} ${x.name??''}`})),'type')},
  {key:'active',minWidth:140,content:select('active',filters.active,[{value:'true',label:t('active')},{value:'false',label:t('inactive')}],'active')}
 ]}/></div><div className="flex shrink-0 items-center gap-2 p-4 pt-10"><span className="text-sm tabular-nums">{total}</span><Button type="button" id="tax-regime-refresh" size="icon" variant="ghost" aria-label={a('refresh')} disabled={loading} onClick={()=>setRevision(x=>x+1)}><RefreshCw size={16}/></Button></div></div>
 <div className="table-scroll"><Table id="tax-regime-table" data-testid="tax-regime-table"><TableHeader><TableRow>{['country','type','code','name','active','support','valid_from','valid_to'].map(x=><TableHead key={x}>{t(x)}</TableHead>)}</TableRow></TableHeader><TableBody>{!rows.length&&<TableRow><TableCell colSpan={8}>{loading?a('loading'):a('empty')}</TableCell></TableRow>}{rows.map(row=><TableRow key={row.id} data-regime-id={row.id}><TableCell>{String(row.country_iso_code??refs.countries.find(x=>x.id===row.country_id)?.iso_code??'—')}</TableCell><TableCell>{String(row.tax_type_code??refs.types.find(x=>x.id===row.tax_type_id)?.code??'—')}</TableCell><TableCell>{row.code}</TableCell><TableCell className="min-w-48 whitespace-normal">{row.name}</TableCell><TableCell><Badge variant={row.is_active?'default':'secondary'}>{t(row.is_active?'active':'inactive')}</Badge></TableCell><TableCell><Badge variant={row.is_supported?'default':'secondary'}>{t(row.is_supported?'supported':'unsupported')}</Badge></TableCell><TableCell>{row.valid_from}</TableCell><TableCell>{row.valid_to??'—'}</TableCell></TableRow>)}</TableBody></Table></div>
 <div className="pagination"><span>{a('page')} {filters.page} {a('of')} {Math.max(1,Math.ceil(total/25))}</span><div><Button type="button" variant="outline" disabled={loading||filters.page<=1} onClick={()=>change({page:filters.page-1})}>{a('previous')}</Button><Button type="button" variant="outline" disabled={loading||filters.page*25>=total} onClick={()=>change({page:filters.page+1})}>{a('next')}</Button></div></div></Card></section>;
}
