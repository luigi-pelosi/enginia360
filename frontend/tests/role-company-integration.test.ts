import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './record-editor-harness.ts';
const base={resource:{key:'roles',fields:[{name:'name',type:'text',required:true}]},row:{id:'role1',name:'Role'},canWrite:false,session:{...session,permissions:['roles.read','companies.read','roles.assign_companies']},tenant:'t',scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:(e:any)=>e.code||e.message};
const panel=(tree:any)=>find(tree,n=>n.type?.name==='RoleCompanyAccess');
const save=(tree:any)=>find(tree,n=>n.props?.form==='record-form');
const form=(tree:any)=>find(tree,n=>n.type==='form');
const plain=(v:any)=>JSON.parse(JSON.stringify(v));
const event={preventDefault(){}};
function setup(overrides:any={},respond?:(p:string,m:string,b:any)=>any){let closed=0;const props={...base,onClose(){closed++;},...overrides};const h=partnerHarness('workspace','en',respond??((p,m)=>m==='GET'?{companyIds:['c1']}:{id:'role1'}));const render=()=>h.tree('RecordEditor',props);return {h,props,render,closed:()=>closed};}
test('companies-only changes use the main atomic save with synchronous duplicate guard despite readonly fields',async()=>{
 const {h,render,closed}=setup();render();await h.flush();let tree=render();assert.ok(save(tree),'main Save is available to company assigners');assert.equal(save(tree).props.disabled,true);
 panel(tree).props.onLookupState(true,'');panel(render()).props.onIdsChange(['c2','c1']);tree=render();assert.equal(save(tree).props.disabled,false);
 const submit=form(tree).props.onSubmit;await Promise.all([submit(event),submit(event)]);const writes=h.calls.filter(c=>c.method!=='GET');assert.equal(writes.length,1);assert.equal(writes[0].path,'/data/roles/role1/save');assert.deepEqual(plain(writes[0].body),{companyIds:['c1','c2']});assert.equal(closed(),1);
});
test('new role offers company draft before identity exists, creates atomically and keeps company draft in pending recovery',async()=>{
 const entries=new Map<string,string>();const storage={getItem:(k:string)=>entries.get(k)??null,setItem:(k:string,v:string)=>{entries.set(k,v);},removeItem:(k:string)=>{entries.delete(k);},clear:()=>entries.clear(),key:(i:number)=>[...entries.keys()][i]??null,get length(){return entries.size;}};
 let pending:any;let closed=0;const props={...base,row:null,canWrite:true,session:{...session,permissions:['roles.create','roles.assign_companies','companies.read']},onClose(){closed++;}};
 const h=partnerHarness('workspace','en',(p,m,b)=>{if(m==='POST'){pending=[...entries.values()].map(v=>{try{return JSON.parse(v);}catch{return null;}}).find(v=>v?.kind==='create');return {id:'new'};}return {ids:[]};},storage);const render=()=>h.tree('RecordEditor',props);
 render();await h.flush();let tree=render();assert.ok(panel(tree));assert.equal(panel(tree).props.roleId,'');assert.equal(h.calls.some(c=>c.path.startsWith('/roles/')),false);
 panel(tree).props.onLookupState(true,'');panel(render()).props.onIdsChange(['c2']);find(render(),n=>n.props?.id==='field-name').props.onChange({target:{value:'New'}});tree=render();assert.equal(save(tree).props.disabled,false);await form(tree).props.onSubmit(event);
 const writes=h.calls.filter(c=>c.method==='POST');assert.equal(writes.length,1);assert.equal(writes[0].path,'/data/roles/save');assert.deepEqual(plain(writes[0].body),{values:{name:'New'},companyIds:['c2']});assert.deepEqual(pending.companyIds,['c2']);assert.equal(closed,1);
});
test('unchanged companies are omitted and explicit removal sends [] alongside values and links',async()=>{
 for(const clear of [false,true]){
  const {h,render}=setup({canWrite:true,session:{...session,permissions:[...base.session.permissions,'roles.update','roles.assign_permissions','permissions.read']}},(p,m)=>m==='GET'?(p.startsWith('/roles/')?{companyIds:['hidden','c1']}:{ids:['p1']}):{id:'role1'});
  render();await h.flush();let tree=render();panel(tree).props.onLookupState(true,'');find(render(),n=>n.props?.id==='field-name').props.onChange({target:{value:'Changed'}});
  if(clear){panel(render()).props.onIdsChange([]);find(render(),n=>n.type?.name==='RelationEditor').props.onIdsChange(['p2']);}
  tree=render();assert.equal(save(tree).props.disabled,false);await form(tree).props.onSubmit(event);const writes=h.calls.filter(c=>c.method!=='GET');assert.equal(writes.length,1);
  assert.deepEqual(plain(writes[0].body),clear?{values:{name:'Changed'},links:{'role-permissions':['p2']},companyIds:[]}:{values:{name:'Changed'}});
 }
});
test('assignment and lookup loading/errors block parent submission without clearing existing draft',async()=>{
 for(const failing of ['assignment','lookup']){
  const {h,render}=setup({canWrite:true},p=>{if(failing==='assignment')throw {code:'denied'};return {companyIds:['hidden']};});
  let tree=render();find(tree,n=>n.props?.id==='field-name').props.onChange({target:{value:'Changed'}});assert.equal(save(render()).props.disabled,true);await form(render()).props.onSubmit(event);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
  await h.flush();tree=render();panel(tree).props.onLookupState(failing==='assignment',failing==='lookup'?'lookup failed':'');tree=render();assert.equal(save(tree).props.disabled,true);panel(tree).props.onIdsChange([]);await form(render()).props.onSubmit(event);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);if(failing==='lookup')assert.deepEqual(plain(panel(render()).props.ids),['hidden']);
 }
});
test('company read and assign permissions are exact; no grant cannot inject changes',async()=>{
 for(const permissions of [['roles.read','companies.read','roles.update'],['roles.read','roles.assign_companies'],['companies.read','roles.assign_companies']]){
  const {h,render}=setup({canWrite:true,session:{...session,permissions}});render();await h.flush();let tree=render();const child=panel(tree);if(child){assert.equal(child.props.editable,false);child.props.onLookupState(true,'');child.props.onIdsChange(['injected']);}else assert.equal(h.calls.some(c=>c.path.startsWith('/roles/')),false);
  find(render(),n=>n.props?.id==='field-name').props.onChange({target:{value:'Changed'}});await form(render()).props.onSubmit(event);const write=h.calls.find(c=>c.method!=='GET');assert.ok(write);assert.equal(Object.hasOwn(write.body,'companyIds'),false);
 }
});
test('main cancel closes without writes and failed save keeps company changes for correction',async()=>{
 const {h,render,closed}=setup({},(p,m)=>{if(m!=='GET')throw {code:'refused'};return {companyIds:['c1']};});render();await h.flush();panel(render()).props.onLookupState(true,'');panel(render()).props.onIdsChange(['hidden']);await form(render()).props.onSubmit(event);let tree=render();assert.equal(closed(),0);assert.deepEqual(plain(panel(tree).props.ids),['hidden']);assert.equal(save(tree).props.disabled,false);assert.ok(find(tree,n=>n.props?.message==='refused'));
 const before=h.calls.length;find(tree,n=>n.props?.variant==='outline'&&n.props.children==='Cancel').props.onClick();assert.equal(closed(),1);assert.equal(h.calls.length,before);
});
test('company draft recovery survives a lookup error while editing other fields',async()=>{
 const entries=new Map<string,string>();const storage={getItem:(k:string)=>entries.get(k)??null,setItem:(k:string,v:string)=>{entries.set(k,v);},removeItem:(k:string)=>{entries.delete(k);},clear:()=>entries.clear(),key:(i:number)=>[...entries.keys()][i]??null,get length(){return entries.size;}};
 const props={...base,row:null,canWrite:true};const h=partnerHarness('workspace','en',()=>({ids:[]}),storage);const render=()=>h.tree('RecordEditor',props);
 render();await h.flush();panel(render()).props.onLookupState(true,'');panel(render()).props.onIdsChange(['hidden']);render();await h.flush();panel(render()).props.onLookupState(false,'lookup failed');find(render(),n=>n.props?.id==='field-name').props.onChange({target:{value:'Recovered'}});render();await h.flush();
 const saved=JSON.parse([...entries.values()][0]);assert.deepEqual(saved.companyIds,['hidden']);assert.equal(saved.values.name,'Recovered');
 const reloaded=partnerHarness('workspace','en',()=>({ids:[]}),storage);reloaded.tree('RecordEditor',props);await reloaded.flush();assert.deepEqual(plain(panel(reloaded.tree('RecordEditor',props)).props.ids),['hidden']);
});
test('pending parent Save freezes fields and company draft, including stale callbacks',async()=>{
 let finish!:(v:any)=>void;const pending=new Promise(resolve=>{finish=resolve;});const {h,render}=setup({canWrite:true},(p,m)=>m==='GET'?{companyIds:['c1']}:pending);
 render();await h.flush();panel(render()).props.onLookupState(true,'');const stale=panel(render()).props.onIdsChange;stale(['c2']);const work=form(render()).props.onSubmit(event);let tree=render();assert.equal(find(tree,n=>n.type==='fieldset'&&n.props?.className==='form-grid').props.disabled,true);assert.equal(panel(tree).props.busy,true);stale(['injected']);assert.deepEqual(plain(panel(render()).props.ids),['c2']);finish({id:'role1'});await work;
});
test('new role main Cancel discards the complete recovered draft without a request',async()=>{
 const entries=new Map<string,string>();const storage={getItem:(k:string)=>entries.get(k)??null,setItem:(k:string,v:string)=>{entries.set(k,v);},removeItem:(k:string)=>{entries.delete(k);},clear:()=>entries.clear(),key:(i:number)=>[...entries.keys()][i]??null,get length(){return entries.size;}};
 let closed=0;const props={...base,row:null,canWrite:true,onClose(){h.components.clearRecordRecovery(props.session,'t','roles');closed++;}};const h=partnerHarness('workspace','en',()=>({ids:[]}),storage);const render=()=>h.tree('RecordEditor',props);
 render();await h.flush();panel(render()).props.onLookupState(true,'');panel(render()).props.onIdsChange(['hidden']);find(render(),n=>n.props?.id==='field-name').props.onChange({target:{value:'Discard'}});render();await h.flush();assert.ok(entries.size);const before=h.calls.length;find(render(),n=>n.props?.variant==='outline'&&n.props.children==='Cancel').props.onClick();assert.equal(closed,1);assert.equal(entries.size,0);assert.equal(h.calls.length,before);
});
