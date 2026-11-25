import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogHarness, catalogSession, CatalogApiError,findCatalog} from './catalog-harness.ts';
const row={id:'r',name:'Merce',code:null,kind:'GOOD',default_sellable:true,default_purchasable:true,default_track_stock:true,is_active:true,version:4};
function server(path:string,method:string,body:any){if(path==='/session')return catalogSession;if(method==='GET')return path.includes('/r?')?row:{items:[row],total:1};return {...row,...body?.values,version:5};}
test('type edit preserves original revision, omits immutable kind, and reads committed record',async()=>{
 const h=catalogHarness('catalog-types',server);await h.settle();await h.action('Modifica Merce').props.onClick();await h.settle();
 assert.equal(findCatalog(h.tree,n=>n.props?.onValueChange&&n.props.value==='GOOD').props.disabled,true);
 h.byId('catalog-name').props.onChange({target:{value:'Changed'}});await h.settle();h.submit();await h.settle();
 const write=h.calls.find(c=>c.method==='PUT')!;assert.equal(write.body.expectedVersion,4);assert.equal(write.body.values.name,'Changed');assert.equal(write.body.values.kind,undefined);
 assert.ok(h.calls.slice(h.calls.indexOf(write)+1).some(c=>c.path.includes('/r?')&&c.method==='GET'));assert.equal(h.state.editor,null);
 assert.equal([...h.storage.keys()].some(k=>k.endsWith(':pending')),false);
});
test('cancel is local, refresh restores a draft and stale revision cannot be saved',async()=>{
 const storage=new Map<string,string>();const h=catalogHarness('catalog-types',server,storage);await h.settle();await h.action('Modifica Merce').props.onClick();await h.settle();h.byId('catalog-name').props.onChange({target:{value:'Draft'}});await h.settle();h.unmount();
 const restored=catalogHarness('catalog-types',(p,m,b)=>p.includes('/r?')?{...row,version:6}:server(p,m,b),storage);await restored.settle();
 assert.equal(restored.byId('catalog-name').props.value,'Draft');assert.equal(restored.byId('catalog-save').props.disabled,true);assert.equal(restored.state.editor.version,4);
 restored.submit();await restored.settle();assert.equal(restored.calls.some(c=>c.method!=='GET'),false);
 restored.byId('catalog-cancel').props.onClick();await restored.settle();assert.equal(restored.state.editor,null);
});
test('lost create response blocks resend after refresh and menu reset; explicit readback is required',async()=>{
 const storage=new Map<string,string>();const h=catalogHarness('catalog-types',(p,m,b)=>{if(m==='POST')throw new CatalogApiError('network_error',0);return server(p,m,b);},storage);
 await h.settle();await h.byId('catalog-new').props.onClick();await h.settle();h.byId('catalog-name').props.onChange({target:{value:'New'}});await h.settle();h.submit();h.submit();await h.settle();assert.equal(h.calls.filter(c=>c.method==='POST').length,1);
 const key=h.helpers.catalogKey('u','t','catalog-types');assert.ok(storage.get(key+':pending'));h.helpers.resetCatalog({getItem:(k:string)=>storage.get(k),removeItem:(k:string)=>storage.delete(k)},key);assert.ok(storage.get(key+':pending'));h.unmount();
 const recovered=catalogHarness('catalog-types',server,storage);await recovered.settle();assert.equal(recovered.byId('catalog-new').props.disabled,true);assert.equal(recovered.calls.some(c=>c.method!=='GET'),false);
 const review=findCatalog(recovered.tree,n=>n.props?.children==='Leggi dati aggiornati');await review.props.onClick();await recovered.settle();
 const acknowledge=findCatalog(recovered.tree,n=>n.props?.children==='Ho verificato l’esito — scarta bozza e sblocca');assert.ok(acknowledge);acknowledge.props.onClick();await recovered.settle();assert.equal(storage.has(key+':pending'),false);assert.equal(recovered.byId('catalog-new').props.disabled,false);
});
test('duplicate code refusal retains an editable draft for correction',async()=>{
 const h=catalogHarness('catalog-types',(p,m,b)=>{if(m==='POST')throw new CatalogApiError('catalog_code_or_base_exists',409);return server(p,m,b);});await h.settle();await h.byId('catalog-new').props.onClick();await h.settle();h.byId('catalog-name').props.onChange({target:{value:'Duplicate'}});await h.settle();h.submit();await h.settle();assert.equal(h.byId('catalog-save').props.disabled,false);assert.equal(h.state.editor.values.name,'Duplicate');
});
test('revocation from the current session prevents a write even with an open editor',async()=>{
 let revoked=false;const h=catalogHarness('catalog-types',(p,m,b)=>p==='/session'&&revoked?{...catalogSession,permissions:['catalog-types.read']}:server(p,m,b));await h.settle();await h.action('Modifica Merce').props.onClick();await h.settle();revoked=true;h.submit();await h.settle();assert.equal(h.calls.some(c=>c.method==='PUT'),false);assert.equal(h.byId('catalog-save').props.disabled,true);
});
test('SERVICE defaults stock off and create payload contains the structural kind',async()=>{
 const h=catalogHarness('catalog-types',server);await h.settle();await h.byId('catalog-new').props.onClick();await h.settle();
 const kind=findCatalog(h.tree,n=>n.props?.onValueChange&&n.props.value==='GOOD');kind.props.onValueChange('SERVICE');await h.settle();
 assert.equal(h.byId('catalog-default_track_stock').props.checked,false);assert.equal(h.byId('catalog-default_track_stock').props.disabled,true);
 h.byId('catalog-name').props.onChange({target:{value:'New service'}});await h.settle();h.submit();await h.settle();assert.equal(h.calls.find(c=>c.method==='POST')?.body.values.kind,'SERVICE');
});
test('numbering preserves kind query and version, and keeps BP path independent',async()=>{
 const config={mode:'AUTO',prefix:'ART-',padding:6,nextNumber:1,version:3};const h=catalogHarness('catalog-numbering',(p,m,b)=>p==='/session'?catalogSession:m==='PUT'?{...b,version:4}:config);await h.settle();await h.action('Modifica Bene materiale').props.onClick();await h.settle();h.byId('catalog-prefix').props.onChange({target:{value:'G-'}});await h.settle();h.submit();await h.settle();const call=h.calls.find(c=>c.method==='PUT')!;assert.ok(call.path.startsWith('/catalog/numbering?kind=GOOD&tenantId=t'));assert.equal(call.body.version,3);assert.equal(call.body.prefix,'G-');
});
test('hierarchical parent excludes descendants and deleting a non-leaf is disabled',async()=>{
 const rows=[{id:'a',name:'A',parent_id:null,is_active:true,version:1},{id:'b',name:'B',parent_id:'a',is_active:true,version:1},{id:'c',name:'C',parent_id:'b',is_active:true,version:1}];const h=catalogHarness('catalog-categories',(p,m,b)=>p==='/session'?catalogSession:p.includes('/a?')?rows[0]:{items:rows,total:3});await h.settle();assert.equal(h.action('Elimina A').props.disabled,true);assert.equal(h.action('Elimina C').props.disabled,false);
 await h.action('Modifica A').props.onClick();await h.settle();const parent=findCatalog(h.tree,n=>n.props?.onValueChange&&n.props.value==='__none__');assert.equal(findCatalog(parent,n=>n.props?.value==='b'),undefined);assert.equal(findCatalog(parent,n=>n.props?.value==='c'),undefined);
});
test('delete verifies absence of the exact target before clearing its pending marker',async()=>{
 const record={id:'leaf',name:'Leaf',parent_id:null,is_active:true,version:8};let deleted=false;const h=catalogHarness('catalog-categories',(p,m)=>{if(p==='/session')return catalogSession;if(m==='DELETE'){deleted=true;return undefined;}if(p.includes('/leaf?')){if(deleted)throw new CatalogApiError('not_found',404);return record;}return {items:deleted?[]:[record],total:deleted?0:1};});await h.settle();h.action('Elimina Leaf').props.onClick();await h.settle();const button=findCatalog(h.tree,n=>n.props?.variant==='destructive');button.props.onClick();await h.settle();const index=h.calls.findIndex(c=>c.method==='DELETE');assert.ok(index>=0);assert.ok(h.calls.slice(index+1).some(c=>c.path.startsWith('/catalog/categories/leaf?')&&c.method==='GET'));assert.equal([...h.storage.keys()].some(k=>k.endsWith(':pending')),false);
});
test('delete confirmation and its original version survive refresh without writing',async()=>{
 const record={id:'leaf',name:'Leaf',parent_id:null,is_active:true,version:8};const storage=new Map<string,string>();const api=(p:string)=>p==='/session'?catalogSession:p.includes('/leaf?')?record:{items:[record],total:1};const h=catalogHarness('catalog-categories',api,storage);await h.settle();h.action('Elimina Leaf').props.onClick();await h.settle();h.unmount();const restored=catalogHarness('catalog-categories',api,storage);await restored.settle();assert.equal(restored.state.deleting?.id,'leaf');assert.equal(restored.state.deleting?.version,8);assert.equal(restored.calls.some(c=>c.method!=='GET'),false);
});
test('conversion sends exact strings and invalidates a preview when its input changes',async()=>{
 const units=[{id:'r',name:'Metre',code:'M',dimension:'LENGTH',is_active:true,version:1},{id:'cm',name:'Centimetre',code:'CM',dimension:'LENGTH',is_active:true,version:1}];const h=catalogHarness('catalog-units',(p,m,b)=>p==='/session'?catalogSession:p.includes('/convert?')?{quantity:'125',unroundedQuantity:'125',rounded:false,decimalPlaces:2}:{items:units,total:2});await h.settle();await h.action('Converti Metre').props.onClick();await h.settle();
 const target=findCatalog(h.tree,n=>n.props?.onValueChange&&findCatalog(n,c=>c.props?.id==='catalog-target'));target.props.onValueChange('cm');await h.settle();h.byId('catalog-quantity').props.onChange({target:{value:'1.25'}});await h.settle();
 const form=findCatalog(h.tree,n=>n.type==='form'&&findCatalog(n,c=>c.props?.id==='catalog-quantity'));form.props.onSubmit({preventDefault(){},stopPropagation(){}});await h.settle();const request=h.calls.find(c=>c.method==='POST')!;assert.equal(request.body.quantity,'1.25');assert.equal(request.body.targetUnitId,'cm');assert.ok(findCatalog(h.tree,n=>n.props?.role==='status'));
 h.byId('catalog-quantity').props.onChange({target:{value:'2'}});await h.settle();assert.equal(findCatalog(h.tree,n=>n.props?.role==='status'),undefined);
});
