import test from 'node:test';
import assert from 'node:assert/strict';
import {harness, find, session, source} from './workspace-harness.ts';

test('personal profile menu is available without grants, including global identity without tenant', () => {
  for (const global of [false, true]) {
    const h = harness('it', {0:{...session, isSuperAdmin:global, tenantId:global ? null : 't'},1:false});
    const tree = h.components.default();
    const trigger = find(tree, n => n.props?.['aria-label'] === 'Profilo personale');
    assert.ok(trigger, 'authenticated profile trigger independent of resources');
    const open = find(tree, n => n.props?.id === 'personal-profile-menu-item');
    assert.ok(open);
    open.props.onSelect();
    assert.equal(h.updates[18], true, 'reuse existing modal state slot');
    assert.ok(find(tree,n => n.props?.id === 'user-logout-menu-item'));
    assert.equal(find(tree,n=>n.props?.['aria-label']==='Cambia password'),undefined);
  }
  const dialogHarness=harness('it',{0:session,1:false,18:true});
  const profileDialog=find(dialogHarness.components.default(),n=>n.type?.name==='ProfileDialog');
  assert.ok(profileDialog,'profile menu state mounts separate dialog outside resource gates');
  profileDialog.props.onSaved({...session,displayName:'Updated'});
  assert.equal((dialogHarness.updates[0] as typeof session).displayName,'Updated');
  const navigation = source.slice(source.indexOf('function WorkspaceNavigation'),source.indexOf('function Notice'));
  assert.doesNotMatch(navigation,/SidebarFooter|session\.displayName|session\.username/);
});
