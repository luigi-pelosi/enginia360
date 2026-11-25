import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,session,find} from './business-partner-harness.ts';

test('methods list provides toolbar and paginates filtered results',async()=>{
 const rows=Array.from({length:30},(_,i)=>({id:String(i),code:`M${i}`,name:`Method ${i}`,direction:'BOTH',isActive:true}));
 const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-methods.read','payment-methods.create']}]}:path.endsWith('/payment-methods')?{items:rows}:{items:[]});
 const p={session,scope:(x:string)=>x,onError:(e:any)=>e.message,heading:'Payments'};const tree=()=>h.tree('PaymentsWorkspace',p);
 tree();await h.flush();let v=tree();find(v,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company')).props.onValueChange('c');tree();await h.flush();tree();await h.flush();v=tree();
 assert.ok(find(v,n=>n.props?.className==='page-heading flex-wrap' && n.props.children));
 assert.ok(find(v,n=>n.props?.className==='table-toolbar'));
 assert.ok(find(v,n=>n.props?.['aria-label']==='Refresh'));
 assert.equal(find(v,n=>n.props?.children==='M25'),undefined);
 find(v,n=>n.props?.children==='Next' && n.props?.onClick).props.onClick();v=tree();assert.ok(find(v,n=>n.props?.children==='M25'));
 find(v,n=>n.props?.id==='payments-filter').props.onChange({target:{value:'M1'}});v=tree();assert.ok(find(v,n=>n.props?.children==='M1'));assert.equal(find(v,n=>n.props?.children==='M25'),undefined);
});
