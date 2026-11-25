import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,session,find} from './business-partner-harness.ts';
test('payment methods filter by code or name',async()=>{
 const p={session,scope:(x:string)=>x,onError:(e:any)=>e.message};
 const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-methods.read']}]}:path.endsWith('/payment-methods')?{items:[{id:'1',code:'WIRE',name:'Transfer',direction:'BOTH',isActive:true},{id:'2',code:'CASH',name:'Cash',direction:'BOTH',isActive:true}]}:{items:[]});
 const tree=()=>h.tree('PaymentsWorkspace',p);tree();await h.flush();let v=tree();find(v,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company')).props.onValueChange('c');tree();await h.flush();tree();await h.flush();v=tree();
 const search=find(v,n=>n.props?.id==='payments-filter');assert.ok(search);search.props.onChange({target:{value:'wire'}});v=tree();
 assert.ok(find(v,n=>n.props?.children==='WIRE'));assert.equal(find(v,n=>n.props?.children==='CASH'),undefined);
});
