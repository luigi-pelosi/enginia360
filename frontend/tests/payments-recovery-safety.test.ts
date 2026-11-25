import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,session,find} from './business-partner-harness.ts';

test('pending payment mutation remains blocked after remount', async()=>{
 const entries=new Map<string,string>();
 const storage={getItem:(k:string)=>entries.get(k)??null,setItem:(k:string,v:string)=>{entries.set(k,v)},removeItem:(k:string)=>{entries.delete(k)},clear:()=>entries.clear(),key:(i:number)=>[...entries.keys()][i]??null,get length(){return entries.size}} as Storage;
 const tenant=session.selectedTenantId || session.tenantId || '';
 storage.setItem(`payments-pending:${encodeURIComponent(session.id)}:${encodeURIComponent(tenant)}`,'1');
 const p={session,scope:(x:string)=>x,onError:(e:any)=>e.message};
 const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-methods.read','payment-methods.create']}]}:{items:[]},storage);
 const tree=()=>h.tree('PaymentsWorkspace',p);
 tree();await h.flush();let v=tree();
 find(v,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company')).props.onValueChange('c');
 tree();await h.flush();tree();await h.flush();v=tree();
 find(v,n=>n.props?.onClick && Array.isArray(n.props?.children) && n.props.children.includes('New')).props.onClick();v=tree();
 const form=find(v,n=>n.type==='form');assert.ok(form);
 await form.props.onSubmit({preventDefault(){}});
 assert.equal(h.calls.filter(x=>x.method==='POST').length,0);
 assert.ok(find(tree(),n=>n.props?.role==='alert'));
});
