import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,session,find} from './business-partner-harness.ts';

test('refresh restores a new method draft after fresh company authorization', async()=>{
 const entries=new Map<string,string>();
 const storage={getItem:(k:string)=>entries.get(k)??null,setItem:(k:string,v:string)=>{entries.set(k,v)},removeItem:(k:string)=>{entries.delete(k)},clear:()=>entries.clear(),key:(i:number)=>[...entries.keys()][i]??null,get length(){return entries.size}} as Storage;
 const p={session,effectiveTenant:'tenant-a',scope:(x:string)=>x,onError:(e:any)=>e.message};
 const response=(path:string)=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-methods.read','payment-methods.create']}]}:{items:[],total:0};
 const h=partnerHarness('payments-workspace','en',response,storage), tree=()=>h.tree('PaymentsWorkspace',p);
 tree();await h.flush();let v=tree();find(v,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company')).props.onValueChange('c');
 tree();await h.flush();tree();await h.flush();v=tree();find(v,n=>n.props?.onClick && Array.isArray(n.props?.children) && n.props.children.includes('New')).props.onClick();v=tree();find(v,n=>n.props?.id==='pm-name').props.onChange({target:{value:'Draft name'}});tree();await h.flush();
 const r=partnerHarness('payments-workspace','en',response,storage), restored=()=>r.tree('PaymentsWorkspace',p);
 restored();await r.flush();restored();await r.flush();restored();await r.flush();restored();await r.flush();v=restored();
 assert.equal(find(v,n=>n.props?.id==='pm-name')?.props.value,'Draft name');
});


test('a deleted saved method is not reopened from storage', async()=>{
 const entries=new Map<string,string>(); const storage={getItem:(k:string)=>entries.get(k)??null,setItem:(k:string,v:string)=>{entries.set(k,v)},removeItem:(k:string)=>{entries.delete(k)},clear:()=>entries.clear(),key:(i:number)=>[...entries.keys()][i]??null,get length(){return entries.size}} as Storage;
 entries.set(`payments-recovery:${encodeURIComponent(session.id)}:tenant-a`,JSON.stringify({company:'c',section:'payment-methods',method:{id:'gone',version:3,code:'X',name:'Deleted'}}));
 const p={session,effectiveTenant:'tenant-a',scope:(x:string)=>x,onError:(e:any)=>e.message};
 const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-methods.read','payment-methods.update']}]}:{items:[],total:0},storage);
 const tree=()=>h.tree('PaymentsWorkspace',p);for(let i=0;i<5;i++){tree();await h.flush();}assert.equal(find(tree(),n=>n.props?.id==='pm-name'),undefined);
});

test('revoked company rights and another effective tenant cannot recover a draft', async()=>{
 const entries=new Map<string,string>(); const storage={getItem:(k:string)=>entries.get(k)??null,setItem:(k:string,v:string)=>{entries.set(k,v)},removeItem:(k:string)=>{entries.delete(k)},clear:()=>entries.clear(),key:(i:number)=>[...entries.keys()][i]??null,get length(){return entries.size}} as Storage;
 entries.set(`payments-recovery:${encodeURIComponent(session.id)}:tenant-a`,JSON.stringify({company:'c',section:'payment-methods',method:{code:'X',name:'Private'}}));
 for(const [tenant,permissions] of [['tenant-a',[]],['tenant-b',['payment-methods.read','payment-methods.create']]] as [string,string[]][]) {
  const p={session,effectiveTenant:tenant,scope:(x:string)=>x,onError:(e:any)=>e.message}; const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions}]}:{items:[],total:0},storage);const tree=()=>h.tree('PaymentsWorkspace',p);for(let i=0;i<5;i++){tree();await h.flush();}assert.equal(find(tree(),n=>n.props?.id==='pm-name'),undefined);
 }
});


test('term draft restores its tab and migrates legacy preview to installments', async()=>{
 for(const [saved,expected] of [['general','General'],['installments','Installments'],['preview','Installments']] as const){
  const entries=new Map<string,string>(); const storage={getItem:(k:string)=>entries.get(k)??null,setItem:(k:string,v:string)=>{entries.set(k,v)},removeItem:(k:string)=>{entries.delete(k)},clear:()=>entries.clear(),key:(i:number)=>[...entries.keys()][i]??null,get length(){return entries.size}} as Storage;
  entries.set(`payments-recovery:${encodeURIComponent(session.id)}:tenant-a`,JSON.stringify({company:'c',section:'payment-terms',termTab:saved,term:{code:'T',name:'Draft',defaultMethodId:null,referenceDateType:'DOCUMENT_DATE',isActive:true,installments:[{percentage:'100',offsetMonths:0,offsetDays:0,dateRule:'EXACT',offsetBase:'REFERENCE_DATE',fixedDay:null,methodId:null}]}}));
  const p={session,effectiveTenant:'tenant-a',scope:(x:string)=>x,onError:(e:any)=>e.message};
  const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-terms.read','payment-terms.create']}]}:{items:[],total:0},storage);const tree=()=>h.tree('PaymentsWorkspace',p);for(let i=0;i<5;i++){tree();await h.flush();}
  const v=tree();assert.equal(find(v,n=>n.props?.role==='tab' && n.props?.['aria-selected']===true)?.props.children,expected);
  if(expected==='General')assert.equal(find(v,n=>n.props?.id==='pt-name')?.props.value,'Draft');else assert.ok(find(v,n=>n.props?.id==='preview-amount'));
 }
});
