import test from 'node:test';
import assert from 'node:assert/strict';
import {harness, session, find} from './workspace-harness.ts';

function selected(field: Record<string, unknown>, row: Record<string, unknown> | null = null, canWrite = true) {
  const resource = {key: 'companies', fields: [{name: 'code', type: 'select', required: true, options: ['first', 'second'], ...field}]};
  const h = harness();
  const tree = h.components.RecordEditor({resource, row, canWrite, session, tenant: 't', scope: (x: string) => x, load: async () => [], onClose() {}, onSaved: async () => {}, onError: String});
  return find(tree, node => node.props?.name === 'code').props.value;
}

test('new required static select initializes the first option in form state', () => {
  assert.equal(selected({}), 'first');
});

test('stored values, semantic defaults, optional fields and read-only forms are preserved', () => {
  assert.equal(selected({}, {id: '1', code: 'second'}), 'second');
  assert.equal(selected({defaultValue: 'second'}), 'second');
  assert.equal(selected({required: false}), '');
  assert.equal(selected({}, null, false), '');
  assert.equal(selected({options: ['', '__none__', 'second']}), 'second');
});

test('required reference selects first usable loaded value for a new record', async () => {
  const resource = {key: 'companies', fields: [{name: 'company_id', type: 'reference', required: true, reference: 'companies'}]};
  const h = harness();
  h.components.RecordEditor({resource, row: null, canWrite: true, session, tenant: 't', scope: (x: string) => x, load: async () => [{id: ''}, {id: 'one'}, {id: 'two'}], onClose() {}, onSaved: async () => {}, onError: String});
  h.effects[0]();
  h.effects[2]();
  await new Promise(resolve => setTimeout(resolve, 0));
  const update = h.updates[0];
  assert.equal(typeof update, 'function');
  assert.equal((update as Function)({company_id: ''}).company_id, 'one');
});


test('failed or cancelled lookup never chooses a reference', async () => {
  const resource = {key: 'companies', fields: [{name: 'company_id', type: 'reference', required: true, reference: 'companies'}]};
  for (const cancelled of [false, true]) {
    let resolve!: (value: unknown) => void, reject!: (reason: unknown) => void;
    const promise = new Promise((ok, fail) => {resolve = ok; reject = fail;});
    const h = harness();
    h.components.RecordEditor({resource, row: null, canWrite: true, session, tenant: 't', scope: (x: string) => x, load: () => promise, onClose() {}, onSaved: async () => {}, onError: String});
    h.effects[0]();
    const cleanup = h.effects[2]() as () => void;
    if (cancelled) {cleanup(); resolve([{id: 'one'}]);} else reject(new Error('unavailable'));
    await new Promise(done => setTimeout(done, 0));
    assert.equal(h.updates[0], undefined);
  }
});

test('reference default respects a value chosen before lookup completion', async () => {
  const resource = {key: 'companies', fields: [{name: 'company_id', type: 'reference', required: true, reference: 'companies'}]};
  const storage = new Map<string, string>();
  // Discover the exact recovery key via the editor's persistence effect.
  const h = harness('it', {}, {ids: []}, storage);
  h.components.RecordEditor({resource, row: null, canWrite: true, session, tenant: 't', scope: (x: string) => x, load: async () => [{id: 'one'}], onClose() {}, onSaved: async () => {}, onError: String});
  h.effects[0](); h.effects[2]();
  await new Promise(done => setTimeout(done, 0));
  const update = h.updates[0] as Function;
  assert.equal(update({company_id: 'chosen'}).company_id, 'chosen');
});
test('new site country default updates form state without overwriting recovery or a choice', () => {
 const resource={key:'sites',fields:[{name:'country_code',type:'select',required:true}]};
 const h=harness(); const props={resource,row:null,canWrite:true,session,tenant:'t',scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:String};
 const tree=h.components.RecordEditor(props);h.effects[0]();
 const country=find(tree,n=>n.type?.name==='SiteCountrySelect');
 assert.equal(typeof country.props.onDefault,'function');country.props.onDefault('IT');
 const update=h.updates[0] as Function;assert.equal(update({country_code:''}).country_code,'IT');assert.equal(update({country_code:'FR'}).country_code,'FR');
});
test('recovered blank country and touched blank remain intentional; edit and readonly have no default',()=>{
 const resource={key:'sites',fields:[{name:'country_code',type:'select',required:true}]};
 const props={resource,row:null,canWrite:true,session,tenant:'t',scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:String};
 const storage=new Map([['workspace:u:t:record:sites',JSON.stringify({kind:'create',values:{country_code:''}})]]);
 const h=harness('it',{}, {ids:[]},storage);let tree=h.components.RecordEditor(props);h.effects[0]();let country=find(tree,n=>n.type?.name==='SiteCountrySelect');country.props.onDefault('IT');assert.equal((h.updates[0] as Function)({country_code:''}).country_code,'');
 const h2=harness();tree=h2.components.RecordEditor(props);h2.effects[0]();country=find(tree,n=>n.type?.name==='SiteCountrySelect');country.props.onChange('');country.props.onDefault('IT');assert.equal((h2.updates[0] as Function)({country_code:''}).country_code,'');
 for(const change of [{row:{id:'1',country_code:''}},{canWrite:false}]){const h3=harness();tree=h3.components.RecordEditor({...props,...change});assert.equal(find(tree,n=>n.type?.name==='SiteCountrySelect').props.onDefault,undefined);}
});
test('reference default reaches actual save payload',async()=>{
 const resource={key:'companies',fields:[{name:'company_id',type:'reference',required:true,reference:'companies'}]};
 const props={resource,row:null,canWrite:true,session,tenant:'t',scope:(p:string)=>p,load:async()=>[{id:'one'}],onClose(){},onSaved:async()=>{},onError:String};
 const h=harness();h.components.RecordEditor(props);h.effects[0]();h.effects[2]();await new Promise(r=>setImmediate(r));
 const values=(h.updates[0] as Function)({company_id:''});
 const ready=harness('it',{0:values,4:false,13:true}, {id:'created'});
 const tree=ready.components.RecordEditor(props);await find(tree,n=>n.type==='form'&&n.props.id==='record-form').props.onSubmit({preventDefault(){}});
 assert.equal((ready.apiPayloads[0] as any)?.values?.company_id,'one');
});
test('site country default is sent in the create payload',async()=>{
 const resource={key:'sites',fields:[{name:'country_code',type:'select',required:true}]};
 const props={resource,row:null,canWrite:true,session,tenant:'t',scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:String};
 const h=harness();const tree=h.components.RecordEditor(props);h.effects[0]();find(tree,n=>n.type?.name==='SiteCountrySelect').props.onDefault('IT');
 const values=(h.updates[0] as Function)({country_code:''});const ready=harness('it',{0:values,4:false,13:true},{id:'new'});
 await find(ready.components.RecordEditor(props),n=>n.type==='form'&&n.props.id==='record-form').props.onSubmit({preventDefault(){}});
 assert.equal((ready.apiPayloads[0] as any)?.values?.country_code,'IT');
});
test('recovered blank reference is not defaulted after the lookup',async()=>{
 const resource={key:'companies',fields:[{name:'company_id',type:'reference',required:true,reference:'companies'}]};
 const storage=new Map([['workspace:u:t:record:companies',JSON.stringify({kind:'create',values:{company_id:''}})]]);
 const h=harness('it',{}, {ids:[]},storage);h.components.RecordEditor({resource,row:null,canWrite:true,session,tenant:'t',scope:(p:string)=>p,load:async()=>[{id:'one'}],onClose(){},onSaved:async()=>{},onError:String});
 h.effects[0]();h.effects[2]();await new Promise(r=>setImmediate(r));assert.equal((h.updates[0] as Function)({company_id:''}).company_id,'');
});
