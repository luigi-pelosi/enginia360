import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,session,find} from './business-partner-harness.ts';

test('installment required headers respond to fixed-day selection', async()=>{
 const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-terms.read','payment-terms.update']}]}:path.endsWith('/payment-terms')?{items:[{id:'t',code:'NET',name:'Net',version:1,referenceDateType:'DOCUMENT_DATE',isActive:true,installments:[{percentage:'100',offsetMonths:0,offsetDays:0,dateRule:'EXACT',offsetBase:'REFERENCE_DATE',fixedDay:null,methodId:null}]}]}:{items:[],total:0});
 const p={session,scope:(x:string)=>x,onError:(e:any)=>e.message}, tree=()=>h.tree('PaymentsWorkspace',p);
 tree();await h.flush();let v=tree();find(v,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company')).props.onValueChange('c');tree();await h.flush();tree();await h.flush();v=tree();find(v,n=>n.props?.['aria-label']==='Edit Net').props.onClick();v=tree();
 assert.equal(find(v,n=>n.props?.htmlFor==='pt-code').props.required,true);
 assert.equal(find(v,n=>n.props?.htmlFor==='pt-reference').props.required,true);
 assert.notEqual(find(v,n=>n.props?.htmlFor==='pt-method').props.required,true);
 find(v,n=>n.props?.role==='tab' && n.props?.children==='Installments').props.onClick();v=tree();
 const header=(label:string)=>find(v,n=>Array.isArray(n.props?.children) && n.props.children[0]===label && n.props.children.length===2);
 const marked=(label:string)=>!!header(label)?.props.children[1];
 assert.equal(marked('Percentage'),true); assert.equal(marked('Day of month'),false);
 const rule=find(v,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='rule-0'));
 rule.props.onValueChange('FIXED_DAY');v=tree();
 assert.equal(marked('Day of month'),true);
 assert.equal(find(v,n=>n.props?.htmlFor==='fixed-0').props.required,true);
 assert.equal(find(v,n=>n.props?.id==='fixed-0').props.required,true);
});
