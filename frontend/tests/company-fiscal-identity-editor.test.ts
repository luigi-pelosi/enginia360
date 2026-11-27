import test from 'node:test';
import assert from 'node:assert/strict';
import {harness,find,session} from './workspace-harness.ts';

const resource={key:'companies',fields:[{name:'name',type:'text',required:true},{name:'is_enabled',type:'boolean',required:false}]};
for(const locale of ['it','en'])test(`Company general omits fiscal identities and filters retired fields from recovery (${locale})`,async()=>{
 const storage=new Map([['workspace:u:t:record:companies',JSON.stringify({kind:'edit',id:'c',baseline:{name:'Company',is_enabled:true,tax_code:'LEGACY'},values:{name:'Draft',is_enabled:true,tax_code:'LEGACY'}})]]);
 const h=harness(locale,{},()=>({id:'c',tenant_id:'t',name:'Draft',is_enabled:true}),storage,undefined,true);
 const props={resource,row:{id:'c',name:'Company',is_enabled:true},canWrite:true,session:{...session,isSuperAdmin:false,tenantId:'t',permissions:['companies.read','companies.update']},tenant:'t',scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:String};
 const render=()=>h.tree('RecordEditor',props);
 for(let i=0;i<4;i++){render();await h.flush();}
 const tree=render();
 assert.equal(find(tree,node=>node.props?.id==='field-tax_code'),undefined);
 assert.equal(find(tree,node=>node.props?.id==='field-vat_number'),undefined);
 const saved=JSON.parse(storage.get('workspace:u:t:record:companies')!);assert.equal(Object.hasOwn(saved.values,'tax_code'),false);
 await find(tree,node=>node.props?.id==='record-form').props.onSubmit({preventDefault(){}});
 assert.deepEqual(h.apiCalls,['/data/companies/c/save']);
 assert.deepEqual(JSON.parse(JSON.stringify(h.apiPayloads)),[{values:{name:'Draft'}}]);
});
