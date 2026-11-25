import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,session,find} from './business-partner-harness.ts';

test('payment term installments are presented as a compact table rather than expanded editors', async()=>{
 const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-terms.read','payment-terms.update']}]}:path.endsWith('/payment-terms')?{items:[{id:'t',code:'NET',name:'Net',version:1,referenceDateType:'DOCUMENT_DATE',isActive:true,installments:[{percentage:'100',offsetMonths:0,offsetDays:0,dateRule:'EXACT',offsetBase:'REFERENCE_DATE',fixedDay:null,methodId:null}]}]}:{items:[],total:0});
 const p={session,scope:(x:string)=>x,onError:(e:any)=>e.message}, tree=()=>h.tree('PaymentsWorkspace',p);
 tree();await h.flush();let v=tree();find(v,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company')).props.onValueChange('c');tree();await h.flush();tree();await h.flush();v=tree();find(v,n=>n.props?.['aria-label']==='Edit Net').props.onClick();v=tree();
 assert.ok(find(v,n=>n.props?.id==='pt-code'), 'general fields visible initially');
 assert.equal(find(v,n=>n.props?.['data-installments-table']),undefined);
 const tabs=(node:any):any[]=>{if(!node||typeof node!=='object')return [];return [ ...(node.props?.role==='tab'?[node]:[]), ...([] as any[]).concat(node.props?.children??[]).flatMap(tabs) ];};
 assert.deepEqual(tabs(v).map(n=>n.props.children),['General','Installments']);
 find(v,n=>n.props?.role==='tab' && n.props?.children==='Installments').props.onClick();v=tree();
 assert.equal(find(v,n=>n.props?.id==='pt-code'),undefined);
 assert.ok(find(v,n=>n.props?.id==='preview-amount'), 'preview follows installments');
 assert.ok(find(v,n=>n.props?.['data-installments-table']), 'installments table should be visible');
 assert.ok(find(v,n=>n.props?.id==='percent-0'), 'percentage should be editable inline');
 for (const id of ['percent-0','months-0','days-0','base-0','rule-0','method-0']) {
  const label=find(v,n=>n.props?.htmlFor===id);
  assert.ok(label, `label ${id}`); assert.match(label.props.className ?? '', /sr-only/, `hidden label ${id}`);
 }
 const remove=find(v,n=>n.props?.['aria-label']==='Remove 1');
 assert.ok(remove, 'localized, row-specific remove action'); assert.equal(remove.props.disabled,true); assert.equal(remove.props.title,'Remove 1');
 const table=find(v,n=>n.props?.['data-installments-table']);
 assert.equal(!!find(table,n=>String(n.props?.className ?? '').includes('min-w-[1150px]')),false);
 for (const id of ['months-0','days-0','base-0','rule-0','method-0']) assert.ok(find(v,n=>n.props?.id===id), id);
 find(v,n=>n.props?.id==='months-0').props.onChange({target:{value:'2'}});v=tree();
 find(v,n=>n.props?.children==='Add' && n.props?.onClick).props.onClick();v=tree();
 assert.ok(find(v,n=>n.props?.id==='percent-1'));assert.equal(find(v,n=>n.props?.id==='percent-1').props.value,'0');
 const secondRemove=find(v,n=>n.props?.['aria-label']==='Remove 2'); assert.equal(secondRemove.props.disabled,false);
 secondRemove.props.onClick(); v=tree(); assert.equal(find(v,n=>n.props?.id==='percent-1'),undefined);
 find(v,n=>n.props?.children==='Add' && n.props?.onClick).props.onClick(); v=tree();
 find(v,n=>n.props?.id==='percent-0').props.onChange({target:{value:'60'}});v=tree();find(v,n=>n.props?.id==='percent-1').props.onChange({target:{value:'40'}});v=tree();
 find(v,n=>n.type==='form').props.onSubmit({preventDefault(){}});await h.flush();
 const write=h.calls.find(x=>x.method==='PUT');assert.ok(write);assert.equal(write.body.installments.length,2);assert.equal(write.body.installments[0].offsetMonths,2);assert.equal(write.body.installments[0].percentage,60);assert.equal(write.body.installments[1].percentage,40);
});
