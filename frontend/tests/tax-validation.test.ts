import test from 'node:test';
import assert from 'node:assert/strict';
import {blankTaxVersion,taxDateValid,taxRateValid,validateTaxVersion,validateTaxVersions,taxNatureChoices,taxCreatePayload,taxMetadataPayload,advanceTaxEditor,readTaxState,resetTaxState,taxKey,taxDefaults,type TaxCode,type TaxEditor,type TaxTreatment} from '../lib/tax.ts';
const version={...blankTaxVersion(),valid_from:'2026-01-01'};
const root:TaxCode={id:'r',tenant_id:'t',tax_type_id:'vat',country_id:'it',code:'VAT22',name:'IVA',description:null,is_active:true,version:4,created_at:'2026-01-01',updated_at:'2026-01-01',versions:[version]};
const editor:TaxEditor={id:'r',expectedVersion:4,original:root,values:{name:'Bozza',code:'VAT22',description:'test',tax_type_id:'vat',country_id:'it'},versions:[version],readonly:false};
test('fresh filters default to the user-local calendar day while explicit empty and future dates recover',()=>{
 const old=process.env.TZ;
 try {
  for(const [zone,expected] of [['America/Los_Angeles','2026-11-24'],['Pacific/Kiritimati','2026-11-25']]){
   process.env.TZ=zone;assert.equal(taxDefaults(new Date('2026-11-25T01:30:00Z')).date,expected);
  }
 }finally{if(old===undefined)delete process.env.TZ;else process.env.TZ=old;}
 const storage=(saved:unknown)=>({getItem:()=>JSON.stringify(saved)});
 assert.equal(readTaxState(storage(null),'k').date,taxDefaults().date);
 assert.equal(readTaxState(storage({date:''}),'k').date,'');
 assert.equal(readTaxState(storage({date:'2030-04-30'}),'k').date,'2030-04-30');
 assert.equal(readTaxState(storage({}),'k').date,taxDefaults().date);
});
test('rates remain exact decimal strings and respect numeric(9,6)',()=>{
 for(const value of ['0','0.000001','22.000000','999.999999','00022.000000'])assert.equal(taxRateValid(value),true,value);
 for(const value of ['','-1','1000','1.0000001','1e2','22,5',' 22','NaN','Infinity'])assert.equal(taxRateValid(value),false,value);
 assert.equal(validateTaxVersion({...version,rate:'0'},'IT',[]),'tax_invalid_rate');
 assert.equal(validateTaxVersion({...version,rate:'22.000001'},'IT',[]),null);
});
test('legal references accept at most 255 characters including recovered drafts',()=>{
 assert.equal(validateTaxVersion({...version,legal_reference:'L'.repeat(255)},'IT',[]),null);
 assert.equal(validateTaxVersion({...version,legal_reference:'L'.repeat(256)},'IT',[]),'tax_field_too_long');
});
test('Italian nature mappings distinguish excluded, margin, other EU and exempt',()=>{
 const mappings:[TaxTreatment,string][]=[['EXCLUDED','N1'],['OUT_OF_SCOPE','N2.1'],['NON_TAXABLE','N3.1'],['EXEMPT','N4'],['MARGIN','N5'],['REVERSE_CHARGE','N6.3'],['OTHER_EU','N7']];
 const natures=mappings.map(([_,code])=>({id:code,country_id:'it',code,valid_from:'2021-01-01',valid_to:null}));
 for(const [treatment,nature] of mappings){assert.equal(validateTaxVersion({...version,rate:'0',treatment,tax_nature_code_id:nature},'IT',natures),null);assert.deepEqual(taxNatureChoices(natures,'it','IT',treatment).map(n=>n.code),[nature]);}
 assert.equal(validateTaxVersion({...version,rate:'0',treatment:'EXEMPT',tax_nature_code_id:'N5'},'IT',natures),'tax_invalid_nature');
 assert.equal(validateTaxVersion({...version,rate:'0',treatment:'ZERO_RATED'},'IT',natures),'tax_zero_rated_not_applicable');
 assert.equal(validateTaxVersion({...version,rate:'0',treatment:'ZERO_RATED'},'FR',[]),null);
 assert.equal(validateTaxVersion({...version,tax_nature_code_id:'N1'},'IT',natures),'tax_invalid_rate');
});
test('periods use calendar dates, inclusive ends, atomic initial versions',()=>{
 assert.equal(taxDateValid('2026-02-29'),false);assert.equal(taxDateValid('2028-02-29'),true);
 assert.equal(validateTaxVersion({...version,valid_to:'2025-12-31'},'IT',[]),'tax_invalid_period');
 assert.equal(validateTaxVersions([],'IT',[]),'initialVersionRequired');
 assert.equal(validateTaxVersions([version,{...version,valid_from:'2027-01-01'}],'IT',[]),'tax_version_overlap');
 assert.equal(validateTaxVersions([{...version,valid_to:'2026-12-31'},{...version,valid_from:'2027-01-01'}],'IT',[]),null);
 const result=taxCreatePayload({...editor,id:null,expectedVersion:0});assert.equal(result.versions[0].rate,'22');assert.equal(result.values.code,'VAT22');
 assert.deepEqual(taxMetadataPayload(editor),{values:{name:'Bozza',description:'test'},expectedVersion:4});
});
test('schedule advances only its own original revision and preserves metadata draft',()=>{
 const advanced=advanceTaxEditor(editor,{...root,version:5},4);
 assert.equal(advanced.expectedVersion,5);assert.deepEqual(advanced.values,editor.values);
 assert.equal(advanceTaxEditor(editor,{...root,version:8},3),editor);
 assert.equal(advanceTaxEditor(editor,{...root,id:'other',version:5},4),editor);
});
test('refresh retains drafts, dialog/tab/filters and original token; reset preserves pending',()=>{
 const values=new Map<string,string>();const storage={getItem:(k:string)=>values.get(k)??null,removeItem:(k:string)=>{values.delete(k);}};const key=taxKey('u','t');
 assert.notEqual(key,taxKey('u','t2'));assert.notEqual(key,taxKey('u2','t'));
 const saved={...taxDefaults(),search:'IVA',tab:'versions',date:'2026-11-25',editor,versionDraft:version,installDate:'2026-01-01'};
 values.set(key,JSON.stringify(saved));assert.deepEqual(readTaxState(storage,key),saved);
 values.set(key+':pending','1');resetTaxState(storage,key);assert.equal(readTaxState(storage,key).editor?.expectedVersion,4);
 values.delete(key+':pending');resetTaxState(storage,key);assert.equal(values.has(key),false);
 values.set(key,'garbage');assert.deepEqual(readTaxState(storage,key),taxDefaults());
 values.set(key,JSON.stringify({...saved,editor:{...editor,expectedVersion:undefined}}));assert.equal(readTaxState(storage,key).editor,null);
});
