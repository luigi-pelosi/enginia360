import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,session,find} from './business-partner-harness.ts';

async function setup(readonly=false, holdWrites=false) {
 const p={session,scope:(x:string)=>x,onError:(e:any)=>e.message};
 const h=partnerHarness('payments-workspace','en',(path,verb)=>holdWrites && verb!=='GET'?new Promise(()=>{}):path==='/payment-companies'?{items:[{id:'c',name:'Company',permissions:readonly?['payment-methods.read','payment-terms.read']:['payment-methods.read','payment-methods.create','payment-methods.update','payment-terms.read','payment-terms.create','payment-terms.update']}]}:path.endsWith('/payment-methods')?{items:[{id:'m',code:'WIRE',name:'Wire',direction:'BOTH',requiresBankAccount:false,isActive:true}]}:path.endsWith('/payment-terms')?{items:[{id:'t',code:'NET',name:'Net',referenceDateType:'DOCUMENT_DATE',isActive:true,installments:[{percentage:'100',offsetMonths:0,offsetDays:0,dateRule:'EXACT',offsetBase:'REFERENCE_DATE',fixedDay:null,methodId:null}]}]}:{items:[]});
 const tree=()=>h.tree('PaymentsWorkspace',p);tree();await h.flush();let v=tree();find(v,n=>n.props?.onValueChange && n.props.children?.some?.((x:any)=>x?.props?.id==='payment-company')).props.onValueChange('c');tree();await h.flush();tree();await h.flush();return {h,tree};
}
test('methods retain compact list while editing in a labelled dialog with icon action',async()=>{
 const {tree}=await setup();let v=tree();const action=find(v,n=>n.props?.['aria-label']==='Edit Wire');assert.ok(action);assert.match(action.props.className,/size-|w-/);action.props.onClick();v=tree();assert.ok(find(v,n=>n.props?.id==='payments-filter'));assert.ok(find(v,n=>n.props?.open===true && n.props?.onOpenChange));assert.ok(find(v,n=>n.props?.id==='pm-code'));
});
test('term dialog places preview under installments',async()=>{
 const {tree,h}=await setup();let v=tree();find(v,n=>n.props?.children==='Payment terms' && n.props?.onClick).props.onClick();tree();await h.flush();v=tree();find(v,n=>n.props?.['aria-label']==='Edit Net').props.onClick();v=tree();assert.ok(find(v,n=>n.props?.role==='tablist'));const selected=find(v,n=>n.props?.role==='tab' && n.props?.['aria-selected']===true);assert.ok(selected);assert.equal(selected.props.tabIndex,0);assert.equal(typeof selected.props.onKeyDown,'function');assert.equal(find(v,n=>n.props?.id==='preview-amount'),undefined);const tab=find(v,n=>n.props?.role==='tab' && n.props?.children==='Installments');assert.ok(tab);tab.props.onClick();v=tree();assert.ok(find(v,n=>n.props?.id==='preview-amount'));assert.ok(find(v,n=>n.props?.id==='percent-0'));assert.equal(find(v,n=>n.props?.id==='pt-code'),undefined);
});

test('payment boolean editors use labelled shared switches and preserve toggles in payloads',async()=>{
 const {tree,h}=await setup();let v=tree();find(v,n=>n.props?.['aria-label']==='Edit Wire').props.onClick();v=tree();
 for(const [id,label,checked] of [['pm-bank','Requires bank details',false],['pm-active','Active',true]] as const){
  const control=find(v,n=>n.props?.id===id);assert.ok(control);assert.equal(typeof control.props.onCheckedChange,'function',`${id} must use shared Switch`);
  assert.equal(control.props.checked,checked);assert.equal(control.props.disabled,false);
  const field=find(v,n=>n.props?.className==='field switch-field' && find(n,x=>x.props?.id===id));assert.ok(field);
  assert.ok(find(field,n=>n.props?.htmlFor===id && n.props?.children===label));
  control.props.onCheckedChange(!checked);v=tree();assert.equal(find(v,n=>n.props?.id===id).props.checked,!checked);
 }
 find(v,n=>n.type==='form').props.onSubmit({preventDefault(){}});await h.flush();
 const method=h.calls.find(x=>x.method==='PATCH');assert.equal(method?.body.requiresBankAccount,true);assert.equal(method?.body.isActive,false);
 v=tree();find(v,n=>n.props?.children==='Payment terms' && n.props?.onClick).props.onClick();tree();await h.flush();v=tree();find(v,n=>n.props?.['aria-label']==='Edit Net').props.onClick();v=tree();
 const control=find(v,n=>n.props?.id==='pt-active');assert.equal(typeof control.props.onCheckedChange,'function');assert.equal(control.props.checked,true);
 const field=find(v,n=>n.props?.className==='field switch-field' && find(n,x=>x.props?.id==='pt-active'));assert.ok(field);assert.ok(find(field,n=>n.props?.htmlFor==='pt-active' && n.props?.children==='Active'));
 control.props.onCheckedChange(false);v=tree();assert.equal(find(v,n=>n.props?.id==='pt-active').props.checked,false);
 find(v,n=>n.type==='form').props.onSubmit({preventDefault(){}});await h.flush();assert.equal(h.calls.find(x=>x.method==='PUT')?.body.isActive,false);
});

test('payment switches disable and ignore changes for read-only details',async()=>{
 const {tree,h}=await setup(true);let v=tree();find(v,n=>n.props?.['aria-label']==='Details Wire').props.onClick();v=tree();
 for(const id of ['pm-bank','pm-active']) {const control=find(v,n=>n.props?.id===id);assert.equal(control.props.disabled,true);const checked=control.props.checked;control.props.onCheckedChange(!checked);v=tree();assert.equal(find(v,n=>n.props?.id===id).props.checked,checked);}
 find(v,n=>n.props?.children==='Payment terms' && n.props?.onClick).props.onClick();tree();await h.flush();v=tree();find(v,n=>n.props?.['aria-label']==='Details Net').props.onClick();v=tree();const control=find(v,n=>n.props?.id==='pt-active');assert.equal(control.props.disabled,true);control.props.onCheckedChange(false);assert.equal(find(tree(),n=>n.props?.id==='pt-active').props.checked,true);
});
test('payment switches disable while a save is in flight',async()=>{
 const {tree}=await setup(false,true);let v=tree();find(v,n=>n.props?.['aria-label']==='Edit Wire').props.onClick();v=tree();find(v,n=>n.type==='form').props.onSubmit({preventDefault(){}});v=tree();
 for(const id of ['pm-bank','pm-active']) {const control=find(v,n=>n.props?.id===id);assert.equal(control.props.disabled,true);const checked=control.props.checked;control.props.onCheckedChange(!checked);assert.equal(find(tree(),n=>n.props?.id===id).props.checked,checked);}
});


test('term tabs support keyboard navigation and missing common fields block saving from installments',async()=>{
 const {tree,h}=await setup();let v=tree();find(v,n=>n.props?.children==='Payment terms' && n.props?.onClick).props.onClick();tree();await h.flush();v=tree();find(v,n=>n.props?.['aria-label']==='Edit Net').props.onClick();v=tree();
 find(v,n=>n.props?.id==='pt-code').props.onChange({target:{value:''}});v=tree();
 let focused=-1;const tab=find(v,n=>n.props?.role==='tab' && n.props?.children==='General');tab.props.onKeyDown({key:'End',preventDefault(){},currentTarget:{parentElement:{querySelectorAll:()=>[{focus(){focused=0}},{focus(){focused=1}}]}}});v=tree();assert.equal(focused,1);assert.ok(find(v,n=>n.props?.id==='percent-0'));
 assert.ok(find(v,n=>n.props?.children==='Save'));assert.ok(find(v,n=>n.props?.children==='Cancel'));find(v,n=>n.type==='form').props.onSubmit({preventDefault(){}});await h.flush();v=tree();assert.ok(find(v,n=>n.props?.id==='pt-code'));assert.equal(h.calls.some(x=>x.method==='PUT'),false);
});
