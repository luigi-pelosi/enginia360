import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';
import {ApiError} from '../lib/api.ts';
const storage=()=>{const map=new Map<string,string>();return {getItem:(k:string)=>map.get(k)??null,setItem:(k:string,v:string)=>map.set(k,v),removeItem:(k:string)=>map.delete(k),clear:()=>map.clear(),key:(i:number)=>[...map.keys()][i]??null,get length(){return map.size;}} as Storage;};
const p={session:{...session,tenantId:'tenant',permissions:['business-partners.read','business-partners.create','business-partners.update']},scope:(s:string)=>s,onError:()=> 'error'};
test('refresh restores open new editor and isolates tenant',async()=>{
 const s=storage(), h=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}),s);
 let tree=h.tree('BusinessPartnerWorkspace',p);await h.flush();find(tree,n=>Array.isArray(n.props?.children)&&n.props.children.includes('New Business Partner')).props.onClick();h.tree('BusinessPartnerWorkspace',p);await h.flush();
 const fresh=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}),s);fresh.tree('BusinessPartnerWorkspace',p);await fresh.flush();tree=fresh.tree('BusinessPartnerWorkspace',p);assert.equal(tree.type,fresh.components.BusinessPartnerEditor);assert.equal(tree.props.id,null);
 const other=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}),s);assert.notEqual(other.tree('BusinessPartnerWorkspace',{...p,session:{...p.session,tenantId:'other'}}).type,other.components.BusinessPartnerEditor);
});

test('refresh restores unsaved editor and open related row',async()=>{
 const s=storage(), props={...p,id:null,onClose(){},onSaved(){}};
 const h=partnerHarness('business-partner-workspace','en',()=>({}),s);let tree=h.tree('BusinessPartnerEditor',props);await h.flush();
 find(tree,n=>n.props?.id==='bp-legal_name').props.onChange({target:{value:'Unsaved'}});tree=h.tree('BusinessPartnerEditor',props);find(tree,n=>n.props?.['data-action']==='add-contact').props.onClick();tree=h.tree('BusinessPartnerEditor',props);find(tree,n=>n.props?.id==='bp-contact-0-value').props.onChange({target:{value:'draft@example.com'}});h.tree('BusinessPartnerEditor',props);await h.flush();
 const fresh=partnerHarness('business-partner-workspace','en',()=>({}),s);fresh.tree('BusinessPartnerEditor',props);await fresh.flush();tree=fresh.tree('BusinessPartnerEditor',props);assert.equal(find(tree,n=>n.props?.id==='bp-legal_name').props.value,'Unsaved');assert.equal(find(tree,n=>n.props?.id==='bp-contact-0-value').props.value,'draft@example.com');
});

test('existing draft keeps original revision on refresh and close clears it',async()=>{
 const s=storage(), props={...p,id:'bp1',onClose(){},onSaved(){}};
 let version=3;const record=()=>({id:'bp1',version,kind:'ORGANIZATION',status:'DRAFT',code:'B',legal_name:'Original',first_name:'',last_name:'',tax_identifiers:[],addresses:[],contact_channels:[]});
 const h=partnerHarness('business-partner-workspace','en',()=>record(),s);h.tree('BusinessPartnerEditor',props);await h.flush();let tree=h.tree('BusinessPartnerEditor',props);await h.flush();find(tree,n=>n.props?.id==='bp-legal_name').props.onChange({target:{value:'Changed'}});h.tree('BusinessPartnerEditor',props);await h.flush();
 version=4;const fresh=partnerHarness('business-partner-workspace','en',()=>record(),s);fresh.tree('BusinessPartnerEditor',props);await fresh.flush();tree=fresh.tree('BusinessPartnerEditor',props);assert.equal(find(tree,n=>n.props?.id==='bp-legal_name').props.value,'Changed');await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(fresh.calls.find(c=>c.method==='PUT')?.body.expectedVersion,3);
 tree=fresh.tree('BusinessPartnerEditor',props);find(tree,n=>n.props?.children==='Cancel').props.onClick();const again=partnerHarness('business-partner-workspace','en',()=>record(),s);again.tree('BusinessPartnerEditor',props);await again.flush();tree=again.tree('BusinessPartnerEditor',props);assert.equal(find(tree,n=>n.props?.id==='bp-legal_name').props.value,'Original');
});

test('superadmin recovery requires explicitly selected tenant',async()=>{
 const s=storage(), admin={...p,session:{...p.session,isSuperAdmin:true,selectedTenantId:'stale'}};
 const h=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}),s);let tree=h.tree('BusinessPartnerWorkspace',admin);await h.flush();find(tree,n=>Array.isArray(n.props?.children)&&n.props.children.includes('New Business Partner')).props.onClick();h.tree('BusinessPartnerWorkspace',admin);await h.flush();assert.equal(s.length,0);
});

test('explicit reset clears only the selected user and tenant recovery',async()=>{
 const s=storage(), make=async(props:any)=>{const h=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}),s);const tree=h.tree('BusinessPartnerWorkspace',props);await h.flush();find(tree,n=>Array.isArray(n.props?.children)&&n.props.children.includes('New Business Partner')).props.onClick();h.tree('BusinessPartnerWorkspace',props);await h.flush();return h;};
 const h=await make(p);const other={...p,session:{...p.session,id:'other-user'}};await make(other);assert.equal(s.length,2);h.components.resetBusinessPartnerRecovery(p.session);assert.equal(s.length,1);const fresh=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}),s);fresh.tree('BusinessPartnerWorkspace',other);await fresh.flush();assert.equal(fresh.tree('BusinessPartnerWorkspace',other).type,fresh.components.BusinessPartnerEditor);
});
test('logout clears all recoveries belonging to the user only',async()=>{
 const s=storage(), make=async(props:any)=>{const h=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}),s);h.tree('BusinessPartnerWorkspace',props);await h.flush();h.tree('BusinessPartnerWorkspace',props);await h.flush();return h;};
 const h=await make(p);await make({...p,session:{...p.session,tenantId:'other'}});await make({...p,session:{...p.session,id:'other-user'}});
 assert.equal(s.length,3);h.components.clearBusinessPartnerRecoveries(p.session);assert.equal(s.length,1);
});

test('logout strips personal data but retains an uncertain create guard for the same user and tenant',async()=>{
 const s=storage(), props={...p,id:null,onClose(){},onSaved(){}};
 const h=partnerHarness('business-partner-workspace','en',(_path,method)=>{if(method==='POST')throw Error('lost');return {};},s);
 h.tree('BusinessPartnerEditor',props);await h.flush();let tree=h.tree('BusinessPartnerEditor',props);find(tree,n=>n.props?.id==='bp-legal_name').props.onChange({target:{value:'Private Name'}});tree=h.tree('BusinessPartnerEditor',props);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});
 h.components.clearBusinessPartnerRecoveries(p.session);
 const key=`bp-refresh:v1:${encodeURIComponent(p.session.id)}:tenant`;assert.deepEqual(JSON.parse(s.getItem(key)!),{editor:{id:null},draft:{id:null,createUncertain:true}});assert.doesNotMatch(s.getItem(key)!,/Private Name/);
 const fresh=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}),s);fresh.tree('BusinessPartnerWorkspace',p);await fresh.flush();assert.equal(fresh.tree('BusinessPartnerWorkspace',p).type,fresh.components.BusinessPartnerEditor);
 const editor=partnerHarness('business-partner-workspace','en',()=>({}),s);editor.tree('BusinessPartnerEditor',props);await editor.flush();tree=editor.tree('BusinessPartnerEditor',props);assert.equal(find(tree,n=>n.props?.id==='bp-legal_name').props.value,'');await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(editor.calls.filter(c=>c.method==='POST').length,0);assert.ok(find(tree,n=>n.props?.role==='alert'));
});

test('logout preserves only the accepted record identifier for verification',async()=>{
 const s=storage(),props={...p,id:null,onClose(){},onSaved(){}};
 const h=partnerHarness('business-partner-workspace','en',(_path,method)=>{if(method==='POST')return {id:'bp-created'};throw Error('read lost');},s);
 h.tree('BusinessPartnerEditor',props);await h.flush();let tree=h.tree('BusinessPartnerEditor',props);find(tree,n=>n.props?.id==='bp-legal_name').props.onChange({target:{value:'Private Name'}});tree=h.tree('BusinessPartnerEditor',props);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});
 h.components.clearBusinessPartnerRecoveries(p.session);const key=`bp-refresh:v1:${encodeURIComponent(p.session.id)}:tenant`;assert.deepEqual(JSON.parse(s.getItem(key)!),{editor:{id:null},draft:{id:null,verificationId:'bp-created'}});
 let saved=0;const fresh=partnerHarness('business-partner-workspace','en',()=>({id:'bp-created'}),s),next={...props,onSaved(){saved++;}};fresh.tree('BusinessPartnerEditor',next);await fresh.flush();tree=fresh.tree('BusinessPartnerEditor',next);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(saved,1);assert.equal(fresh.calls.filter(c=>c.method==='POST').length,0);assert.equal(fresh.calls.at(-1)?.path,'/data/business-partners/bp-created');
});

test('lost create response survives refresh and cannot POST again',async()=>{
 const s=storage(), props={...p,id:null,onClose(){},onSaved(){}};
 let observed=false;
 const h=partnerHarness('business-partner-workspace','en',(_path,method)=>{if(method==='POST'){observed=JSON.stringify([...Array(s.length)].map((_,i)=>s.getItem(s.key(i)!))).includes('createUncertain');throw Error('lost');}return {};},s);
 h.tree('BusinessPartnerEditor',props);await h.flush();let tree=h.tree('BusinessPartnerEditor',props);find(tree,n=>n.props?.id==='bp-legal_name').props.onChange({target:{value:'Acme'}});tree=h.tree('BusinessPartnerEditor',props);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(observed,true,'uncertain marker persisted before POST');
 const fresh=partnerHarness('business-partner-workspace','en',()=>({}),s);fresh.tree('BusinessPartnerEditor',props);await fresh.flush();tree=fresh.tree('BusinessPartnerEditor',props);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(fresh.calls.filter(c=>c.method==='POST').length,0);assert.match(fresh.render('BusinessPartnerEditor',props),/may have been created/i);
});

test('refresh after accepted create retains verificationId and verifies without POST',async()=>{
 const s=storage(),props={...p,id:null,onClose(){},onSaved(){}};
 const h=partnerHarness('business-partner-workspace','en',(_path,method)=>{if(method==='POST')return {id:'bp-created'};throw Error('read lost');},s);
 h.tree('BusinessPartnerEditor',props);await h.flush();let tree=h.tree('BusinessPartnerEditor',props);find(tree,n=>n.props?.id==='bp-legal_name').props.onChange({target:{value:'Acme'}});tree=h.tree('BusinessPartnerEditor',props);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});
 let saved=0;const fresh=partnerHarness('business-partner-workspace','en',()=>({id:'bp-created'}),s),next={...props,onSaved(){saved++;}};fresh.tree('BusinessPartnerEditor',next);await fresh.flush();tree=fresh.tree('BusinessPartnerEditor',next);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(saved,1);assert.equal(fresh.calls.filter(c=>c.method==='POST').length,0);assert.equal(fresh.calls.at(-1)?.path,'/data/business-partners/bp-created');
});
test('unavailable session storage blocks creation',async()=>{
 const s={getItem(){throw Error('denied');},setItem(){throw Error('denied');}} as unknown as Storage, props={...p,id:null,onClose(){},onSaved(){}};
 const h=partnerHarness('business-partner-workspace','en',()=>({id:'x'}),s);h.tree('BusinessPartnerEditor',props);await h.flush();let tree=h.tree('BusinessPartnerEditor',props);find(tree,n=>n.props?.id==='bp-legal_name').props.onChange({target:{value:'Acme'}});tree=h.tree('BusinessPartnerEditor',props);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(h.calls.filter(c=>c.method==='POST').length,0);assert.match(h.render('BusinessPartnerEditor',props),/storage is unavailable/i);
});

 test('menu reset retains an uncertain creation and restores the blocked editor',async()=>{
 const s=storage(),props={...p,id:null,onClose(){},onSaved(){}};
 const h=partnerHarness('business-partner-workspace','en',(_path,method)=>{if(method==='POST')throw Error('lost');return {};},s);
 h.tree('BusinessPartnerEditor',props);await h.flush();let tree=h.tree('BusinessPartnerEditor',props);find(tree,n=>n.props?.id==='bp-legal_name').props.onChange({target:{value:'Acme'}});tree=h.tree('BusinessPartnerEditor',props);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});
 h.components.resetBusinessPartnerRecovery(p.session);
 const fresh=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}),s);fresh.tree('BusinessPartnerWorkspace',p);await fresh.flush();tree=fresh.tree('BusinessPartnerWorkspace',p);assert.equal(tree.type,fresh.components.BusinessPartnerEditor);
 const editor=partnerHarness('business-partner-workspace','en',()=>({}),s);editor.tree('BusinessPartnerEditor',props);await editor.flush();tree=editor.tree('BusinessPartnerEditor',props);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(editor.calls.filter(c=>c.method==='POST').length,0);
});

test('pending creation blocks submission before recovery has been loaded',async()=>{
 const s=storage(), props={...p,id:null,onClose(){},onSaved(){}};
 s.setItem(`bp-refresh:v1:${encodeURIComponent(p.session.id)}:tenant`,JSON.stringify({draft:{id:null,createUncertain:true}}));
 const h=partnerHarness('business-partner-workspace','en',()=>({}),s);let tree=h.tree('BusinessPartnerEditor',props);find(tree,n=>n.props?.id==='bp-legal_name').props.onChange({target:{value:'Acme'}});tree=h.tree('BusinessPartnerEditor',props);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
});

test('HTTP 408 creation timeout remains uncertain after refresh',async()=>{
 const s=storage(),props={...p,id:null,onClose(){},onSaved(){}};
 const h=partnerHarness('business-partner-workspace','en',(_path,method)=>{if(method==='POST')throw new ApiError('timeout',408);return {};},s);h.tree('BusinessPartnerEditor',props);await h.flush();let tree=h.tree('BusinessPartnerEditor',props);find(tree,n=>n.props?.id==='bp-legal_name').props.onChange({target:{value:'Acme'}});tree=h.tree('BusinessPartnerEditor',props);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});
 const fresh=partnerHarness('business-partner-workspace','en',()=>({}),s);fresh.tree('BusinessPartnerEditor',props);await fresh.flush();tree=fresh.tree('BusinessPartnerEditor',props);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(fresh.calls.filter(c=>c.method==='POST').length,0);
});
