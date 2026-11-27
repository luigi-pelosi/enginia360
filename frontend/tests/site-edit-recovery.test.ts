import test from 'node:test';
import assert from 'node:assert/strict';
import {harness,find,session} from './workspace-harness.ts';
const resource={key:'sites',fields:[{name:'name',type:'text',required:true},{name:'address',type:'text',required:true}]};
test('site recovery reopens only the exact fresh site from its resource collection',async()=>{
 const h=harness();const saved={kind:'edit',id:'s',baseline:{name:'Site',address:'Old street'}};
 const rows=[{id:'other',name:'Other site'},{id:'s',name:'Fresh site'}];
 assert.equal((await h.components.recoverCurrencyEdit(saved,resource,async(key:string)=>{assert.equal(key,'sites');return rows;})).id,'s');
 assert.equal(await h.components.recoverCurrencyEdit({...saved,id:'missing'},resource,async()=>rows),null);
});
test('site edit recovery retains original baseline and omits retired fiscal fields',async()=>{
 const storage=new Map([['workspace:u:t:record:sites',JSON.stringify({kind:'edit',id:'s',baseline:{name:'Old name',address:'Old street'},values:{name:'Old name',address:'Draft street',vat_number:'LEGACY',tax_code:'LEGACY'}})]]);
 const h=harness('it',{},()=>({id:'s',name:'Fresh name',address:'Draft street'}),storage,undefined,true);
 const props={resource,row:{id:'s',name:'Fresh name',address:'Old street'},canWrite:true,session,tenant:'t',scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:String};
 const render=()=>h.tree('RecordEditor',props);
 for(let i=0;i<4;i++){render();await h.flush();}
 const tree=render();assert.equal(find(tree,n=>n.props?.id==='field-address').props.value,'Draft street');
 await find(tree,n=>n.props?.id==='record-form').props.onSubmit({preventDefault(){}});
 assert.deepEqual(JSON.parse(JSON.stringify(h.apiPayloads)),[{values:{address:'Draft street'}}]);
});
