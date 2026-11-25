import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogHarness,catalogSession,findCatalog} from './catalog-harness.ts';
const kinds=['GOOD','INTANGIBLE','SERVICE','CHARGE'];
const labels=['Bene materiale','Bene immateriale','Servizio','Onere accessorio'];
const config=(path:string)=>({mode:'AUTO',prefix:path.includes('INTANGIBLE')?'IMM-':path.includes('CHARGE')?'ONR-':path.includes('SERVICE')?'SRV-':'ART-',padding:6,nextNumber:1,version:3});
const server=(path:string,method:string,body:any)=>path==='/session'?catalogSession:method==='POST'?{id:'new',...body.values,version:1}:path.startsWith('/catalog/numbering')?config(path):{items:[],total:0};
function select(h:any,id:string){return findCatalog(h.tree,n=>n.props?.onValueChange&&findCatalog(n,c=>c.props?.id===id));}
test('type creation offers four exact natures and nonphysical stock is false and disabled',async()=>{
 for(const kind of kinds){const h=catalogHarness('catalog-types',server);await h.settle();await h.byId('catalog-new').props.onClick();await h.settle();const choice=select(h,'catalog-kind');for(const value of kinds)assert.ok(findCatalog(choice,n=>n.props?.value===value));choice.props.onValueChange(kind);await h.settle();assert.equal(h.byId('catalog-default_track_stock').props.checked,kind==='GOOD');assert.equal(h.byId('catalog-default_track_stock').props.disabled,kind!=='GOOD');h.submit();await h.settle();const values=h.calls.find(c=>c.method==='POST')!.body.values;assert.equal(values.kind,kind);assert.equal(values.default_track_stock,kind==='GOOD');assert.equal(values.default_sellable,true);assert.equal(values.default_purchasable,true);h.unmount();}
});
test('numbering shows four independent configurations with exact localized labels and payload query',async()=>{
 const h=catalogHarness('catalog-numbering',server);await h.settle();assert.equal(h.calls.filter(c=>c.path.startsWith('/catalog/numbering')).length,4);for(const label of labels)assert.ok(h.action('Modifica '+label));
 for(const [i,kind] of kinds.entries()){await h.action('Modifica '+labels[i]).props.onClick();await h.settle();assert.equal(h.byId('catalog-padding').props.value,'6');h.submit();await h.settle();assert.ok(h.calls.some(c=>c.method==='PUT'&&c.path.includes('kind='+kind)));}h.unmount();
});
for(const [locale,names] of [['it',labels],['en',['Tangible good','Intangible asset','Service','Ancillary charge']]] as const)test(`numbering ${locale} search and filter recover each nature without writing`,async()=>{
 for(const [i,kind] of kinds.entries()){
  const h=catalogHarness('catalog-numbering',server,new Map(),locale);await h.settle();findCatalog(h.tree,n=>n.props?.onValueChange&&n.props.value==='ALL').props.onValueChange(kind);await h.settle();h.byId('catalog-search').props.onChange({target:{value:names[i]}});await h.settle();assert.ok(h.action((locale==='it'?'Modifica ':'Edit ')+names[i]));h.unmount();
  const recovered=catalogHarness('catalog-numbering',server,h.storage,locale);await recovered.settle();assert.equal(recovered.state.kind,kind);assert.equal(recovered.state.search,names[i]);assert.equal(recovered.calls.some(c=>c.method!=='GET'),false);recovered.unmount();
 }
});
test('type list kind filter exposes all four and sends selected kind',async()=>{
 const h=catalogHarness('catalog-types',server);await h.settle();const filter=findCatalog(h.tree,n=>n.props?.onValueChange&&n.props.value==='ALL');assert.ok(filter);for(const kind of kinds)assert.ok(findCatalog(filter,n=>n.props?.value===kind));filter.props.onValueChange('INTANGIBLE');await h.settle();assert.ok(h.calls.some(c=>c.path.startsWith('/catalog/types?')&&c.path.includes('kind=INTANGIBLE')));h.unmount();
});
