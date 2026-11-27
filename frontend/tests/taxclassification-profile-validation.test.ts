import test from 'node:test';
import assert from 'node:assert/strict';
import * as profiles from '../lib/tax-profiles.ts';
import {taxProfileValues,taxProfileError,taxProfileOptions,taxProfileInitial,taxProfilePath,taxProfileKey,type TaxProfileDraft} from '../lib/tax-profiles.ts';
import {itemCreation,itemEditor} from '../lib/catalog-items.ts';
const lookups={countries:[{id:'it',name:'Italia',is_active:true},{id:'fr',name:'France',is_active:true}],types:[{id:'vat',name:'VAT',is_active:true}],classifications:[{id:'old',country_id:'it',tax_type_id:'vat',name:'Old',is_active:false},{id:'it-standard',country_id:'it',tax_type_id:'vat',name:'Standard',is_active:true},{id:'fr-standard',country_id:'fr',tax_type_id:'vat',name:'Standard',is_active:true}]};
const draft:TaxProfileDraft={country_id:'it',tax_type_id:'vat',item_tax_classification_id:'it-standard',valid_from:'2026-01-01',valid_to:null};
test('profile drafts serialize only canonical fields for their subject kind',()=>{
 assert.deepEqual(taxProfileValues('item',{...draft,partner_tax_classification_id:'foreign',clientId:'local'} as TaxProfileDraft),draft);
 assert.equal(taxProfileValues('partner',{...draft,partner_tax_classification_id:'partner'}).item_tax_classification_id,undefined);
});
test('profile dates are inclusive calendar dates and classification compatibility is mandatory',()=>{
 assert.equal(taxProfileError('item',draft,lookups),null);
 assert.equal(taxProfileError('item',{...draft,valid_to:draft.valid_from},lookups),null);
 assert.equal(taxProfileError('item',{...draft,valid_to:'2025-12-31'},lookups),'invalidRange');
 assert.equal(taxProfileError('item',{...draft,valid_from:'2026-02-30'},lookups),'invalidDate');
 assert.equal(taxProfileError('item',{...draft,item_tax_classification_id:'old'},lookups),'classificationUnavailable');
 assert.equal(taxProfileError('item',{...draft,item_tax_classification_id:'fr-standard'},lookups),'classificationUnavailable');
});
test('admissible defaults use active compatible options without a residency or nature fallback',()=>{
 assert.equal(taxProfileInitial('item',lookups,'2026-01-01').item_tax_classification_id,'it-standard');
 assert.deepEqual(taxProfileOptions(lookups,draft).classifications.map(r=>r.id),['it-standard']);
 assert.equal(taxProfileInitial('item',{...lookups,countries:lookups.countries.map(row=>row.id==='it'?{...row,is_enabled:false}:row)},'2026-01-01').country_id,'fr');
 assert.equal(taxProfileInitial('item',{countries:[],types:[],classifications:[]},'2026-01-01').country_id,'');
 assert.notEqual(taxProfileKey('u','t','item','x'),taxProfileKey('u','t','partner','x'));
 assert.equal(taxProfilePath('partner','a/b'),'/tax/partners/a%2Fb/profiles');
});
test('menu reset clears ordinary drafts only for its user tenant and kind while retaining pending commands',()=>{
 const store=new Map<string,string>();
 const ordinary=taxProfileKey('u','t','item','r'),pending=taxProfileKey('u','t','item','p'),newKey=taxProfileKey('u','t','item','new'),foreign=taxProfileKey('v','t','item','r'),partner=taxProfileKey('u','t','partner','r');
 for(const key of [ordinary,newKey,foreign,partner])store.set(key,JSON.stringify({editor:{values:draft},pending:null}));
 const marker={body:{values:draft,expectedVersion:3},operation:'assign'};store.set(pending,JSON.stringify({editor:{values:draft,expectedVersion:3},pending:marker}));
 const storage={get length(){return store.size;},key:(i:number)=>[...store.keys()][i]??null,getItem:(k:string)=>store.get(k)??null,setItem:(k:string,v:string)=>{store.set(k,v);},removeItem:(k:string)=>{store.delete(k);}};
 assert.equal(typeof profiles.clearTaxProfileDrafts,'function');profiles.clearTaxProfileDrafts(storage,'u','t','item');
 assert.equal(store.has(ordinary),false);assert.equal(store.has(newKey),false);assert.equal(store.has(foreign),true);assert.equal(store.has(partner),true);
 assert.deepEqual(JSON.parse(store.get(pending)!).pending,marker);assert.equal(JSON.parse(store.get(pending)!).editor.expectedVersion,3);
});
test('item create includes optional profiles once, without altering the root revision',()=>{
 const editor=itemEditor({id:'',version:0});
 assert.equal('taxProfiles' in itemCreation(editor),false);
 editor.taxProfiles=[draft];
 assert.deepEqual(itemCreation(editor).taxProfiles,[draft]);
 assert.equal(editor.version,0);
});
