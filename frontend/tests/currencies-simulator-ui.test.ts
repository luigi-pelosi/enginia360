import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness, session, find} from './business-partner-harness.ts';
import {renderToStaticMarkup} from 'react-dom/server';

function newButton(tree:any) {
 const button=find(tree,n=>n.props?.onClick && Array.isArray(n.props.children) && n.props.children.includes('New') && /^<button\b/.test(renderToStaticMarkup(n)));
 assert.ok(button, 'New action must render as a button');
 return button;
}

test('new simulator defaults to the first enabled currency with known precision', async () => {
 const props={session,scope:(x:string)=>x,onError:(e:any)=>e.message};
 const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-terms.read','payment-terms.create','payment-schedule.preview']}]}:path.startsWith('/data/currencies')?{items:[{code:'JPY',name:'Yen',is_enabled:true,minor_units:0},{code:'XXX',name:'None',is_enabled:true,minor_units:null},{code:'OLD',name:'Old',is_enabled:false,minor_units:2}],total:3}:{items:[]});
 h.tree('PaymentsWorkspace',props); await h.flush();
 let tree=h.tree('PaymentsWorkspace',props);
 const company=find(tree,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company'));
 company.props.onValueChange('c'); h.tree('PaymentsWorkspace',props); await h.flush(); h.tree('PaymentsWorkspace',props); await h.flush();
 tree=h.tree('PaymentsWorkspace',props);
 newButton(tree).props.onClick();
 tree=h.tree('PaymentsWorkspace',props);
 find(tree,n=>n.props?.role==='tab' && n.props.children==='Installments').props.onClick(); tree=h.tree('PaymentsWorkspace',props);
 const select=find(tree,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='preview-currency'));
 assert.ok(select); assert.equal(select.props.value,'JPY');
 const choices=select.props.children[1].props.children.flat().filter(Boolean).map((n:any)=>n.props.value);
 assert.deepEqual(Array.from(choices),['__none__','JPY']);
});

async function simulator() {
 const props={session,scope:(x:string)=>x,onError:(e:any)=>e.message};
 const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-terms.read','payment-terms.create','payment-schedule.preview']}]}:path.startsWith('/data/currencies')?{items:[{code:'JPY',name:'Yen',is_enabled:true,minor_units:0},{code:'CLF',name:'Unit',is_enabled:true,minor_units:4}],total:2}:{items:[]});
 const tree=()=>h.tree('PaymentsWorkspace',props);
 tree(); await h.flush(); let t=tree();
 find(t,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company')).props.onValueChange('c');
 tree(); await h.flush(); tree(); await h.flush(); t=tree(); newButton(t).props.onClick();
 const input=(id:string,value:string)=>{find(tree(),n=>n.props?.id===id).props.onChange({target:{value}})};
 const select=(value:string)=>find(tree(),n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='preview-currency')).props.onValueChange(value);
 const preview=()=>find(tree(),n=>n.props?.role==='tab' && n.props.children==='Installments').props.onClick();
 const calculate=()=>find(tree(),n=>n.props?.onClick && n.props.children==='Calculate');
 return {h,tree,input,select,calculate,preview};
}

test('preview renumbers remaining installments after removal', async()=>{
 const {h,tree,input,select,calculate,preview}=await simulator();
 h.state[7]={code:'T',name:'Term',defaultMethodId:null,referenceDateType:'DOCUMENT_DATE',isActive:true,installments:[{sequence:1,percentage:'50',offsetMonths:0,offsetDays:0,dateRule:'EXACT',offsetBase:'REFERENCE_DATE',fixedDay:null,methodId:null},{sequence:2,percentage:'100',offsetMonths:0,offsetDays:0,dateRule:'EXACT',offsetBase:'REFERENCE_DATE',fixedDay:null,methodId:null}]};
 preview(); find(tree(),n=>n.props?.onClick && n.props['aria-label']==='Remove 1').props.onClick();
 input('preview-date','2026-11-20'); select('JPY'); input('preview-amount','12');
 calculate().props.onClick(); await new Promise(resolve=>setImmediate(resolve));
 const call=h.calls.find(x=>x.path.endsWith('/payment-schedule/preview'));
 assert.equal(call?.body.paymentTerm.installments[0].sequence,1);
});

test('preview enforces selected currency decimal precision and step', async()=>{
 const {h,tree,input,select,calculate,preview}=await simulator();
 preview(); input('preview-date','2026-11-20'); select('CLF'); input('preview-amount','12.1234');
 assert.equal(find(tree(),n=>n.props?.id==='preview-amount').props.step,'0.0001');
 assert.equal(calculate().props.disabled,false);
 select('JPY'); assert.equal(find(tree(),n=>n.props?.id==='preview-amount').props.step,'1');
 assert.equal(calculate().props.disabled,true);
 calculate().props.onClick(); assert.equal(h.calls.some(x=>x.path.endsWith('/payment-schedule/preview')),false);
});

test('preview accepts exact string amounts and rejects excess nonzero digits', async()=>{
 const {h,input,select,calculate,preview}=await simulator();
 preview(); input('preview-date','2026-11-20'); select('CLF'); input('preview-amount','12345678901234567890.12345');
 assert.equal(calculate().props.disabled,true); calculate().props.onClick();
 assert.equal(h.calls.some(x=>x.path.endsWith('/payment-schedule/preview')),false);
 input('preview-amount','12345678901234567890.1234'); assert.equal(calculate().props.disabled,false);
 calculate().props.onClick(); await new Promise(resolve=>setImmediate(resolve));
 assert.equal(h.calls.find(x=>x.path.endsWith('/payment-schedule/preview'))?.body.amountDue,'12345678901234567890.1234');
});


test('late catalog does not overwrite a user currency selection', async()=>{
 let resolveCatalog:(value:any)=>void=()=>{};
 const catalog=new Promise(resolve=>{resolveCatalog=resolve});
 const props={session,scope:(x:string)=>x,onError:(e:any)=>e.message};
 const h=partnerHarness('payments-workspace','en',path=>path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:['payment-terms.read','payment-terms.create']}]}:path.startsWith('/data/currencies')?catalog:{items:[]});
 const tree=()=>h.tree('PaymentsWorkspace',props);
 tree();await h.flush();find(tree(),n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company')).props.onValueChange('c');
 tree();await h.flush();tree();await h.flush();newButton(tree()).props.onClick();
 find(tree(),n=>n.props?.role==='tab' && n.props.children==='Installments').props.onClick();
 const select=()=>find(tree(),n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='preview-currency'));
 select().props.onValueChange('CLF');
 resolveCatalog({items:[{code:'JPY',name:'Yen',is_enabled:true,minor_units:0},{code:'CLF',name:'Unit',is_enabled:true,minor_units:4}],total:2});
 await new Promise(resolve=>setImmediate(resolve));tree();await h.flush();
 assert.equal(select().props.value,'CLF');
});

test('default currency is sent in the preview payload', async()=>{
 const {h,input,calculate,preview}=await simulator();
 preview();input('preview-date','2026-11-20');input('preview-amount','12');
 assert.equal(calculate().props.disabled,false);calculate().props.onClick();
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(h.calls.find(x=>x.path.endsWith('/payment-schedule/preview'))?.body.currency,'JPY');
});
