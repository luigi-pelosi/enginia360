import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync,readdirSync} from 'node:fs';
import {harness,session} from './workspace-harness.ts';
import type {Resource} from '../lib/model.ts';
const resources:Resource[]=[{key:'settings',fields:[]},{key:'countries',fields:[]},{key:'cities',fields:[]}];
test('frontend runtime and translations contain no removed provider references',()=>{
 assert.equal(existsSync(new URL('../components/geoapify-settings.tsx',import.meta.url)),false);
 for(const dir of ['components','lib','messages']) {
  const base=new URL(`../${dir}/`,import.meta.url);
  for(const file of readdirSync(base,{recursive:true})) {
   if(!/\.(tsx?|json)$/.test(String(file))) continue;
   assert.doesNotMatch(readFileSync(new URL(String(file),base),'utf8'),/geoapify|openstreetmap/i,String(file));
  }
 }
});
test('opening Settings without grants never requests tenant settings data',async()=>{
 const h=harness('en',{0:{...session,permissions:[]},1:false,5:resources,6:'settings',7:''},(path:string)=>path==='/session'?session:path==='/resources'?resources:{items:[],total:0});
 h.components.default();
 const cleanups=h.effects.map(effect=>effect());
 await new Promise(resolve=>setImmediate(resolve));
 assert.deepEqual(h.apiCalls,['/session','/resources']);
 assert.equal((h.updates[6] as (current:string)=>string)('settings'),'');
 const html=harness('en',{0:{...session,permissions:[]},1:false,5:resources,6:'settings',7:''}).render('default');
 assert.doesNotMatch(html,/aria-label="Settings"|<h1>Settings<\/h1>/);
 for(const cleanup of cleanups) if(typeof cleanup==='function') cleanup();
});
test('Settings has no empty integrations tile even with settings authority',()=>{
 const h=harness('en',{0:{...session,permissions:['settings.read']},1:false,5:resources,6:'settings',7:'tenant'});
 const html=h.render('default');
 assert.doesNotMatch(html,/Integrations|Geoapify/);
 assert.doesNotMatch(html,/<h2[^>]*>Countries<\//);
 assert.doesNotMatch(html,/<h2[^>]*>Cities<\//);
});
for(const locale of ['it','en']) test(`geography catalogs are Settings tiles without a selected tenant (${locale})`,()=>{
 const h=harness(locale,{0:{...session,isSuperAdmin:true,tenantId:null},1:false,5:resources,6:'settings-system',7:''});
 const html=h.render('default');const nav=html.match(/<nav[\s\S]*?<\/nav>/)?.[0]||'';
 assert.match(nav,locale==='it'?/Impostazioni/:/Settings/);
 assert.doesNotMatch(nav,locale==='it'?/Nazioni|Città|Anagrafiche/:/Countries|Cities|Master data/);
 assert.match(html,locale==='it'?/<h2[^>]*>Nazioni<\//:/<h2[^>]*>Countries<\//);
 assert.match(html,locale==='it'?/<h2[^>]*>Città<\//:/<h2[^>]*>Cities<\//);
 assert.doesNotMatch(html,/empty-state/);
});
test('ordinary catalog readers can open Settings without gaining settings data permission',()=>{
 const h=harness('en',{0:{...session,permissions:['countries.read','cities.read']},1:false,5:resources,6:'settings-system',7:'tenant'});
 const html=h.render('default');assert.match(html,/<h2[^>]*>Countries<\//);assert.match(html,/<h2[^>]*>Cities<\//);
 assert.doesNotMatch(html,/<h2[^>]*>Integrations<\//);
});
test('catalog list provides a return to Settings and highlights only its Settings navigation entry',()=>{
 const h=harness('en',{0:{...session,isSuperAdmin:true,tenantId:null},1:false,5:resources,6:'cities',7:''});
 const html=h.render('default');assert.match(html,/Back to System/);const nav=html.match(/<nav[\s\S]*?<\/nav>/)?.[0]||'';
 assert.doesNotMatch(nav,/>Cities</);assert.match(nav,/aria-current="page"/);
});
