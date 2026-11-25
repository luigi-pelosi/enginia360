import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogHarness,catalogSession,findCatalog} from './catalog-harness.ts';
const api=(p:string)=>p==='/session'?catalogSession:{mode:'AUTO',prefix:p.includes('SERVICE')?'SRV-':'ART-',padding:6,nextNumber:1,version:3};
test('numbering defaults to all and combines search with the four configuration filters',async()=>{
 const h=catalogHarness('catalog-numbering',api);await h.settle();
 assert.equal(h.state.kind,'ALL');assert.ok(h.action('Modifica Bene materiale'));assert.ok(h.action('Modifica Servizio'));assert.ok(h.action('Modifica Bene immateriale'));assert.ok(h.action('Modifica Onere accessorio'));
 const select=findCatalog(h.tree,n=>n.props?.onValueChange&&n.props.value==='ALL');assert.ok(select);assert.ok(findCatalog(select,n=>n.props?.value==='ALL'));
 select.props.onValueChange('SERVICE');await h.settle();assert.equal(h.action('Modifica Bene materiale'),undefined);assert.ok(h.action('Modifica Servizio'));
 findCatalog(h.tree,n=>n.props?.onValueChange&&n.props.value==='SERVICE').props.onValueChange('ALL');await h.settle();
 assert.ok(h.byId('catalog-search'));assert.ok(h.action('Modifica Bene materiale'));assert.ok(h.action('Modifica Servizio'));
 h.byId('catalog-search').props.onChange({target:{value:'Servizio'}});await h.settle();
 assert.equal(h.action('Modifica Bene materiale'),undefined);assert.ok(h.action('Modifica Servizio'));
 findCatalog(h.tree,n=>n.props?.onValueChange&&n.props.value==='ALL').props.onValueChange('GOOD');await h.settle();
 assert.equal(h.state.search,'Servizio');assert.equal(h.action('Modifica Bene materiale'),undefined);assert.equal(h.action('Modifica Servizio'),undefined);
 findCatalog(h.tree,n=>n.props?.onValueChange&&n.props.value==='GOOD').props.onValueChange('SERVICE');await h.settle();assert.ok(h.action('Modifica Servizio'));
});

test('legacy filters reset once without losing editor or pending; new preferences survive refresh',async()=>{
 const storage=new Map<string,string>();const seed=catalogHarness('catalog-numbering',api,storage);const key=seed.helpers.catalogKey('u','t','catalog-numbering');
 const editor={id:'SERVICE',version:3,values:{prefix:'draft'},original:{prefix:'old'}};
 storage.set(key,JSON.stringify({kind:'SERVICE',search:'legacy',editor}));storage.set(key+':pending',JSON.stringify({kind:'SERVICE',method:'PUT',id:'SERVICE',values:{},version:3}));
 const h=catalogHarness('catalog-numbering',api,storage);await h.settle();assert.equal(h.state.kind,'ALL');assert.equal(h.state.search,'');assert.equal(h.state.editor.values.prefix,'draft');assert.ok(storage.has(key+':pending'));
 findCatalog(h.tree,n=>n.props?.onValueChange&&n.props.value==='ALL').props.onValueChange('GOOD');await h.settle();h.unmount();
 const refreshed=catalogHarness('catalog-numbering',api,storage);await refreshed.settle();assert.equal(refreshed.state.kind,'GOOD');assert.equal(refreshed.state.editor.id,'SERVICE');assert.ok(storage.has(key+':pending'));
});
