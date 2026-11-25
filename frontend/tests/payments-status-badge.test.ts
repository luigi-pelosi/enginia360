import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,session,find} from './business-partner-harness.ts';

test('inactive payment methods and terms show localized status badges in read-only lists',async()=>{
 for (const [locale,disabled,terms,details] of [['en','Inactive','Payment terms','Details'],['it','Disattivo','Condizioni di pagamento','Dettagli']] as const) {
  const h=partnerHarness('payments-workspace',locale,path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-methods.read','payment-terms.read']}]}:path.endsWith('/payment-methods')?{items:[{id:'m',code:'M',name:'Method',direction:'BOTH',isActive:false}]}:path.endsWith('/payment-terms')?{items:[{id:'t',code:'T',name:'Term',isActive:false,installments:[]}]}:{items:[]});
  const props={session,scope:(x:string)=>x,onError:(e:any)=>e.message};const tree=()=>h.tree('PaymentsWorkspace',props);
  tree();await h.flush();let v=tree();find(v,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company')).props.onValueChange('c');tree();await h.flush();tree();await h.flush();v=tree();
  assert.ok(find(v,n=>n.props?.variant==='secondary' && n.props?.children===disabled),'method status badge');
  assert.ok(find(v,n=>n.props?.['aria-label']===`${details} Method`));
  find(v,n=>n.props?.onClick && n.props?.children===terms).props.onClick();tree();await h.flush();v=tree();
  assert.ok(find(v,n=>n.props?.variant==='secondary' && n.props?.children===disabled),'term status badge');
  assert.ok(find(v,n=>n.props?.['aria-label']===`${details} Term`));
 }
});
