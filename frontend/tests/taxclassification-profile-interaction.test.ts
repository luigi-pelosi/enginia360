import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import React from 'react';
import ts from 'typescript';
import {createTranslator} from 'next-intl';
import * as model from '../lib/model.ts';
import * as tax from '../lib/tax-profiles.ts';
class ErrorResponse extends Error {code:string;status:number;constructor(code:string,status:number){super(code);this.code=code;this.status=status;}}
const session:model.Session={id:'u',username:'ada',displayName:'Ada',preferredLanguage:'it',isSuperAdmin:false,tenantId:'t',mustChangePassword:false,permissions:['catalog-items.read','tax-item-profiles.read','tax-item-profiles.assign','tax-item-profiles.schedule']};
const draft:tax.TaxProfileDraft={country_id:'it',tax_type_id:'vat',item_tax_classification_id:'std',valid_from:'2026-01-01',valid_to:null};
const page:tax.TaxProfilePage={items:[],total:0,page:1,pageSize:25,version:0};
const refs={countries:[{id:'it',name:'Italia',is_active:true}],types:[{id:'vat',code:'VAT',name:'IVA',is_active:true}],classifications:[{id:'std',country_id:'it',tax_type_id:'vat',code:'STD',name:'Standard',is_active:true}]};
function find(node:any,predicate:(node:any)=>boolean):any {if(!node||typeof node!=='object')return;if(predicate(node))return node;for(const child of [node.props?.children,...(node.props?.fields??[]).map((x:any)=>x.content)].flat(Infinity)){const result=find(child,predicate);if(result)return result;}}
function harness(saved:any={},handler:(path:string,method:string,body:any)=>any=()=>undefined,identity=session,storage=new Map<string,string>()) {
 const key=tax.taxProfileKey(identity.id,'t','item',saved.subjectId===null?'new':'r');if(saved.editor||saved.pending)storage.set(key,JSON.stringify(saved));
 let staged:tax.TaxProfileDraft[]=saved.staged??[];
 const slots:any[]=[],effectSlots:any[]=[],effects:any[]=[],calls:{path:string;method:string;body:any}[]=[];
 let cursor=0,dirty=true,tree:any;
 const messages=JSON.parse(readFileSync(new URL('../messages/it.json',import.meta.url),'utf8'));messages.taxProfiles={"title": "Fiscalità", "assign": "Assegna nuovo profilo", "schedule": "Programma sostituzione", "stage": "Aggiungi alla bozza", "country_id": "Paese fiscale", "tax_type_id": "Tipo imposta", "classification": "Classificazione", "item_tax_classification_id": "Classificazione articolo", "partner_tax_classification_id": "Classificazione Business Partner", "valid_from": "Valido dal", "valid_to": "Valido fino al (incluso)", "atDate": "Alla data", "effective": "In vigore", "previewDate": "Data di consultazione", "empty": "Nessun profilo fiscale. L'assenza non impedisce la creazione.", "inactiveClassification": "Classificazione non attiva", "independentHint": "Le modifiche ai profili fiscali vengono salvate subito, senza salvare gli altri dati del soggetto. Lo storico non è modificabile né eliminabile.", "stagingHint": "I profili sono facoltativi e verranno salvati atomicamente alla prima creazione del soggetto. Il paese è il contesto fiscale, non la residenza.", "assignHint": "Crea un nuovo intervallo. Le sovrapposizioni sono rifiutate: nessun profilo precedente verrà chiuso automaticamente.", "scheduleHint": "Sostituisce il profilo coprente: chiude il precedente il giorno prima dell'inizio e inserisce il nuovo profilo nella stessa operazione.", "invalidDate": "Inserire date di calendario valide.", "invalidRange": "La data finale non può precedere quella iniziale.", "classificationUnavailable": "Selezionare paese, tipo e classificazione attivi e compatibili.", "uncertain": "Esito da verificare. La richiesta non sarà ripetuta automaticamente. Rileggere lo storico prima di chiudere questa operazione.", "review": "Rileggi storico", "acknowledge": "Conferma verifica e chiudi operazione", "storageUnavailable": "Impossibile conservare la bozza in questa scheda.", "stale_version": "Il profilo è cambiato. La bozza conserva il token originale: annullare e riaprire l'operazione dopo la verifica.", "tax_profile_overlap": "L'intervallo si sovrappone a un profilo esistente. Usare esplicitamente Programma sostituzione quando appropriato.", "tax_profile_invalid_range": "Intervallo di validità non valido."};
 const require=createRequire(import.meta.url);
 const module={exports:{} as any};
 const scope=(path:string)=>path+(path.includes('?')?'&':'?')+'tenantId=t';
 const ui=new Proxy({},{get:(_,name)=>{const fn=(props:any)=>React.createElement('div',props);Object.defineProperty(fn,'name',{value:String(name)});return fn;}});
 const resolve=(name:string):any=>{
  if(name==='react')return {...React,useState:(initial:any)=>{const index=cursor++;if(!(index in slots))slots[index]=typeof initial==='function'?initial():initial;return [slots[index],(next:any)=>{const value=typeof next==='function'?next(slots[index]):next;if(!Object.is(slots[index],value)){slots[index]=value;dirty=true;}}];},useRef:(initial:any)=>{const i=cursor++;return slots[i]??(slots[i]={current:initial});},useEffect:(fn:any,deps:any[])=>{const i=cursor++,old=effectSlots[i];if(!old||deps.some((v,j)=>!Object.is(v,old.deps[j])))effects.push(()=>{old?.cleanup?.();effectSlots[i]={deps,cleanup:fn()};});}};
  if(name==='next-intl')return {useTranslations:(namespace:string)=>createTranslator({locale:'it',messages,namespace})};
  if(name==='@/lib/model')return model;if(name==='@/lib/tax-profiles')return tax;
  if(name==='@/lib/catalog')return {readCatalog:(storage:any,key:string)=>JSON.parse(storage.getItem(key)||'null'),storeCatalog:(storage:any,key:string,value:any)=>{if(value===null)storage.removeItem(key);else storage.setItem(key,JSON.stringify(value));return true;}};
  if(name.startsWith('@/components/ui/'))return ui;
  if(name==='@/lib/api')return {ApiError:ErrorResponse,api:async(path:string,method='GET',body:any)=>{
   calls.push({path,method,body});const custom=await handler(path,method,body);if(custom!==undefined)return custom;
   if(path==='/session')return identity;
   if(path.startsWith('/tax/classification-lookups'))return refs;
   if(path.startsWith('/tax/items/r/profiles'))return page;
   throw new Error('Unexpected '+path);
  }};
  return require(name);
 };
 const code=ts.transpileModule(readFileSync(new URL('../components/tax-profiles.tsx',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
 runInNewContext(code,{module,exports:module.exports,require:resolve,sessionStorage:{getItem:(k:string)=>storage.get(k)??null,setItem:(k:string,v:string)=>storage.set(k,v),removeItem:(k:string)=>storage.delete(k)},console,AbortController,URLSearchParams});
 function render(){cursor=0;dirty=false;tree=module.exports.TaxProfiles({kind:'item',subjectId:saved.subjectId===null?null:'r',session:identity,tenantId:'t',scope,onError:(e:any)=>e.code||e.message,staged,onStagedChange:(rows:tax.TaxProfileDraft[])=>{staged=rows;dirty=true;},disabled:saved.disabled??false});}
 async function settle(){for(let i=0;i<40;i++){if(dirty)render();while(effects.length)effects.shift()();await new Promise(resolve=>setImmediate(resolve));if(!dirty&&!effects.length)break;}return tree;}
 return {settle,calls,storage,key,byId:(id:string)=>find(tree,n=>n.props?.id===id),byTest:(id:string)=>find(tree,n=>n.props?.['data-testid']===id),find:(p:any)=>find(tree,p),get state(){return slots[0] as tax.TaxProfileEditor|null;},get staged(){return staged;},get tree(){return tree;},unmount(){for(const effect of effectSlots)effect?.cleanup?.();}};
}

const submit=(h:any)=>h.byTest('tax-profile-form').props.onSubmit({preventDefault(){},stopPropagation(){}});
test('new subject stages canonical optional profiles with assign-only authority',async()=>{
 const h=harness({subjectId:null},()=>undefined,{...session,permissions:['catalog-items.create','tax-item-profiles.assign']});await h.settle();
 h.byId('tax-profile-assign').props.onClick();await h.settle();
 assert.equal(h.state?.values.item_tax_classification_id,'std');
 await submit(h);await h.settle();assert.equal(h.staged.length,1);assert.equal(h.calls.some(c=>c.method==='POST'),false);
 assert.equal(h.calls.some(c=>c.path.startsWith('/tax/items/')),false);h.unmount();
});
test('existing profile assignment is independent of base update permission and sends zero stream token',async()=>{
 let version=0;
 const h=harness({},(path,method,body)=>{if(method==='POST'){assert.equal(body.expectedVersion,0);version=1;return {...page,version};}if(path.startsWith('/tax/items/r/profiles'))return {...page,version};});await h.settle();
 h.byId('tax-profile-assign').props.onClick();await h.settle();await submit(h);await h.settle();
 const post=h.calls.find(c=>c.method==='POST')!;assert.ok(post.path.startsWith('/tax/items/r/profiles?'));assert.equal(post.body.values.item_tax_classification_id,'std');
 assert.equal(h.calls.some(c=>c.path.includes('/catalog/')),false);assert.equal(h.state,null);assert.equal(JSON.parse(h.storage.get(h.key)!).pending,null);h.unmount();
});
test('schedule is an explicit distinct operation with the original subject-stream token',async()=>{
 let version=7;
 const h=harness({},(path,method)=>{if(method==='POST'){version=8;return {...page,version};}if(path.startsWith('/tax/items/r/profiles'))return {...page,version};});await h.settle();
 h.byId('tax-profile-schedule').props.onClick();await h.settle();await submit(h);await h.settle();
 const post=h.calls.find(c=>c.method==='POST')!;assert.ok(post.path.includes('/profiles/schedule?'));assert.equal(post.body.expectedVersion,7);assert.equal(h.state,null);h.unmount();
});
test('stale profile drafts survive remount with their original token, never silently rebase',async()=>{
 const h=harness({editor:{values:draft,operation:'assign',expectedVersion:2}},(path,method)=>{if(method==='POST')throw new ErrorResponse('tax_profile_stale_version',409);if(path.startsWith('/tax/items/r/profiles'))return {...page,version:9};});await h.settle();
 assert.equal(h.state?.expectedVersion,2);await submit(h);await h.settle();assert.equal(h.state?.expectedVersion,2);
 h.unmount();const recovered=harness({},()=>undefined,session,h.storage);await recovered.settle();assert.equal(recovered.state?.expectedVersion,2);assert.equal(recovered.state?.values.valid_from,'2026-01-01');recovered.unmount();
});
test('accepted write with mismatching readback keeps its marker and cannot be repeated after refresh',async()=>{
 let posted=false;
 const h=harness({},(path,method)=>{if(method==='POST'){posted=true;return {...page,version:1};}if(path.startsWith('/tax/items/r/profiles'))return {...page,version:posted?2:0};});await h.settle();h.byId('tax-profile-assign').props.onClick();await h.settle();await submit(h);await h.settle();
 assert.equal(JSON.parse(h.storage.get(h.key)!).pending.committedVersion,1);assert.equal(h.byId('tax-profile-assign').props.disabled,true);h.unmount();
 const recovered=harness({},()=>undefined,session,h.storage);await recovered.settle();assert.equal(recovered.byId('tax-profile-assign').props.disabled,true);assert.equal(recovered.calls.some(c=>c.method==='POST'),false);recovered.unmount();
});
test('ordinary in-flight assignment keeps its editor dialog mounted until authoritative readback',async()=>{
 let release:(value:any)=>void=()=>{};let version=0;const held=new Promise(resolve=>{release=resolve;});
 const h=harness({},(path,method)=>{if(method==='POST')return held;if(path.startsWith('/tax/items/r/profiles'))return {...page,version};});await h.settle();h.byId('tax-profile-assign').props.onClick();await h.settle();const write=submit(h);await h.settle();
 assert.equal(h.find((n:any)=>n.type?.name==='Dialog').props.open,true);assert.equal(h.byId('tax-profile-save').props.disabled,true);
 version=1;release({...page,version});await write;await h.settle();assert.equal(h.state,null);h.unmount();
});
test('fresh authority is checked before sending a profile write',async()=>{
 const h=harness({},path=>path==='/session'?{...session,permissions:['catalog-items.read','tax-item-profiles.read']}:undefined);await h.settle();h.byId('tax-profile-assign').props.onClick();await h.settle();await submit(h);await h.settle();assert.equal(h.calls.some(c=>c.method==='POST'),false);assert.ok(h.state);h.unmount();
});
test('history is paginated, readonly, and retains inactive classifications',async()=>{
 const h=harness({},path=>path.startsWith('/tax/items/r/profiles')?{...page,total:26,items:[{...draft,id:'history',classification_code:'OLD',classification_name:'Historic',classification_is_active:false}]}:undefined,{...session,permissions:['catalog-items.read','tax-item-profiles.read']});await h.settle();assert.equal(h.byId('tax-profile-assign'),undefined);assert.equal(h.byId('tax-profile-schedule'),undefined);assert.equal(h.calls.some(c=>c.method==='DELETE'),false);
 const next=h.find((n:any)=>n.props?.['aria-label']==='Successiva');assert.ok(next);next.props.onClick();await h.settle();assert.ok(h.calls.some(c=>c.path.includes('page=2')));h.unmount();
});
