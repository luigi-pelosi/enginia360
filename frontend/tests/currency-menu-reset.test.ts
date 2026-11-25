import test from 'node:test';
import assert from 'node:assert/strict';
import {harness, session, find} from './workspace-harness.ts';

test('clicking Payments again remounts its nested workspace', () => {
 const initial={0:{...session,isSuperAdmin:true,permissions:['payment-methods.read']},1:false,5:[{key:'payments',fields:[]}],6:'payments',7:'t'};
 const h=harness('en',initial);
 const tree=h.components.default();
 const nav=find(tree,n=>n.type?.name==='WorkspaceNavigation');
 const child=find(tree,n=>n.type?.name==='PaymentsWorkspace');
 assert.ok(nav); assert.ok(child);
 const navTree=nav.type(nav.props);
 const menuButton=find(navTree,n=>typeof n.props?.onClick==='function' && find(n,c=>c.type==='span' && c.props?.children==='Payments'));
 assert.ok(menuButton); menuButton.props.onClick();
 const entry=Object.entries(h.updates).find(([,v])=>typeof v==='function');
 assert.ok(entry);
 const next=harness('en',{...initial,[entry[0]]:1});
 const updated=find(next.components.default(),n=>n.type?.name==='PaymentsWorkspace');
 assert.notEqual(child.key,updated.key);
});
