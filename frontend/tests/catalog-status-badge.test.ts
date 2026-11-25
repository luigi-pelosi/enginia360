import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogHarness,catalogSession,findCatalog} from './catalog-harness.ts';

const session={...catalogSession,permissions:[...catalogSession.permissions,'catalog-brands.read','catalog-brands.update']};
for(const locale of ['it','en']) for(const resource of ['catalog-units','catalog-categories','catalog-types','catalog-brands']) test(`${resource} displays localized status badges (${locale})`,async()=>{
 const rows=[true,false].map((active,i)=>({id:String(i),name:`Record ${i}`,code:`C${i}`,dimension:'COUNT',kind:'GOOD',is_active:active,version:1}));
 const h=catalogHarness(resource,(p)=>p==='/session'?session:{items:rows,total:2},new Map(),locale,session);await h.settle();
 for(const [i,label] of (locale==='it'?['Attivo','Inattivo']:['Active','Inactive']).entries()) {
  const row=findCatalog(h.tree,n=>n.props?.['data-record-id']===String(i));
  const badge=findCatalog(row,n=>n.type?.name==='Badge');assert.ok(badge,`status badge ${i}`);assert.equal(badge.props.children,label);
 }
});
test('stale summaries show status badges without changing other booleans or edit switch',async()=>{
 const original={id:'r',name:'Merce',code:null,kind:'GOOD',default_sellable:true,default_purchasable:true,default_track_stock:true,is_active:true,version:4};
 const storage=new Map<string,string>();const server=(p:string)=>p==='/session'?catalogSession:p.includes('/r?')?original:{items:[original],total:1};
 const h=catalogHarness('catalog-types',server,storage);await h.settle();await h.action('Modifica Merce').props.onClick();await h.settle();assert.equal(h.byId('catalog-is_active').props.checked,true);h.unmount();
 const restored=catalogHarness('catalog-types',p=>p.includes('/r?')?{...original,is_active:false,version:5}:server(p),storage);await restored.settle();
 const summaries: any[]=[];function visit(n:any){if(!n||typeof n!=='object')return;if(n.type==='dl')summaries.push(n);for(const c of [n.props?.children].flat(Infinity))visit(c);}visit(restored.tree);
 assert.equal(summaries.length,2);for(const [i,label] of ['Attivo','Inattivo'].entries()){const badge=findCatalog(summaries[i],n=>n.type?.name==='Badge');assert.ok(badge);assert.equal(badge.props.children,label);assert.ok(findCatalog(summaries[i],n=>n.type==='dd'&&n.props.children==='Sì'));}
});
