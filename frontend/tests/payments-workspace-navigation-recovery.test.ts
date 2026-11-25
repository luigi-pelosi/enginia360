import test from 'node:test';
import assert from 'node:assert/strict';
import {harness, session, find} from './workspace-harness.ts';

const user = {...session, id:'user:1', isSuperAdmin:true, permissions:['payment-methods.read']};
const states = {0:user,1:false,5:[{key:'payments',fields:[]}],6:'payments',7:'tenant:2'};
const recovery = 'payments-recovery:user%3A1:tenant%3A2';
const pending = 'payments-pending:user%3A1:tenant%3A2';
function open(storage: Map<string,string>) {return harness('en',states,{ids:[]},storage);}
function clickPayments(h: ReturnType<typeof open>) {
 const tree=h.components.default();
 const nav=find(tree,n=>n.type?.name==='WorkspaceNavigation');
 const button=find(nav.type(nav.props),n=>typeof n.props?.onClick==='function' && find(n,c=>c.type==='span' && c.props?.children==='Payments'));
 assert.ok(button); button.props.onClick();
 return tree;
}
test('effective tenant is passed and menu reset removes only its recovery, not pending',()=>{
 const storage=new Map([[recovery,'draft'],[pending,'1'],['payments-recovery:user%3A1:other','other'],['payments-recovery:other:tenant%3A2','private']]);
 const h=open(storage); const tree=clickPayments(h);
 assert.equal(storage.has(recovery),false); assert.equal(storage.get(pending),'1');
 assert.equal(find(tree,n=>n.type?.name==='PaymentsWorkspace').props.effectiveTenant,'tenant:2');
 assert.equal(storage.get('payments-recovery:user%3A1:other'),'other'); assert.equal(storage.get('payments-recovery:other:tenant%3A2'),'private');
});
test('rendering after reload does not clear payments recovery',()=>{
 const storage=new Map([[recovery,'draft']]); const h=open(storage); h.components.default(); assert.equal(storage.get(recovery),'draft');
});
test('logout clears only user payment drafts, retaining all pending markers',async()=>{
 const storage=new Map([[recovery,'draft'],[pending,'1'],['payments-recovery:user%3A1:other','draft2'],['payments-pending:user%3A1:other','1'],['payments-recovery:other:tenant%3A2','private']]);
 const h=open(storage); const tree=h.components.default();
 const logout=find(tree,n=>n.props?.id==='user-logout-menu-item'); assert.ok(logout); logout.props.onSelect();
 await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(storage.has(recovery),false); assert.equal(storage.has('payments-recovery:user%3A1:other'),false);
 assert.equal(storage.get(pending),'1'); assert.equal(storage.get('payments-pending:user%3A1:other'),'1'); assert.equal(storage.get('payments-recovery:other:tenant%3A2'),'private');
});
