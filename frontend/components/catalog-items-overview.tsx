"use client";
import {useEffect,useRef,useState,type ReactNode} from 'react';
import {useTranslations} from 'next-intl';
import {Button} from '@/components/ui/button';
import {CatalogItemWorkspace} from '@/components/catalog-item-workspace';
import {CompanyCatalogItems} from '@/components/company-catalog-items';
import {api} from '@/lib/api';
import {can,type Session} from '@/lib/model';
import {catalogKey,readCatalog,storeCatalog} from '@/lib/catalog';
type View='identity'|'company';
type Props={session:Session;tenantId:string;scope:(path:string)=>string;onError:(error:unknown)=>string;heading:ReactNode};
export function CatalogItemsOverview({session,tenantId,scope,onError,heading}:Props){
 const t=useTranslations('catalogItems');
 const tenant=session.isSuperAdmin?tenantId:session.tenantId||'';
 const key=catalogKey(session.id,tenant,'catalog-items-view');
 const [selection,setSelection]=useState<{key:string;view:View}|null>(null);
 const [validated,setValidated]=useState<{key:string;session:Session;source:Session}|null>(null);
 const [error,setError]=useState('');
 const generation=useRef(0);
 const permits=(authority:Session,view:View)=>!!tenant&&can(session,view==='identity'?'catalog-items':'catalog-item-companies','read')&&can(authority,view==='identity'?'catalog-items':'catalog-item-companies','read');
 async function validate(wanted?:View){
  const request=++generation.current;
  // Non montare una vista autorizzata in precedenza durante la nuova verifica dei permessi.
  setValidated(null);
  try{
   const fresh=await api<Session>('/session');
   if(request!==generation.current)return;
   if(fresh.id!==session.id||(!fresh.isSuperAdmin&&fresh.tenantId!==tenant))return;
   const saved=typeof sessionStorage==='undefined'?null:readCatalog<View>(sessionStorage,key);
   const candidate=wanted??(saved==='company'?'company':'identity');
   const view=permits(fresh,candidate)?candidate:permits(fresh,'identity')?'identity':'company';
   setSelection({key,view});setValidated({key,session:fresh,source:session});setError('');
   if(typeof sessionStorage!=='undefined')storeCatalog(sessionStorage,key,view);
  }catch(e){if(request===generation.current)setError(onError(e));}
 }
 useEffect(()=>{void validate();return()=>{generation.current++;};},[key,session]);
 const authority=validated?.key===key&&validated.source===session?validated.session:null;
 const view=selection?.key===key?selection.view:'identity';
 const identity=!!authority&&permits(authority,'identity'),company=!!authority&&permits(authority,'company');
 function renderToolbar(actions:ReactNode){return <div data-testid="catalog-items-toolbar" className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
  <div className="flex flex-wrap gap-2">
   <Button type="button" variant={view==='identity'?'default':'outline'} data-action="catalog-identity-view" aria-pressed={view==='identity'} disabled={!identity} onClick={()=>validate('identity')}>{t('identity')}</Button>
   <Button type="button" variant={view==='company'?'default':'outline'} data-action="catalog-company-view" aria-pressed={view==='company'} disabled={!company} onClick={()=>validate('company')}>{t('byCompany')}</Button>
  </div>
  <div className="flex flex-wrap items-center justify-end gap-2 sm:ml-auto">{actions}</div>
 </div>;}
 return <div data-catalog-overview="catalog-items" className="space-y-4">
  <div className="page-heading">{heading}</div>
  {!authority&&renderToolbar(null)}
  {error&&<p role="alert">{error}</p>}
  {authority&&view==='identity'&&identity&&<CatalogItemWorkspace session={authority} tenantId={tenant} scope={scope} onError={onError} heading={null} renderToolbar={renderToolbar}/>}
  {authority&&view==='company'&&company&&<CompanyCatalogItems session={authority} tenantId={tenant} scope={scope} onError={onError} heading={<></>} renderToolbar={renderToolbar}/>}
 </div>;
}
