import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogHarness,catalogSession,CatalogApiError,findCatalog} from './catalog-harness.ts';
const kinds=['GOOD','INTANGIBLE','SERVICE','CHARGE'];
const row={id:'type-a',name:'Merce',code:'M',kind:'GOOD',default_sellable:true,default_purchasable:true,default_track_stock:true,is_active:true,version:4};
const permissions=['catalog-types.read','catalog-types.update'];
function fixture(options:{flag?:unknown;missing?:boolean;storage?:Map<string,string>;locale?:string;version?:number;handler?:(p:string,m:string,b:any)=>any;create?:boolean}={}) {
 const session={...catalogSession,permissions:options.create?[...permissions,'catalog-types.create']:permissions};
 let record={...row,version:options.version??4,...options.missing?{}:{canChangeKind:options.flag??true}};
 return catalogHarness('catalog-types',(p,m,b)=>{
  const override=options.handler?.(p,m,b);if(override!==undefined)return override;
  if(p==='/session')return session;
  if(m==='PUT'||m==='POST'){record={...record,...b.values,version:record.version+1};return record;}
  if(p.startsWith('/catalog/types/type-a?'))return record;
  return {items:[row],total:1};
 },options.storage,options.locale??'it',session);
}
const choice=(h:ReturnType<typeof fixture>)=>findCatalog(h.tree,n=>n.props?.onValueChange&&findCatalog(n,c=>c.props?.id==='catalog-kind'));
async function open(h:ReturnType<typeof fixture>,readonly=false){await h.settle();await h.action((readonly?'Dettagli ':'Modifica ')+'Merce').props.onClick();await h.settle();}
const writes=(h:ReturnType<typeof fixture>)=>h.calls.filter(c=>c.method!=='GET');
for(const flag of [false,undefined,'true',1])test(`used or missing/nonboolean metadata fails closed (${String(flag)}); other fields remain editable`,async()=>{
 const h=fixture({flag,missing:flag===undefined});await open(h);assert.equal(choice(h).props.disabled,true);
 h.byId('catalog-name').props.onChange({target:{value:'Updated'}});await h.settle();h.byId('catalog-code').props.onChange({target:{value:'U'}});await h.settle();h.byId('catalog-default_sellable').props.onCheckedChange(false);await h.settle();h.submit();await h.settle();assert.equal(writes(h).length,1);assert.equal(writes(h)[0].body.values.name,'Updated');assert.equal(writes(h)[0].body.values.code,'U');assert.equal(writes(h)[0].body.values.default_sellable,false);assert.equal(Object.hasOwn(writes(h)[0].body.values,'kind'),false);h.unmount();
});
test('read-only remains disabled even for unused type',async()=>{const h=fixture();await open(h,true);assert.equal(choice(h).props.disabled,true);assert.equal(h.byId('catalog-name').props.disabled,true);h.unmount();});
test('new type remains editable without metadata',async()=>{const h=fixture({missing:true,create:true});await h.settle();await h.byId('catalog-new').props.onClick();await h.settle();assert.equal(choice(h).props.disabled,false);h.unmount();});
test('refresh replaces eligibility metadata without replacing draft, original comparison or version',async()=>{
 let flag=true;const h=fixture({handler:(p,m)=>m==='GET'&&p.startsWith('/catalog/types/type-a?')?{...row,canChangeKind:flag}:undefined});await open(h);
 choice(h).props.onValueChange('SERVICE');await h.settle();h.byId('catalog-name').props.onChange({target:{value:'Draft'}});await h.settle();flag=false;
 h.action('Aggiorna').props.onClick();await h.settle();assert.equal(choice(h).props.disabled,true);assert.equal(h.state.editor.values.kind,'SERVICE');assert.equal(h.state.editor.values.name,'Draft');assert.equal(h.state.editor.original.kind,'GOOD');assert.equal(h.state.editor.version,4);assert.equal(writes(h).length,0);h.unmount();
});
test('recovery accepts fresh true eligibility despite stored false metadata',async()=>{
 const storage=new Map<string,string>(),h=fixture({storage,flag:false});await open(h);h.byId('catalog-name').props.onChange({target:{value:'Draft'}});await h.settle();h.unmount();
 const recovered=fixture({storage,flag:true});await recovered.settle();assert.equal(choice(recovered).props.disabled,false);assert.equal(recovered.state.editor.values.name,'Draft');assert.equal(recovered.state.editor.original.canChangeKind,false);assert.equal(recovered.state.editor.version,4);assert.equal(writes(recovered).length,0);recovered.unmount();
});
for(const version of [4,5])test(`recovery ignores stored eligibility and preserves original concurrency token (server v${version})`,async()=>{
 const storage=new Map<string,string>(),h=fixture({storage});await open(h);choice(h).props.onValueChange('INTANGIBLE');await h.settle();h.unmount();
 const recovered=fixture({storage,flag:false,version});recovered.render();assert.equal(choice(recovered).props.disabled,true);await recovered.settle();assert.equal(choice(recovered).props.disabled,true);assert.equal(recovered.state.editor.values.kind,'INTANGIBLE');assert.equal(recovered.state.editor.original.kind,'GOOD');assert.equal(recovered.state.editor.version,4);assert.equal(recovered.byId('catalog-save').props.disabled,version!==4);assert.equal(writes(recovered).length,0);recovered.unmount();
});
for(const [locale,message] of [['it','La natura non può essere modificata perché la tipologia è associata ad articoli o servizi esistenti.'],['en','The nature cannot be changed because this type is associated with existing goods or services.']])test(`concurrent immutable_item_kind conflict is localized (${locale}) and preserves draft without retry`,async()=>{
 const h=fixture({locale,handler:(_p,m)=>{if(m==='PUT')throw new CatalogApiError('immutable_item_kind',409);}});await h.settle();await h.action((locale==='it'?'Modifica ':'Edit ')+'Merce').props.onClick();await h.settle();choice(h).props.onValueChange('SERVICE');await h.settle();h.submit();await h.settle();
 assert.ok(findCatalog(h.tree,n=>n.props?.role==='alert'&&n.props.children===message));assert.equal(h.state.editor.values.kind,'SERVICE');assert.equal(h.state.editor.original.kind,'GOOD');assert.equal(h.state.editor.version,4);assert.equal([...h.storage.keys()].some(k=>k.endsWith(':pending')),false);await h.settle();assert.equal(writes(h).length,1);h.unmount();
});
test('pending and busy guards disable kind and prevent duplicate writes',async()=>{
 let reject!:(e:Error)=>void;const h=fixture({handler:(_p,m)=>m==='PUT'?new Promise((_resolve,r)=>{reject=r;}):undefined});await open(h);choice(h).props.onValueChange('SERVICE');await h.settle();h.submit();await h.settle();assert.equal(choice(h).props.disabled,true);h.submit();await h.settle();assert.equal(writes(h).length,1);reject(new CatalogApiError('network_error',0));await h.settle();assert.equal(choice(h).props.disabled,true);h.submit();await h.settle();assert.equal(writes(h).length,1);h.unmount();
});
for(const kind of kinds)test(`unused existing type permits ${kind} with versioned payload and read/update permissions only`,async()=>{
 const h=fixture();await open(h);assert.equal(choice(h).props.disabled,false);
 for(const option of kinds)assert.ok(findCatalog(choice(h),n=>n.props?.value===option));
 choice(h).props.onValueChange(kind);await h.settle();assert.equal(choice(h).props.value,kind);
 assert.equal(h.byId('catalog-default_track_stock').props.checked,kind==='GOOD');
 assert.equal(h.byId('catalog-default_track_stock').props.disabled,kind!=='GOOD');
 h.submit();await h.settle();assert.equal(writes(h).length,1);assert.equal(writes(h)[0].method,'PUT');assert.equal(writes(h)[0].body.expectedVersion,4);assert.equal(writes(h)[0].body.values.kind,kind);assert.equal(writes(h)[0].body.values.default_track_stock,kind==='GOOD');assert.equal(Object.hasOwn(writes(h)[0].body.values,'canChangeKind'),false);
 assert.equal(h.calls.some(c=>c.path.includes('deletion-check')||c.path.startsWith('/catalog/items')),false);h.unmount();
});
