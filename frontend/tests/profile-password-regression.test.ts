import test from 'node:test';
import assert from 'node:assert/strict';
import {harness,find,session} from './workspace-harness.ts';
import {passwordValidation} from '../lib/password.ts';

test('mandatory password gate still precedes personal profile and keeps existing password form',()=>{
 const h=harness('it',{0:{...session,mustChangePassword:true},1:false,18:true});const tree=h.components.default();
 assert.ok(find(tree,n=>n.type?.name==='PasswordForm'));
 assert.equal(find(tree,n=>n.type?.name==='ProfileDialog'),undefined);
 assert.equal(find(tree,n=>n.props?.id==='personal-profile-menu-item'),undefined);
});

test('forced self-change and administrative reset retain their existing endpoints and payloads',async()=>{
 for(const reset of [false,true]){
  const h=harness('it',{0:'old password',1:'new password long enough',2:'new password long enough'});
  const tree=h.components.PasswordForm({resetId:reset?'other-user':undefined,scope:(path:string)=>path+'?tenantId=chosen',onSaved:async()=>{},onError:()=> 'error'});
  await tree.props.onSubmit({preventDefault(){}});
  assert.deepEqual(h.apiCalls,[reset?'/users/other-user/password?tenantId=chosen':'/auth/password']);
  assert.deepEqual(JSON.parse(JSON.stringify(h.apiPayloads[0])),reset?{newPassword:'new password long enough'}:{currentPassword:'old password',newPassword:'new password long enough'});
 }
 assert.equal(passwordValidation('short','short'),'passwordMinimum');
 assert.equal(passwordValidation('new password long','different'),'passwordMismatch');
});

test('profile form uses localized messages and a single Save in both languages',async()=>{
 const {driver}=await import('./profile-dialog-harness.ts');
 for(const locale of ['it','en']){
  const h=driver(undefined,locale);const tree=await h.load();
  const labels:any[]=[];
  function walk(node:any){if(!node||typeof node!=='object')return;if(node.props?.type==='submit')labels.push(node.props.children);for(const child of [node.props?.children].flat(Infinity))walk(child)}
  walk(tree);assert.deepEqual(labels,[locale==='it'?'Salva':'Save']);
 }
});
