import test from 'node:test';
import assert from 'node:assert/strict';
import {driver,find,ownProfile,session} from './profile-dialog-harness.ts';
const json=(v:any)=>JSON.parse(JSON.stringify(v));
const submitButton=(tree:any)=>find(tree,n=>n.props?.type==='submit');

test('personal and optional password drafts share one atomic save, CSRF/session refresh, and stored language application',async()=>{
 const h=driver((path,method)=>path==='/session'?{...session,preferredLanguage:'en',selectedTenantId:'chosen'}:method==='PUT'?{...ownProfile,preferred_language:'en'}:ownProfile);
 let tree=await h.load();
 h.change(tree,'profile-last_name','Byron');
 find(tree,n=>typeof n.props?.onValueChange==='function').props.onValueChange('en');
 for(const [name,value] of [['current','old password'],['new','new password long enough'],['confirm','new password long enough']]) {
  h.change(h.render(),`profile-password-${name}`,value);
 }
 tree=h.render();
 assert.equal(submitButton(tree).props.disabled,false);
 await h.submit(tree);
 const put=h.calls.find(c=>c.method==='PUT')!;
 assert.deepEqual(json(put),{path:'/profile',method:'PUT',body:{values:{last_name:'Byron',preferred_language:'en'},currentPassword:'old password',newPassword:'new password long enough'}});
 assert.ok(!('confirmPassword' in put.body));
 assert.deepEqual(h.events,['/profile','/profile','csrf','/session','saved','close','reload']);
 assert.equal(h.document.cookie,'locale=en; Path=/; Max-Age=31536000; SameSite=Strict');
});

test('required personal fields, email/date/language and password rules block both UI and synthetic submission',async()=>{
 const cases:Array<[string,string]>= [['first_name','  '],['last_name',''],['email','wrong'],['email','x@local'],['date_of_birth','2025-02-30'],['date_of_birth','3000-01-01'],['phone_number','1'.repeat(51)],['first_name','x'.repeat(201)]];
 for(const [name,value] of cases){
  const h=driver();let tree=await h.load(); h.change(tree,`profile-${name}`,value); tree=h.render();
  assert.equal(submitButton(tree).props.disabled,true,`${name} invalid disables Save`);
  await h.submit(tree);assert.equal(h.calls.length,1,`${name} rejected synthetically`);
 }
 const invalidLanguage=driver();let tree=await invalidLanguage.load();find(tree,n=>typeof n.props?.onValueChange==='function').props.onValueChange('fr');tree=invalidLanguage.render();assert.equal(submitButton(tree).props.disabled,true);await invalidLanguage.submit(tree);assert.equal(invalidLanguage.calls.length,1);
 for(const [current,password,confirm] of [['','new password long','new password long'],['old','short','short'],['old','new password long','different'],['same password long','same password long','same password long'],['old','              ','              ']]){
  const h=driver();let tree=await h.load();h.change(tree,'profile-first_name','Grace');
  for(const [name,value] of [['current',current],['new',password],['confirm',confirm]])h.change(h.render(),`profile-password-${name}`,value);
  tree=h.render();assert.equal(submitButton(tree).props.disabled,true,JSON.stringify([current,password,confirm]));await h.submit(tree);assert.equal(h.calls.length,1);
 }
});

test('current password autofill never activates optional password change or blocks personal data save',async()=>{
 for(const current of ['autofilled existing password',' '.repeat(14)]){
  const h=driver();let tree=await h.load();h.change(tree,'profile-password-current',current);tree=h.render();
  assert.equal(submitButton(tree).props.disabled,true,'autofill alone is not a changed draft');
  await h.submit(tree);assert.equal(h.calls.filter(c=>c.method==='PUT').length,0);
  h.change(tree,'profile-first_name','Grace');tree=h.render();
  assert.equal(submitButton(tree).props.disabled,false,'personal changes do not require a new password');
  assert.equal(find(tree,n=>n.props?.id==='profile-password-new').props.required,false);
  assert.equal(find(tree,n=>n.props?.id==='profile-password-new').props['aria-invalid'],false);
  await h.submit(tree);assert.deepEqual(json(h.calls.find(c=>c.method==='PUT')?.body),{values:{first_name:'Grace'}});
  assert.ok(!h.events.includes('csrf'),'no credential/session rotation for personal data');
 }
});

test('existing current password is preserved byte for byte, including whitespace',async()=>{
 const h=driver();let tree=await h.load();
 for(const [name,value] of [['current',' '.repeat(14)],['new','replacement password long'],['confirm','replacement password long']])h.change(tree,`profile-password-${name}`,value);
 tree=h.render();assert.equal(submitButton(tree).props.disabled,false);await h.submit(tree);
 assert.equal(h.calls.find(c=>c.method==='PUT')?.body.currentPassword,' '.repeat(14));
});

test('password only update omits empty values and counts Unicode code points for minimum',async()=>{
 const h=driver();let tree=await h.load();for(const [name,value] of [['current','old password'],['new','😀'.repeat(7)],['confirm','😀'.repeat(7)]])h.change(tree,`profile-password-${name}`,value);
 tree=h.render();assert.equal(submitButton(tree).props.disabled,true);
 for(const name of ['new','confirm'])h.change(tree,`profile-password-${name}`,'😀'.repeat(14));
 await h.submit(h.render());assert.deepEqual(json(h.calls.find(c=>c.method==='PUT')?.body),{currentPassword:'old password',newPassword:'😀'.repeat(14)});
});
test('committed update retries session readback without issuing a second write after refresh failure',async()=>{
 let refreshes=0;
 const h=driver((path,method)=>{if(path==='/session' && ++refreshes===1)throw Error('network_error');return path==='/session'?session:ownProfile});
 let tree=await h.load();h.change(tree,'profile-first_name','Grace');await h.submit(h.render());
 assert.ok(!h.events.includes('close'));
 await h.submit(h.render());assert.equal(h.calls.filter(c=>c.method==='PUT').length,1,'a committed mutation is not replayed');assert.ok(h.events.includes('close'));
});

test('failed PUT retains personal/password drafts for retry; Cancel and Escape never write',async()=>{
 let reject=true;
 const h=driver((path,method)=>{if(method==='PUT' && reject)throw Error('current_password_invalid');return path==='/session'?session:ownProfile});
 let tree=await h.load();h.change(tree,'profile-phone_number','');h.change(tree,'profile-first_name','Grace');
 for(const [name,value] of [['current','incorrect password'],['new','new password long'],['confirm','new password long']])h.change(tree,`profile-password-${name}`,value);
 await h.submit(h.render());tree=h.render();
 assert.equal(find(tree,n=>n.props?.id==='profile-first_name').props.value,'Grace');assert.equal(find(tree,n=>n.props?.id==='profile-password-current').props.value,'incorrect password');
 assert.ok(find(tree,n=>n.props?.role==='alert'));
 assert.equal(h.events.includes('saved'),false);reject=false;await h.submit(tree);
 assert.deepEqual(json(h.calls.filter(c=>c.method==='PUT').map(c=>c.body)),Array(2).fill({values:{first_name:'Grace',phone_number:null},currentPassword:'incorrect password',newPassword:'new password long'}));
 for(const escape of [false,true]){const cancel=driver();const tree=await cancel.load();cancel.change(tree,'profile-first_name','Unsaved');if(escape)tree.props.onOpenChange(false);else find(tree,n=>n.props?.id==='profile-cancel').props.onClick();assert.equal(cancel.calls.length,1);assert.deepEqual(cancel.events,['/profile','close']);}
});

test('dialog load failure and pending load never allow writes; in-flight Escape cannot discard submitted draft',async()=>{
 const failed=driver(()=>{throw Error('network_error')});const errorTree=await failed.load();assert.equal(submitButton(errorTree).props.disabled,true);await failed.submit(errorTree);assert.equal(failed.calls.length,1);
 let finish!:(value:any)=>void;const pending=driver(()=>new Promise(resolve=>{finish=resolve}));let tree=await pending.load();assert.equal(submitButton(tree).props.disabled,true);await pending.submit(tree);assert.equal(pending.calls.length,1);finish(ownProfile);
 let release!:(value:any)=>void;const saving=driver((path,method)=>method==='PUT'?new Promise(resolve=>{release=resolve}):path==='/session'?session:ownProfile);tree=await saving.load();saving.change(tree,'profile-first_name','Grace');const submit=saving.submit(saving.render());saving.render().props.onOpenChange(false);assert.ok(!saving.events.includes('close'));saving.change(saving.render(),'profile-first_name','Discard');assert.equal(find(saving.render(),n=>n.props?.id==='profile-first_name').props.value,'Grace');release(ownProfile);await submit;
});

test('dedicated dialog loads own profile unscoped and saves only changed whitelist values once',async()=>{
 let release!:(v:any)=>void;
 const h=driver((path,method)=>method==='PUT'?new Promise(resolve=>{release=resolve}):path==='/session'?{...session,displayName:'Grace Lovelace',selectedTenantId:'preserved'}:ownProfile);
 let tree=await h.load();
 assert.deepEqual(h.calls.map(c=>c.path),['/profile']);
 assert.equal(find(tree,n=>n.props?.id==='profile-username').props.readOnly,true);
 assert.equal(find(tree,n=>n.props?.type==='submit').props.disabled,true);
 h.change(tree,'profile-first_name','Grace');tree=h.render();
 const one=h.submit(tree);const two=h.submit(tree);
 assert.equal(h.calls.length,2,'synchronous double submit lock');
 assert.deepEqual(json(h.calls[1]),{path:'/profile',method:'PUT',body:{values:{first_name:'Grace'}}});
 assert.equal(find(h.render(),n=>n.props?.id==='profile-first_name').props.disabled,true);
 release({...ownProfile,first_name:'Grace'});await Promise.all([one,two]);
 assert.deepEqual(h.calls.map(c=>c.path),['/profile','/profile','/session']);
 assert.ok(h.events.includes('saved'));assert.ok(h.events.includes('close'));assert.ok(!h.events.includes('csrf'));
});
