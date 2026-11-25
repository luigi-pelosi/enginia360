import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,session,find} from './business-partner-harness.ts';
test('payment workspace uses selected company grants instead of session-wide grants',async()=>{
 const s={...session,permissions:['payment-methods.read','payment-terms.read','payment-settings.read']};
 const p={session:s,scope:(x:string)=>x,onError:(e:any)=>e.message};
 const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c1',name:'One',permissions:['payment-settings.read']}]}:path.endsWith('payment-settings')?{defaultSalesTermId:null,defaultPurchaseTermId:null,defaultSalesMethodId:null,defaultPurchaseMethodId:null,version:0}:{items:[]});
 h.tree('PaymentsWorkspace',p);await h.flush();let tree=h.tree('PaymentsWorkspace',p);
 const select=find(tree,n=>n.props?.children && n.props?.onValueChange && n.props.children.some?.((x:any)=>x?.props?.id==='payment-company'));assert.ok(select);select.props.onValueChange('c1');
 h.tree('PaymentsWorkspace',p);await h.flush();h.tree('PaymentsWorkspace',p);await h.flush();
 assert.equal(h.calls.some(x=>x.path==='/companies/c1/payment-methods'),false);
 assert.equal(h.calls.some(x=>x.path==='/companies/c1/payment-terms'),false);
});
