import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './record-editor-harness.ts';

const makeStorage=()=>{const m=new Map<string,string>();return {getItem:(k:string)=>m.get(k)??null,setItem:(k:string,v:string)=>{m.set(k,v);},removeItem:(k:string)=>{m.delete(k);},clear:()=>m.clear(),key:(i:number)=>[...m.keys()][i]??null,get length(){return m.size;}} as Storage;};
const props={resource:{key:'countries',fields:[{name:'name',type:'text',required:true}]},row:null,canWrite:true,session:{...session,isSuperAdmin:true},tenant:'t',scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:()=> 'error'};
const submit=(tree:any)=>find(tree,n=>n.props?.id==='record-form').props.onSubmit({preventDefault(){}});
async function ready(h:any){h.tree('RecordEditor',props);await h.flush();h.tree('RecordEditor',props);await h.flush();return h.tree('RecordEditor',props);}
test('pending create is recorded before POST and blocks refresh replay',async()=>{
 const storage=makeStorage();let observed=false;
 const h=partnerHarness('workspace','en',(_p,method)=>{if(method==='POST'){observed=storage.length>1;throw Error('lost response');}return {};},storage);
 let tree=await ready(h);find(tree,n=>n.props?.id==='field-name').props.onChange({target:{value:'Acme'}});tree=h.tree('RecordEditor',props);await submit(tree);
 assert.equal(observed,true,'marker must exist before POST');
 const fresh=partnerHarness('workspace','en',()=>({id:'x'}),storage);tree=await ready(fresh);await submit(tree);assert.equal(fresh.calls.filter(c=>c.method==='POST').length,0);
});

test('a definite successful create removes the lock and allows a new create',async()=>{
 const s=makeStorage(), h=partnerHarness('workspace','en',()=>({id:'one'}),s);let tree=await ready(h);find(tree,n=>n.props?.id==='field-name').props.onChange({target:{value:'Acme'}});tree=h.tree('RecordEditor',props);await submit(tree);
 assert.equal([...Array(s.length)].map((_,i)=>s.key(i)).some(k=>k?.startsWith('record-pending:')),false);
 const next=partnerHarness('workspace','en',()=>({id:'two'}),s);tree=await ready(next);find(tree,n=>n.props?.id==='field-name').props.onChange({target:{value:'Other'}});tree=next.tree('RecordEditor',props);await submit(tree);assert.equal(next.calls.filter(c=>c.method==='POST').length,1);
});
test('unavailable storage prevents POST',async()=>{
 const s=makeStorage();s.setItem=()=>{throw Error('unavailable');};const h=partnerHarness('workspace','en',()=>({id:'one'}),s);let tree=await ready(h);find(tree,n=>n.props?.id==='field-name').props.onChange({target:{value:'Acme'}});tree=h.tree('RecordEditor',props);await submit(tree);assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
});
test('a validation rejection releases the lock for correction',async()=>{
 const {ApiError}=await import('../lib/api.ts');const s=makeStorage();const h=partnerHarness('workspace','en',()=>{throw new ApiError('invalid',400);},s);let tree=await ready(h);find(tree,n=>n.props?.id==='field-name').props.onChange({target:{value:'Acme'}});tree=h.tree('RecordEditor',props);await submit(tree);assert.equal([...Array(s.length)].map((_,i)=>s.key(i)).some(k=>k?.startsWith('record-pending:')),false);
});
test('menu reset cannot discard a pending draft',async()=>{
 const s=makeStorage();let release:(v:any)=>void=()=>{};const pending=new Promise(resolve=>{release=resolve;});const h=partnerHarness('workspace','en',()=>pending,s);
 let tree=await ready(h);find(tree,n=>n.props?.id==='field-name').props.onChange({target:{value:'Acme'}});tree=h.tree('RecordEditor',props);const inflight=submit(tree);
 h.components.clearRecordRecovery(props.session,'t','countries');
 const draft=JSON.parse(s.getItem('workspace:u:t:record:countries')!);assert.equal(draft.values.name,'Acme');
 const fresh=partnerHarness('workspace','en',()=>({id:'duplicate'}),s);tree=await ready(fresh);assert.equal(find(tree,n=>n.props?.id==='field-name').props.value,'Acme');await submit(tree);assert.equal(fresh.calls.length,0);
 release({id:'ok'});await inflight;
});
