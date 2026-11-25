import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,session,find} from './business-partner-harness.ts';

for (const [section,label] of [['payment-methods','Payment methods'],['payment-terms','Payment terms'],['payment-settings','Company settings']] as const) {
 test(`${section} disables save with a pending outcome`, async()=>{
  const entries=new Map<string,string>();
  const storage={getItem:(k:string)=>entries.get(k)??null,setItem:(k:string,v:string)=>{entries.set(k,v)},removeItem:(k:string)=>{entries.delete(k)},clear:()=>entries.clear(),key:(i:number)=>[...entries.keys()][i]??null,get length(){return entries.size}} as Storage;
  const tenant=session.selectedTenantId || session.tenantId || '';
  storage.setItem(`payments-pending:${encodeURIComponent(session.id)}:${encodeURIComponent(tenant)}`,'1');
  const grants=['payment-methods.read','payment-methods.create','payment-terms.read','payment-terms.create','payment-settings.read','payment-settings.update'];
  const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:grants}]}:path.endsWith('/payment-settings')?{defaultSalesTermId:null,defaultPurchaseTermId:null,defaultSalesMethodId:null,defaultPurchaseMethodId:null,version:1}:{items:[],total:0},storage);
  const p={session,scope:(x:string)=>x,onError:(e:any)=>e.message};const tree=()=>h.tree('PaymentsWorkspace',p);
  const settle=async()=>{for(let i=0;i<5;i++){tree();await h.flush();}return tree();};
  let v=await settle();find(v,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company')).props.onValueChange('c');v=await settle();
  find(v,n=>n.props?.onClick && n.props?.children===label).props.onClick();v=await settle();
  if(section!=='payment-settings'){find(v,n=>n.props?.onClick && Array.isArray(n.props?.children) && n.props.children.includes('New')).props.onClick();v=tree();}
  const save=find(v,n=>n.props?.children==='Save');assert.ok(save);assert.equal(save.props.disabled,true,'save must be disabled while outcome is uncertain');
  assert.ok(find(v,n=>n.props?.role==='alert'));
  find(v,n=>n.type==='form').props.onSubmit({preventDefault(){}});await h.flush();
  assert.equal(h.calls.filter(x=>x.method==='POST'||x.method==='PUT'||x.method==='PATCH').length,0);
  assert.equal(storage.getItem(`payments-pending:${encodeURIComponent(session.id)}:${encodeURIComponent(tenant)}`),'1');
 });
}
