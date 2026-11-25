import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,session,find} from './business-partner-harness.ts';

test('term list shows localized real installments in a compact accessible disclosure',async()=>{
 for (const [locale,heading,base,rule,day] of [['en','Installments','Reference month end','Fixed day','Day of month'],['it','Rate','Fine mese di riferimento','Giorno fisso','Giorno del mese']] as const) {
  const rows=Array.from({length:5},(_,i)=>({percentage:i===0?'12.5':'20',offsetMonths:i,offsetDays:i+1,offsetBase:'REFERENCE_MONTH_END',dateRule:'FIXED_DAY',fixedDay:15,methodId:null}));
  const h=partnerHarness('payments-workspace',locale,path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-terms.read']}]}:path.endsWith('/payment-terms')?{items:[{id:'t',code:'NET',name:'Net',isActive:true,installments:rows}]}:{items:[]});
  const props={session,scope:(x:string)=>x,onError:(e:any)=>e.message};const tree=()=>h.tree('PaymentsWorkspace',props);
  tree();await h.flush();let v=tree();find(v,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company')).props.onValueChange('c');tree();await h.flush();tree();await h.flush();v=tree();
  const nav=find(v,n=>n.props?.onClick && n.props?.children===(locale==='en'?'Payment terms':'Condizioni di pagamento'));assert.ok(nav);nav.props.onClick();tree();await h.flush();v=tree();
  assert.ok(find(v,n=>n.props?.children===heading));
  const list=find(v,n=>n.props?.['data-term-installments']===true);assert.ok(list,'installment summary in list');
  const text=JSON.stringify(list);assert.match(text,/12[.,]5/);assert.ok(text.includes(base));assert.ok(text.includes(rule));assert.ok(text.includes(day));assert.ok(text.includes('15'));
  assert.ok(find(list,n=>n.type==='details'));assert.ok(find(list,n=>n.type==='summary'));
  assert.ok(find(v,n=>n.props?.['aria-label']===(locale==='en'?'Details Net':'Dettagli Net')));
 }
});
