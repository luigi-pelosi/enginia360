import test from 'node:test';
import assert from 'node:assert/strict';
import * as items from '../lib/catalog-items.ts';
import {itemHarness,itemSession,root} from './catalog-items-harness.ts';
const values={is_enabled:true,is_sellable:true,is_purchasable:false,track_stock:false,default_sales_uom_id:null,default_purchase_uom_id:null};
const metadata=[{id:'a',name:'A',code:null,is_enabled:true,permissions:['read','create']},{id:'b',name:'B',code:null,is_enabled:true,permissions:['read','create']}];
const session={...itemSession,permissions:[...itemSession.permissions,'catalog-item-companies.read','catalog-item-companies.create']};
test('new root exposes Companies before the first save and remains opt-in',async()=>{
 const h=itemHarness(undefined,{session});await h.settle();await h.click('catalog-item-new');
 assert.ok(h.byId('item-tab-companies'));assert.equal(items.itemCreation(h.state.editor!).companies,undefined);
 h.unmount();
});
test('creation carries two local company configurations inside the single root body',()=>{
 const editor={...items.itemEditor(root({id:''})),companyDrafts:[{company_id:'a',values},{company_id:'b',values:{...values,is_sellable:false}}]};
 assert.deepEqual(items.itemCreation(editor).companies,editor.companyDrafts);
});
test('type defaults copy actual lowercase fields and only GOOD supports stock',()=>{
 for(const kind of ['GOOD','SERVICE','INTANGIBLE','CHARGE'] as const){
  const type={id:'type',kind,default_sellable:false,default_purchasable:true,default_track_stock:true};
  const copied=items.itemCompanyInitial(type,kind);
  assert.equal(copied.is_sellable,false);assert.equal(copied.is_purchasable,true);assert.equal(copied.track_stock,kind==='GOOD');
  type.default_sellable=true;assert.equal(copied.is_sellable,false);
 }
});
test('company unit defaults require current active global and base or active local association',()=>{
 const editor={...items.itemEditor(root({id:'',base_uom_id:'g',units:[{id:'local',uom_id:'cf',is_active:true}]})),companyDrafts:[{company_id:'a',values:{...values,default_sales_uom_id:'cf' as string|null}}]};
 const opts={types:[],categories:[],brands:[],numbering:{},units:[{id:'g',is_active:true},{id:'cf',is_active:true},{id:'other',is_active:true},{id:'inactive',is_active:false}]};
 assert.deepEqual(items.itemCompanyUnits(editor.values.base_uom_id,editor.record.units,opts.units).map(r=>r.id),['g','cf']);
 assert.equal(items.itemCompanyDraftError(editor,opts,metadata),null);
 editor.record.units=[];
 assert.equal(items.itemCompanyDraftError(editor,opts,metadata),'draftUnitInvalid');
 assert.equal(editor.companyDrafts[0].values.default_sales_uom_id,'cf');
 editor.companyDrafts[0].values.default_sales_uom_id=null;
 assert.equal(items.itemCompanyDraftError(editor,opts,[{...metadata[0],is_enabled:false}]),'draftCompanyUnavailable');
 editor.record.kind='SERVICE';editor.companyDrafts[0].values.track_stock=true;
 assert.equal(items.itemCompanyDraftError(editor,opts,metadata),'draftStockInvalid');
});
