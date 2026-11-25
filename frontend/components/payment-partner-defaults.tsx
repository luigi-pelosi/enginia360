"use client";
import {useEffect, useRef, useState} from "react";
import {useTranslations} from "next-intl";
import {methodCompatible, termCompatible, referenceOptions, type PaymentMethodReference, type PaymentTermReference} from "@/lib/payments";
import {api, ApiError} from "@/lib/api";
import {can, type Session} from "@/lib/model";
import type {CompanyPartner, PartnerRoleCode} from "@/components/business-partner-companies";
import {Button} from "@/components/ui/button";
import {Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter} from "@/components/ui/dialog";
import {Label} from "@/components/ui/label";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";

type Company = {id:string; permissions:string[]};
type Method = PaymentMethodReference;
type Term = PaymentTermReference;
type Defaults = {paymentTermId:string|null; paymentMethodId:string|null; version:number};
export function PaymentPartnerDefaults({businessPartnerId, relations, companies, selectedCompanyId, onClose, session, scope, onError, onSaved}: {businessPartnerId:string; relations:CompanyPartner[]; companies:Company[]; selectedCompanyId:string|null; onClose:()=>void; session:Session; scope:(path:string)=>string; onError:(error:unknown)=>string; onSaved?:()=>void}) {
 const t=useTranslations('payments'), a=useTranslations('app'), p=useTranslations('partnerCompanies');
 const [role,setRole]=useState<PartnerRoleCode>('CUSTOMER');
 const [value,setValue]=useState<Defaults|null>(null), [loadedPath,setLoadedPath]=useState(''), [methods,setMethods]=useState<Method[]>([]), [terms,setTerms]=useState<Term[]>([]);
 const [error,setError]=useState(''), [busy,setBusy]=useState(false), [revision,setRevision]=useState(0), [blocked,setBlocked]=useState(false);
 const lock=useRef(false);
 const company=selectedCompanyId || '';
 const grant=companies.find(x=>x.id===company)?.permissions || [];
 const relation=relations.find(x=>x.company_id===company && x.usable_roles.length && grant.includes('payment-partner-defaults.read'));
 useEffect(()=>{if(relation) setRole(relation.usable_roles[0]);},[company]);
 const path=`/companies/${encodeURIComponent(company)}/business-partners/${encodeURIComponent(businessPartnerId)}/payment-defaults/${role}`;
 useEffect(()=>{setValue(null);setMethods([]);setTerms([]);setError('');setBlocked(false);if(!relation || !relation.usable_roles.includes(role))return;
  let alive=true; const controller=new AbortController(); const get=<T,>(url:string)=>api<T>(scope(url),'GET',undefined,{signal:controller.signal});
  const defaults=get<Defaults>(path);
  const jobs:Promise<void>[]=[];
  if(grant.includes('payment-methods.read')) jobs.push(get<{items:Method[]}>(`/companies/${encodeURIComponent(company)}/payment-methods`).then(x=>{if(alive)setMethods(x.items);}));
  if(grant.includes('payment-terms.read')) jobs.push(get<{items:Term[]}>(`/companies/${encodeURIComponent(company)}/payment-terms`).then(x=>{if(alive)setTerms(x.items);}));
  Promise.all([defaults,...jobs]).then(([value])=>{if(alive){setValue(value as Defaults);setLoadedPath(path);}}).catch(e=>{if(alive){setBlocked(true);setError(onError(e));}});return ()=>{alive=false;controller.abort();};
 },[company,role,businessPartnerId,scope,onError,companies,relations,revision,selectedCompanyId]);
 if(!can(session,'payment-partner-defaults','read'))return null;
 const editable=grant.includes('payment-partner-defaults.update') && grant.includes('payment-methods.read') && grant.includes('payment-terms.read');
 async function save(e:{stopPropagation:()=>void}) {e.stopPropagation();if(!editable||!value||loadedPath!==path||!relation||blocked||lock.current)return;lock.current=true;setBusy(true);setError('');
  try {const saved=await api<Defaults>(scope(path),'PUT',{paymentTermId:value.paymentTermId,paymentMethodId:value.paymentMethodId,expectedVersion:value.version});setValue(saved);onClose();onSaved?.();}
  catch(e){if(e instanceof ApiError && (e.status===0 || e.code==='stale_version')){setBlocked(true);onSaved?.();}setError(onError(e));}finally{lock.current=false;setBusy(false);}
 }
 const select=(id:string,v:string|null,items:{value:string;label:string}[],change:(v:string)=>void,disabled=false)=><Select value={v||'__none__'} disabled={disabled||busy} onValueChange={change}><SelectTrigger id={id} className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="__none__">{a('none')}</SelectItem>{items.map(x=><SelectItem key={x.value} value={x.value}>{x.label}</SelectItem>)}</SelectContent></Select>;
 const direction=role==='CUSTOMER'?'INBOUND':'OUTBOUND';
 if (!selectedCompanyId || !relation) return null;
 return <Dialog open onOpenChange={next=>{if(!next&&!lock.current&&!blocked)onClose();}}><DialogContent aria-describedby={undefined}><DialogHeader><DialogTitle>{t('partnerDefaults')} — {relation.company_name}</DialogTitle></DialogHeader>{error && <p role="alert">{error}</p>}
 {relation && <div className="space-y-2"><Label htmlFor="defaults-role">{t('partnerRole')}</Label>{select('defaults-role',role,relation.usable_roles.map(x=>({value:x,label:p(x)})),v=>{if(v==='CUSTOMER'||v==='SUPPLIER'){setValue(null);setRole(v);}},blocked)}</div>}
 {value && loadedPath===path && relation.usable_roles.includes(role) && <div data-payment-defaults-form={role} className="space-y-3"><fieldset disabled={!editable||blocked||busy} className="grid gap-3 sm:grid-cols-2"><div className="space-y-2"><Label htmlFor="defaults-term">{t('defaultTerm')}</Label>{select('defaults-term',value.paymentTermId,referenceOptions(terms,value.paymentTermId,x=>termCompatible(x,methods,direction),a('disabled')),v=>setValue({...value,paymentTermId:v==='__none__'?null:v}))}</div><div className="space-y-2"><Label htmlFor="defaults-method">{t('method')}</Label>{select('defaults-method',value.paymentMethodId,referenceOptions(methods,value.paymentMethodId,x=>methodCompatible(x,direction),a('disabled')),v=>setValue({...value,paymentMethodId:v==='__none__'?null:v}))}</div></fieldset>{editable && <Button type="button" onClick={save} disabled={busy||blocked}>{a('save')}</Button>}</div>}
 {blocked && <Button type="button" disabled={busy} onClick={()=>{setRevision(x=>x+1);onSaved?.();}}>{a('refresh')}</Button>}<DialogFooter><Button type="button" variant="outline" data-action="cancel-payment-defaults" disabled={busy||blocked} onClick={()=>{if(!lock.current&&!blocked)onClose();}}>{a('cancel')}</Button></DialogFooter></DialogContent></Dialog>;
}

export function PaymentDefaultsSummary({businessPartnerId, relation, permissions, scope, onError, revision}: {businessPartnerId:string; relation:CompanyPartner; permissions:string[]; scope:(path:string)=>string; onError:(error:unknown)=>string; revision:number}) {
 const p=useTranslations('partnerCompanies'), a=useTranslations('app');
 const [values,setValues]=useState<Record<string,string>>({}); const [error,setError]=useState('');
 const roles=relation.usable_roles.join(','); const allowed=permissions.includes('payment-partner-defaults.read') && permissions.includes('payment-terms.read') && permissions.includes('payment-methods.read');
 useEffect(()=>{setValues({});setError('');if(!allowed||!roles)return;let alive=true;const controller=new AbortController();
  const base=`/companies/${encodeURIComponent(relation.company_id)}`;
  Promise.all([api<{items:Term[]}>(scope(`${base}/payment-terms`),'GET',undefined,{signal:controller.signal}),...roles.split(',').map(role=>api<Defaults>(scope(`${base}/business-partners/${encodeURIComponent(businessPartnerId)}/payment-defaults/${role}`),'GET',undefined,{signal:controller.signal}))]).then(([catalog,...defaults])=>{if(!alive)return;const terms=(catalog as {items:Term[]}).items;const result:Record<string,string>={};roles.split(',').forEach((role,i)=>{const id=(defaults[i] as Defaults).paymentTermId;const term=terms.find(t=>t.id===id);result[role]=id?(term ? `${term.code} · ${term.name}` : a('disabled')):a('none');});setValues(result);}).catch(e=>{if(alive)setError(onError(e));});
  return ()=>{alive=false;controller.abort();};
 },[businessPartnerId,relation.company_id,roles,allowed,scope,onError,revision]);
 if(!allowed)return <>—</>;
 if(error)return <span role="alert">{error}</span>;
 return <div>{relation.usable_roles.map(role=><div key={role}>{p(role)}: {values[role] || a('loading')}</div>)}</div>;
}
