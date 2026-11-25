import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogHarness,catalogSession,findCatalog} from './catalog-harness.ts';
const units=[{id:'source',name:'Source',code:'S',dimension:'LENGTH',is_active:true},{id:'inactive',name:'Inactive',dimension:'LENGTH',is_active:false},{id:'item',name:'Item',dimension:'LENGTH',is_active:true,conversion_scope:'ITEM'},{id:'other',name:'Other',dimension:'MASS',is_active:true},{id:'target',name:'Target',dimension:'LENGTH',is_active:true}];
test('new conversion defaults to first eligible distinct target and submits it',async()=>{
 const h=catalogHarness('catalog-units',(p,m)=>p==='/session'?catalogSession:m==='POST'?{}:{items:units,total:units.length});await h.settle();await h.action('Converti Source').props.onClick();await h.settle();
 assert.equal(h.state.conversion.targetId,'target');
 const select=findCatalog(h.tree,n=>n.props?.onValueChange&&findCatalog(n,c=>c.props?.id==='catalog-target'));
 assert.equal(findCatalog(select,n=>n.props?.value==='source'),undefined);
 const form=findCatalog(h.tree,n=>n.type==='form'&&findCatalog(n,c=>c.props?.id==='catalog-quantity'));form.props.onSubmit({preventDefault(){},stopPropagation(){}});await h.settle();assert.equal(h.calls.find(c=>c.method==='POST')?.body.targetUnitId,'target');
});
test('no eligible target leaves conversion unselected and prevents submission',async()=>{
 const alone=[units[0],units[1],units[2],units[3]];const h=catalogHarness('catalog-units',(p,m)=>p==='/session'?catalogSession:{items:alone,total:alone.length});await h.settle();await h.action('Converti Source').props.onClick();await h.settle();assert.equal(h.state.conversion.targetId,'');
 const form=findCatalog(h.tree,n=>n.type==='form'&&findCatalog(n,c=>c.props?.id==='catalog-quantity'));assert.equal(findCatalog(form,n=>n.props?.type==='submit').props.disabled,true);form.props.onSubmit({preventDefault(){},stopPropagation(){}});await h.settle();assert.equal(h.calls.some(c=>c.method==='POST'),false);
});
test('recovered conversion preserves selection even when it is no longer eligible',async()=>{
 const storage=new Map<string,string>();const api=(p:string)=>p==='/session'?catalogSession:{items:units,total:units.length};const h=catalogHarness('catalog-units',api,storage);await h.settle();await h.action('Converti Source').props.onClick();await h.settle();h.unmount();
 const remaining=units.filter(u=>u.id!=='target');const recovered=catalogHarness('catalog-units',(p)=>p==='/session'?catalogSession:{items:remaining,total:remaining.length},storage);await recovered.settle();assert.equal(recovered.state.conversion.targetId,'target');const form=findCatalog(recovered.tree,n=>n.type==='form'&&findCatalog(n,c=>c.props?.id==='catalog-quantity'));assert.equal(findCatalog(form,n=>n.props?.type==='submit').props.disabled,true);
});
test('new catalog structural selections retain semantic defaults and edit retains persisted kind',async()=>{
 for(const [resource,field,expected] of [['catalog-units','dimension','COUNT'],['catalog-types','kind','GOOD']] as const){const h=catalogHarness(resource,(p)=>p==='/session'?catalogSession:{items:[],total:0});await h.settle();await h.byId('catalog-new').props.onClick();await h.settle();assert.equal(h.state.editor.values[field],expected);h.unmount();}
});
test('conversion waits for options before opening and preserves recovered choice during reload',async()=>{
 let release:(value:any)=>void=()=>{};let delay=false;const pending=new Promise(resolve=>{release=resolve;});const storage=new Map<string,string>();const handler=(p:string)=>p==='/session'?catalogSession:delay?pending:{items:units,total:units.length};const h=catalogHarness('catalog-units',handler,storage);await h.settle();delay=true;const opening=h.action('Converti Source').props.onClick();await h.settle();assert.equal(h.state.conversion,null);release({items:units,total:units.length});await opening;await h.settle();assert.equal(h.state.conversion.targetId,'target');h.unmount();
 let releaseReload:(value:any)=>void=()=>{};const reload=new Promise(resolve=>{releaseReload=resolve;});const restored=catalogHarness('catalog-units',(p)=>p==='/session'?catalogSession:reload,storage);await restored.settle();assert.equal(restored.state.conversion.targetId,'target');const form=findCatalog(restored.tree,n=>n.type==='form'&&findCatalog(n,c=>c.props?.id==='catalog-quantity'));assert.equal(findCatalog(form,n=>n.props?.type==='submit').props.disabled,true);releaseReload({items:units,total:units.length});await restored.settle();assert.equal(restored.state.conversion.targetId,'target');
});
