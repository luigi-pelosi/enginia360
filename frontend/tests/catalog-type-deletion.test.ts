import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogHarness,catalogSession,CatalogApiError,findCatalog} from './catalog-harness.ts';
const row={id:'type-a',name:'Merce',kind:'GOOD',is_active:true,version:4};
const warning='Impossibile eliminare la tipologia: è associata ad articoli o servizi esistenti.';
function fixture(options:{linked?:boolean;storage?:Map<string,string>;handler?:(p:string,m:string)=>any;permissions?:string[]}={}) {
 let deleted=false;
 const session=options.permissions?{...catalogSession,permissions:options.permissions}:catalogSession;
 return catalogHarness('catalog-types',(p,m)=>{
  const override=options.handler?.(p,m);if(override!==undefined)return override;
  if(p==='/session')return session;
  if(m==='DELETE'){deleted=true;return undefined;}
  if(p.includes('/deletion-check?'))return {canDelete:!options.linked};
  if(p.startsWith('/catalog/types/type-a?')){if(deleted)throw new CatalogApiError('not_found',404);return row;}
  return {items:deleted?[]:[row],total:deleted?0:1};
 },options.storage,'it',session);
}
const writes=(h:ReturnType<typeof fixture>)=>h.calls.filter(c=>c.method!=='GET');
const dialog=(h:ReturnType<typeof fixture>,id:string)=>findCatalog(h.tree,n=>typeof n.props?.open==='boolean'&&findCatalog(n,c=>c.props?.['data-testid']===id));
const open=async(h:ReturnType<typeof fixture>)=>{await h.settle();const action=h.action('Elimina Merce');assert.ok(action,'type row exposes delete action');action.props.onClick();await h.settle();};
test('linked type preflight opens a close-only warning without delete confirmation or writes',async()=>{
 const h=fixture({linked:true});await open(h);
 assert.equal(h.calls.filter(c=>c.path.includes('/deletion-check?')).length,1);
 assert.equal(dialog(h,'catalog-type-delete-blocked').props.open,true);
 assert.equal(dialog(h,'catalog-delete-confirm').props.open,false);
 assert.ok(findCatalog(h.tree,n=>n.props?.children===warning));
 assert.ok(h.byId('catalog-type-delete-close'));assert.equal(writes(h).length,0);
 h.byId('catalog-type-delete-close').props.onClick();await h.settle();assert.equal(dialog(h,'catalog-type-delete-blocked').props.open,false);
});

test('unused confirmation cancels locally; confirm sends one versioned delete and verifies 404',async()=>{
 const h=fixture();await open(h);assert.equal(dialog(h,'catalog-delete-confirm').props.open,true);assert.equal(writes(h).length,0);
 h.byId('catalog-delete-cancel').props.onClick();await h.settle();assert.equal(h.state.deleting,null);assert.equal(writes(h).length,0);
 await open(h);h.byId('catalog-delete-confirm').props.onClick();h.byId('catalog-delete-confirm').props.onClick();await h.settle();
 assert.equal(writes(h).length,1);assert.equal(writes(h)[0].path,'/catalog/types/type-a?expectedVersion=4&tenantId=t');
 const index=h.calls.indexOf(writes(h)[0]);assert.ok(h.calls.slice(index+1).some(c=>c.path==='/catalog/types/type-a?tenantId=t'&&c.method==='GET'));
 assert.equal(h.state.deleting,null);assert.equal([...h.storage.keys()].some(k=>k.endsWith(':pending')),false);
 assert.equal(h.calls.some(c=>c.path.startsWith('/catalog/items')),false);
});
test('newly linked type conflict switches confirmation to localized close-only warning and never retries',async()=>{
 const h=fixture({handler:(_p,m)=>{if(m==='DELETE')throw new CatalogApiError('item_type_in_use',409);}});await open(h);
 h.byId('catalog-delete-confirm').props.onClick();await h.settle();
 assert.equal(dialog(h,'catalog-delete-confirm').props.open,false);assert.equal(dialog(h,'catalog-type-delete-blocked').props.open,true);
 assert.ok(findCatalog(h.tree,n=>n.props?.children===warning));assert.equal(h.state.deleting,null);assert.equal(writes(h).length,1);
 assert.equal([...h.storage.keys()].some(k=>k.endsWith(':pending')),false);await h.settle();assert.equal(writes(h).length,1);
});
test('refresh repeats preflight before confirmation and blocks newly linked references',async()=>{
 const storage=new Map<string,string>(),h=fixture({storage});await open(h);h.unmount();
 const recovered=fixture({storage,linked:true});recovered.render();assert.equal(dialog(recovered,'catalog-delete-confirm').props.open,false);await recovered.settle();
 assert.equal(recovered.calls.filter(c=>c.path.includes('/deletion-check?')).length,1);assert.equal(dialog(recovered,'catalog-type-delete-blocked').props.open,true);
 assert.equal(recovered.state.deleting,null);assert.equal(writes(recovered).length,0);
});
test('refresh preserves original deletion version and refuses stale confirmation',async()=>{
 const storage=new Map<string,string>(),h=fixture({storage});await open(h);h.unmount();
 const recovered=fixture({storage,handler:p=>p.startsWith('/catalog/types/type-a?')?{...row,version:5}:undefined});await recovered.settle();
 assert.equal(recovered.calls.filter(c=>c.path.includes('/deletion-check?')).length,1);assert.equal(recovered.state.deleting.version,4);
 assert.equal(dialog(recovered,'catalog-delete-confirm').props.open,true);assert.equal(recovered.byId('catalog-delete-confirm').props.disabled,true);
 recovered.byId('catalog-delete-confirm').props.onClick();await recovered.settle();assert.equal(writes(recovered).length,0);
});

test('delete icon requires the exact type delete permission, not item or category delete',async()=>{
 for(const permissions of [['catalog-types.read'],['catalog-types.read','catalog-items.delete','catalog-categories.delete']]) {
  const h=fixture({permissions});await h.settle();assert.equal(h.action('Elimina Merce'),undefined);assert.equal(h.calls.some(c=>c.path.includes('/deletion-check')),false);
 }
 const h=fixture({permissions:['catalog-types.read','catalog-types.delete']});await open(h);assert.equal(h.calls.some(c=>c.path.startsWith('/catalog/items')),false);
});
test('preflight waits for response, disables row actions, and coalesces double clicks',async()=>{
 let release!:(value:{canDelete:boolean})=>void;
 const h=fixture({handler:p=>p.includes('/deletion-check?')?new Promise(resolve=>{release=resolve;}):undefined});await h.settle();
 const action=h.action('Elimina Merce');action.props.onClick();action.props.onClick();await h.settle();
 assert.equal(h.action('Elimina Merce').props.disabled,true);assert.equal(dialog(h,'catalog-delete-confirm').props.open,false);
 assert.equal(h.calls.filter(c=>c.path.includes('/deletion-check?')).length,1);assert.equal(writes(h).length,0);
 release({canDelete:true});await h.settle();assert.equal(dialog(h,'catalog-delete-confirm').props.open,true);
});
for(const failure of [new CatalogApiError('network_error',0),new CatalogApiError('forbidden',403),{canDelete:'yes'}])test(`failed or malformed preflight fails closed (${String(failure)})`,async()=>{
 const h=fixture({handler:p=>{if(p.includes('/deletion-check?')){if(failure instanceof Error)throw failure;return failure;}}});await open(h);
 assert.equal(dialog(h,'catalog-delete-confirm').props.open,false);assert.equal(dialog(h,'catalog-type-delete-blocked').props.open,false);assert.equal(h.state.deleting,null);
 assert.equal(writes(h).length,0);assert.equal(h.calls.filter(c=>c.path.includes('/deletion-check?')).length,1);await h.settle();assert.equal(writes(h).length,0);
});
for(const phase of ['preflight','confirm','recovery'])test(`fresh delete revocation fails closed before ${phase}`,async()=>{
 let revoked=false;const storage=new Map<string,string>();const handler=(p:string)=>p==='/session'&&revoked?{...catalogSession,permissions:['catalog-types.read']}:undefined;
 const h=fixture({storage,handler});await h.settle();
 if(phase==='preflight'){revoked=true;h.action('Elimina Merce').props.onClick();await h.settle();assert.equal(h.calls.some(c=>c.path.includes('/deletion-check?')),false);}
 else {await open(h);revoked=true;if(phase==='confirm'){h.byId('catalog-delete-confirm').props.onClick();await h.settle();}else {h.unmount();const recovered=fixture({storage,handler});await recovered.settle();assert.equal(dialog(recovered,'catalog-delete-confirm').props.open,false);assert.equal(recovered.calls.some(c=>c.path.includes('/deletion-check?')),false);assert.equal(writes(recovered).length,0);}}
 if(phase!=='recovery')assert.equal(dialog(h,'catalog-delete-confirm').props.open,false);assert.equal(writes(h).length,0);
});
test('pending delete keeps the confirmation portal open and cannot be double submitted',async()=>{
 let reject!:(error:Error)=>void;
 const storage=new Map<string,string>(),h=fixture({storage,handler:(_p,m)=>m==='DELETE'?new Promise((_resolve,r)=>{reject=r;}):undefined});await open(h);
 h.byId('catalog-delete-confirm').props.onClick();await h.settle();assert.equal(dialog(h,'catalog-delete-confirm').props.open,true);
 assert.equal(h.byId('catalog-delete-confirm').props.disabled,true);h.byId('catalog-delete-confirm').props.onClick();await h.settle();assert.equal(writes(h).length,1);
 reject(new CatalogApiError('network_error',0));await h.settle();assert.equal(dialog(h,'catalog-delete-confirm').props.open,false);
 const key=h.helpers.catalogKey('u','t','catalog-types'),marker=storage.get(key+':pending');assert.ok(marker);h.unmount();
 const recovered=fixture({storage});await recovered.settle();assert.equal(storage.get(key+':pending'),marker);assert.equal(writes(recovered).length,0);assert.equal(recovered.calls.some(c=>c.path.includes('/deletion-check?')),false);assert.equal(dialog(recovered,'catalog-delete-confirm').props.open,false);
});
test('successful delete with failed absence readback keeps pending and never replays after reload',async()=>{
 const storage=new Map<string,string>();let accepted=false;
 const h=fixture({storage,handler:(p,m)=>{if(m==='DELETE'){accepted=true;return {};}if(accepted&&p.startsWith('/catalog/types/type-a?'))throw new CatalogApiError('network_error',0);}});await open(h);h.byId('catalog-delete-confirm').props.onClick();await h.settle();
 const key=h.helpers.catalogKey('u','t','catalog-types');assert.equal(JSON.parse(storage.get(key+':pending')!).committed,true);assert.equal(writes(h).length,1);h.unmount();
 const recovered=fixture({storage});await recovered.settle();assert.equal(writes(recovered).length,0);assert.equal(dialog(recovered,'catalog-delete-confirm').props.open,false);
});
test('unmounted preflight response cannot persist or open a delete target',async()=>{
 let release!:(value:{canDelete:boolean})=>void;const storage=new Map<string,string>();
 const h=fixture({storage,handler:p=>p.includes('/deletion-check?')?new Promise(resolve=>{release=resolve;}):undefined});await h.settle();h.action('Elimina Merce').props.onClick();await h.settle();h.unmount();release({canDelete:true});await h.settle();
 assert.equal(h.state.deleting,null);assert.equal(writes(h).length,0);
});

for(const linked of [false,true])test(`context change hides an already opened type deletion dialog (linked=${linked})`,async()=>{
 const h=fixture({linked});await open(h);h.rerender({resource:'catalog-categories'});
 assert.equal(dialog(h,'catalog-delete-confirm').props.open,false);assert.equal(dialog(h,'catalog-type-delete-blocked').props.open,false);
 await h.settle();assert.equal(writes(h).length,0);
});
test('tenant change during preflight session refresh never checks or deletes the new tenant target',async()=>{
 let release!:(s:typeof catalogSession)=>void,delay=false;const admin={...catalogSession,isSuperAdmin:true};
 const h=catalogHarness('catalog-types',(p)=>{if(p==='/session')return delay?new Promise(resolve=>{release=resolve;}):admin;if(p.includes('/deletion-check?'))return {canDelete:true};return {items:[row],total:1};},undefined,'it',admin);
 await h.settle();delay=true;h.action('Elimina Merce').props.onClick();await h.settle();delay=false;h.rerender({tenantId:'other'});await h.settle();release(admin);await h.settle();
 assert.equal(h.calls.some(c=>c.path.includes('/deletion-check?')),false);assert.equal(writes(h).length,0);assert.equal(dialog(h,'catalog-delete-confirm').props.open,false);
});
test('late successful deletion response cannot clear or rewrite another resource recovery state',async()=>{
 let release!:(r:object)=>void;const h=fixture({handler:(_p,m)=>m==='DELETE'?new Promise(resolve=>{release=resolve;}):undefined});await open(h);h.byId('catalog-delete-confirm').props.onClick();await h.settle();
 const key=h.helpers.catalogKey('u','t','catalog-types'),raw=h.storage.get(key+':pending');assert.ok(raw);
 h.rerender({resource:'catalog-categories'});await h.settle();const before=h.calls.length;release({});await h.settle();
 assert.equal(h.storage.get(key+':pending'),raw);assert.equal(h.calls.slice(before).some(c=>c.path.startsWith('/catalog/types/type-a?')),false);assert.equal(writes(h).length,1);
});

test('a stale DELETE conflict retains the original token, blocks retry and does not adopt latest version',async()=>{
 let rejected=false;const h=fixture({handler:(p,m)=>{if(m==='DELETE'){rejected=true;throw new CatalogApiError('stale_version',409);}if(rejected&&p.startsWith('/catalog/types/type-a?'))return {...row,version:9};}});await open(h);
 h.byId('catalog-delete-confirm').props.onClick();await h.settle();assert.equal(h.state.deleting.version,4);assert.equal(h.byId('catalog-delete-confirm').props.disabled,true);
 h.byId('catalog-delete-confirm').props.onClick();await h.settle();assert.equal(writes(h).length,1);assert.ok(writes(h)[0].path.includes('expectedVersion=4'));assert.equal([...h.storage.keys()].some(k=>k.endsWith(':pending')),false);
});
test('recovered unused type waits for a repeated server check before offering original version confirmation',async()=>{
 const storage=new Map<string,string>(),h=fixture({storage});await open(h);h.unmount();let release!:(v:{canDelete:boolean})=>void;
 const recovered=fixture({storage,handler:p=>p.includes('/deletion-check?')?new Promise(resolve=>{release=resolve;}):undefined});await recovered.settle();
 assert.equal(dialog(recovered,'catalog-delete-confirm').props.open,false);assert.equal(recovered.state.deleting.version,4);assert.equal(writes(recovered).length,0);
 release({canDelete:true});await recovered.settle();assert.equal(dialog(recovered,'catalog-delete-confirm').props.open,true);assert.equal(recovered.state.deleting.version,4);
});
test('recovery preflight failure discards confirmation and never automatically retries or deletes',async()=>{
 const storage=new Map<string,string>(),h=fixture({storage});await open(h);h.unmount();
 const recovered=fixture({storage,handler:p=>{if(p.includes('/deletion-check?'))throw new CatalogApiError('network_error',0);}});await recovered.settle();await recovered.settle();
 assert.equal(dialog(recovered,'catalog-delete-confirm').props.open,false);assert.equal(recovered.state.deleting,null);assert.equal(recovered.calls.filter(c=>c.path.includes('/deletion-check?')).length,1);assert.equal(writes(recovered).length,0);
});
test('English blocked warning and shared dialog accessibility contract are preserved',async()=>{
 const h=catalogHarness('catalog-types',p=>p==='/session'?catalogSession:p.includes('/deletion-check?')?{canDelete:false}:{items:[row],total:1},undefined,'en');await h.settle();h.action('Delete Merce').props.onClick();await h.settle();
 const content=findCatalog(h.tree,n=>n.props?.['data-testid']==='catalog-type-delete-blocked');assert.equal(content.type.name,'DialogContent');assert.equal(content.props.showCloseButton,false);
 assert.ok(findCatalog(content,n=>n.type?.name==='DialogTitle'));assert.ok(findCatalog(content,n=>n.type?.name==='DialogDescription'&&n.props.children==='Cannot delete this type: it is associated with existing goods or services.'));
 assert.equal(h.byId('catalog-type-delete-close').props.children,'Close');assert.equal(writes(h).length,0);
});
