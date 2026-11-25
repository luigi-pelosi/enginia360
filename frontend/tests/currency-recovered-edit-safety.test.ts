import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness, session, find} from './business-partner-harness.ts';

function setup(saved:any, respond:(path:string, method:string, body:any)=>any=()=>({id:'eur'})) {
 const entries=new Map<string,string>();
 const storage: Storage={getItem:k=>entries.get(k)??null,setItem:(k,v)=>{entries.set(k,v)},removeItem:k=>{entries.delete(k)},clear:()=>entries.clear(),key:i=>[...entries.keys()][i]??null,get length(){return entries.size}};
 if(saved) storage.setItem('workspace:u:t:record:currencies',JSON.stringify(saved));
 const h=partnerHarness('workspace','en',respond,storage);
 const props={resource:{key:'currencies',fields:[{name:'code',type:'text'},{name:'name',type:'text'}]},row:{id:'eur',code:'EUR',name:'Euro',version:3},canWrite:true,session,tenant:'t',scope:(x:string)=>x,load:async()=>[],onClose(){},onSaved:async()=>{},onError:()=>''};
 return {h,props,storage};
}

test('recovered currency draft submits its original version', async () => {
 const {h,props}=setup({kind:'edit',id:'eur',version:3,baseline:{code:'EUR',name:'Euro'},values:{code:'EUR',name:'Draft'}});
 h.tree('RecordEditor',props); await h.flush(); h.tree('RecordEditor',props); await h.flush();
 const tree=h.tree('RecordEditor',props);
 assert.equal(find(tree,n=>n.props?.id==='field-name').props.value,'Draft');
 assert.equal(find(tree,n=>n.props?.form==='record-form').props.disabled,false);
 await find(tree,n=>n.props?.id==='record-form').props.onSubmit({preventDefault(){}});
 assert.equal(h.calls.find(c=>c.method==='PUT')?.body.expectedVersion,3);
});

test('legacy draft stays visible but cannot be submitted', async () => {
 const {h,props}=setup({kind:'edit',id:'eur',baseline:{code:'EUR',name:'Euro'},values:{code:'EUR',name:'Draft'}});
 h.tree('RecordEditor',props); await h.flush(); h.tree('RecordEditor',props); await h.flush();
 const tree=h.tree('RecordEditor',props);
 assert.equal(find(tree,n=>n.props?.id==='field-name').props.value,'Draft');
 assert.equal(find(tree,n=>n.props?.form==='record-form').props.disabled,true);
 await find(tree,n=>n.props?.id==='record-form').props.onSubmit({preventDefault(){}});
 assert.equal(h.calls.length,0);
});

test('conflict preserves original draft and version', async () => {
 const {ApiError}=await import('../lib/api.ts');
 const {h,props,storage}=setup({kind:'edit',id:'eur',version:2,baseline:{code:'EUR',name:'Euro'},values:{code:'EUR',name:'Draft'}},()=>{throw new ApiError('version_conflict',409)});
 h.tree('RecordEditor',props); await h.flush(); h.tree('RecordEditor',props); await h.flush();
 const tree=h.tree('RecordEditor',props);
 await find(tree,n=>n.props?.id==='record-form').props.onSubmit({preventDefault(){}});
 const saved=JSON.parse(storage.getItem('workspace:u:t:record:currencies')!);
 assert.equal(saved.version,2); assert.equal(saved.values.name,'Draft');
 assert.equal(h.calls[0].body.expectedVersion,2);
 assert.equal(storage.getItem('record-pending:u:t:currencies'),null);
});

test('uncertain edit cannot be repeated after reload', async () => {
 const {h,props,storage}=setup({kind:'edit',id:'eur',version:3,baseline:{code:'EUR',name:'Euro'},values:{code:'EUR',name:'Draft'}},()=>{throw new Error('lost response')});
 h.tree('RecordEditor',props); await h.flush(); h.tree('RecordEditor',props); await h.flush();
 await find(h.tree('RecordEditor',props),n=>n.props?.id==='record-form').props.onSubmit({preventDefault(){}});
 assert.equal(storage.getItem('record-pending:u:t:currencies'),'pending');
 const h2=partnerHarness('workspace','en',()=>({}),storage);
 h2.tree('RecordEditor',props); await h2.flush(); h2.tree('RecordEditor',props); await h2.flush();
 const tree=h2.tree('RecordEditor',props);
 assert.equal(find(tree,n=>n.props?.id==='field-name').props.value,'Draft');
 assert.equal(find(tree,n=>n.props?.form==='record-form').props.disabled,true);
});

test('fresh edit sends authoritative row version', async () => {
 const {h,props}=setup(null);
 h.tree('RecordEditor',props); await h.flush(); h.tree('RecordEditor',props); await h.flush();
 let tree=h.tree('RecordEditor',props);
 find(tree,n=>n.props?.id==='field-name').props.onChange({target:{value:'Edited'}});
 tree=h.tree('RecordEditor',props);
 await find(tree,n=>n.props?.id==='record-form').props.onSubmit({preventDefault(){}});
 assert.equal(h.calls.find(c=>c.method==='PUT')?.body.expectedVersion,3);
});

test('opening another currency cannot overwrite a pending draft', async () => {
 const draft={kind:'edit',id:'eur',version:3,baseline:{code:'EUR',name:'Euro'},values:{code:'EUR',name:'Draft'}};
 const {h,props,storage}=setup(draft);
 storage.setItem('record-pending:u:t:currencies','pending');
 props.row={id:'usd',code:'USD',name:'Dollar',version:4};
 h.tree('RecordEditor',props); await h.flush(); h.tree('RecordEditor',props); await h.flush();
 assert.deepEqual(JSON.parse(storage.getItem('workspace:u:t:record:currencies')!),draft);
 assert.equal(find(h.tree('RecordEditor',props),n=>n.props?.form==='record-form').props.disabled,true);
});
