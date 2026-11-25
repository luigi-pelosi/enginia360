import test from 'node:test';
import assert from 'node:assert/strict';
import {navigationPath} from '../lib/model.ts';
import {catalogHarness,catalogSession,findCatalog} from './catalog-harness.ts';

test('types-only reader traverses settings catalog, not operational catalog',()=>{
 const s={...catalogSession,permissions:['catalog-types.read']}; const w=catalogHarness().workspace({});
 assert.deepEqual(navigationPath('catalog-types'),['settings','settings-master-data','settings-catalog','catalog-types']);
 for(const key of navigationPath('catalog-types')) assert.equal(w.canOpenResource(s,key),true,key);
 for(const key of ['catalog','catalog-categories','catalog-numbering']) assert.equal(w.canOpenResource(s,key),false,key);
});
for(const locale of ['it','en']) test(`types tile lives only in settings catalog (${locale})`,()=>{
 const s={...catalogSession,permissions:['catalog-types.read','catalog-categories.read','catalog-numbering.read']};
 const resources=['settings','settings-master-data','settings-catalog','catalog','catalog-types','catalog-categories','catalog-numbering'].map(key=>({key,fields:[]}));
 const render=(active:string)=>catalogHarness('catalog-types',()=>null,new Map(),locale).workspace({0:s,1:false,5:resources,6:active,7:'t'}).default();
 const text=(n:any):string=>typeof n==='string'?n:n?.props?[n.props.children].flat(Infinity).map(text).join(' '):'';
 const label=locale==='it'?'Tipologie articolo':'Item types';
 assert.ok(text(render('settings-catalog')).includes(label));
 assert.ok(!text(render('catalog')).includes(label));
 const child=findCatalog(render('catalog-types'),n=>n.props?.resource==='catalog-types'); assert.ok(child);
 const heading=text(child.props.heading); for(const part of locale==='it'?['Impostazioni','Anagrafiche','Catalogo']:['Settings','Master data','Catalog']) assert.ok(heading.includes(part),part);
});
