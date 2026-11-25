import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {itemHarness,itemOptions,itemSession,root,CatalogApiError} from './catalog-items-harness.ts';
import {itemEditor} from '../lib/catalog-items.ts';
import {catalogKey} from '../lib/catalog.ts';

const invalid=['A-B','',' ',' A','A ','A B','A_B','A.B','é','Å','中','Ａ','١','A\n','A\t','A'.repeat(41)];
const messages=(locale:string)=>JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8')).catalogItems;
async function open(h:ReturnType<typeof itemHarness>,existing:boolean){
 await h.settle();
 if(existing){await h.action('Modifica Item A').props.onClick();await h.settle();}
 else{await h.click('catalog-item-new');await h.edit('item-name','Manual item');await h.select('item-category-id','category');await h.select('item-base-uom','g');}
}
for(const existing of [false,true])for(const locale of ['it','en'])test(`invalid manual code blocks before confirmation and all requests (${existing?'edit':'new'}, ${locale})`,async()=>{
 const h=itemHarness(undefined,{locale});
 await h.settle();
 if(existing){await h.action(locale==='it'?'Modifica Item A':'Edit Item A').props.onClick();await h.settle();}
 else{await h.click('catalog-item-new');await h.edit('item-name','Manual item');await h.select('item-category-id','category');await h.select('item-base-uom','g');}
 await h.select('item-status','ACTIVE');
 for(const code of invalid){
  await h.edit('item-code',code);assert.equal(h.state.editor!.values.code,code,'typing must not sanitize');
  const before=h.calls.length;await h.submit();
  assert.equal(h.byId('item-code').props['aria-invalid'],true,JSON.stringify(code));
  assert.equal(h.byId('item-field-error').props.children,messages(locale).manualCodeInvalid);
  assert.equal(h.byId('item-activation-confirm'),undefined);assert.equal(h.calls.length,before,'preflight must not request');assert.equal(h.pending,null);
 }
});

test('manual input exposes exact pattern/limit and delegates native validation to preflight',async()=>{
 const h=itemHarness();await open(h,false);
 assert.equal(h.byId('item-code').props.maxLength,40);assert.equal(h.byId('item-code').props.pattern,'[A-Za-z0-9]{1,40}');
 assert.equal(h.find(n=>n.type==='form').props.noValidate,true);
});

for(const existing of [false,true])for(const code of ['a','Z','0','Abc09','aZ9'.repeat(13)+'X'])test(`valid exact-case manual code is sent unchanged (${existing?'edit':'new'} ${code.length})`,async()=>{
 let record=root();const h=itemHarness((path,method,body)=>{if(method!=='GET'){record={...record,...body.values,version:5};return record;}if(path.startsWith('/catalog/items/'))return record;});
 await open(h,existing);await h.select('item-status','SUSPENDED');await h.edit('item-code',code);await h.submit();
 const writes=h.calls.filter(c=>c.method!=='GET');assert.equal(writes.length,1);assert.equal(writes[0].body.values.code,code);
});

for(const mode of ['MANUAL','AUTO'] as const)for(const code of ['ART-'+ 'X'.repeat(43),'SRV-00001','à legacy code'])test(`unchanged historical ${mode} code remains savable: ${code}`,async()=>{
 let record=root({code});const h=itemHarness((path,method,body)=>{if(method==='PUT'){record={...record,...body.values,version:5};return record;}if(path.startsWith('/catalog/items/'))return record;},{record,options:{...itemOptions,numbering:{GOOD:{mode}}}});
 await open(h,true);assert.equal(h.byId('item-code').props.value,code);
 if(mode==='AUTO'){assert.equal(h.byId('item-code').props.disabled,true);assert.equal(h.byId('item-code').props.maxLength,undefined);assert.equal(h.byId('item-code').props.pattern,undefined);}
 await h.edit('item-name','Unrelated edit');await h.submit();const writes=h.calls.filter(c=>c.method!=='GET');assert.equal(writes.length,1);assert.equal(writes[0].body.values.code,code);
});

for(const existing of [false,true])test(`recovered invalid manual draft is blocked (${existing?'edit':'new'})`,async()=>{
 const editor=itemEditor(root({id:existing?'item-a':''}));editor.values.code='bad-code';editor.statusDraft='ACTIVE';
 const storage=new Map([[catalogKey(itemSession.id,itemSession.tenantId!,'catalog-items'),JSON.stringify({editor})]]);
 const h=itemHarness(undefined,{storage});await h.settle();const before=h.calls.length;await h.submit();assert.equal(h.byId('item-code').props['aria-invalid'],true);assert.equal(h.calls.length,before);assert.equal(h.byId('item-activation-confirm'),undefined);
});

for(const locale of ['it','en'])test(`backend manual-code error resolves to same localized message (${locale})`,async()=>{
 const text=messages(locale);assert.equal(typeof text.manualCodeInvalid,'string');assert.equal(text.catalog_item_manual_code_invalid,text.manualCodeInvalid);
 const h=itemHarness((_path,method)=>{if(method==='POST')throw new CatalogApiError('catalog_item_manual_code_invalid',400,'code');},{locale});
 await h.settle();await h.click('catalog-item-new');await h.edit('item-name','Valid');await h.select('item-category-id','category');await h.select('item-base-uom','g');await h.select('item-status','SUSPENDED');await h.edit('item-code','Ab9');await h.submit();assert.equal(h.byId('item-code').props['aria-invalid'],true);assert.ok(String(h.byId('item-field-error').props.children).startsWith(text.manualCodeInvalid));
});
