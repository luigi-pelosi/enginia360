import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';

test('company tax drafts select active VAT and explicit enabled establishment without a normative regime date',async()=>{
 const url=new URL('../lib/company-tax.ts',import.meta.url);assert.ok(existsSync(url),'company tax draft model is implemented');
 const m=await import('../lib/company-tax.ts');
 const refs={countries:[{id:'off',is_enabled:false,is_supported:true},{id:'unknown',is_enabled:true,is_supported:false},{id:'it',is_enabled:true,is_supported:true}],types:[{id:'old',code:'VAT',is_active:false},{id:'other',code:'OTHER',is_active:true},{id:'vat',code:'VAT',is_active:true}],regimes:[],registrationTypesByCountry:{it:['DOMESTIC']}};
 assert.deepEqual(m.companyTaxInitial(refs),{values:{tax_type_id:'vat',establishment_country_id:'it'},registrations:[]});
 assert.equal(m.companyTaxRegimeOptions(refs,'it','vat').length,0);
});

test('regime list recovery reset is isolated by authenticated user and effective tenant',async()=>{
 const m=await import('../lib/company-tax.ts');assert.equal(typeof m.clearTaxRegimeDraft,'function');
 const rows=new Map([[m.taxRegimeKey('u','t'),'filters'],[m.taxRegimeKey('u','other'),'keep']]);
 m.clearTaxRegimeDraft({removeItem:(key:string)=>{rows.delete(key);}},'u','t');assert.equal(rows.has(m.taxRegimeKey('u','t')),false);assert.equal(rows.size,1);
});

test('new company tax configuration prefers supported Italy regardless of lookup order',async()=>{
 const m=await import('../lib/company-tax.ts');
 const refs={countries:[{id:'fr',iso_code:'FR',is_enabled:true,is_supported:true},{id:'it',iso_code:'IT',is_enabled:true,is_supported:true}],types:[{id:'vat',code:'VAT',is_active:true}],regimes:[],registrationTypesByCountry:{}};
 assert.equal(m.companyTaxInitial(refs).values.establishment_country_id,'it');
 assert.equal(m.companyTaxInitial({...refs,countries:[{...refs.countries[1],is_enabled:false},refs.countries[0]]}).values.establishment_country_id,'fr');
 assert.equal(m.companyTaxInitial({...refs,countries:[{...refs.countries[1],is_supported:false},refs.countries[0]]}).values.establishment_country_id,'fr');
 assert.equal(m.companyTaxInitial({...refs,countries:[]}).values.establishment_country_id,'');
});

test('system regimes component exists as readonly list',()=>{assert.ok(existsSync(new URL('../components/tax-regimes.tsx',import.meta.url)),'readonly system regimes are implemented');});

test('formal identifiers are exact canonical input, never trimmed, case-folded or VIES claims',async()=>{const m=await import('../lib/company-tax.ts');assert.equal(typeof m.companyTaxIdentifier,'function');for(const [iso,value,valid] of [['IT','IT12345678901',true],['DE','DE123456789',true],['FR','FRAB123456789',true],['FR','FRII123456789',false],['IT','it12345678901',false],['IT',' IT12345678901',false],['US','US123',false]] as const)assert.equal(m.companyTaxIdentifier(iso,value),valid);});

test('root readback verifies complete child content and tenant ownership, not just matching revisions',async()=>{const m=await import('../lib/company-tax.ts');const root={id:'r',tenant_id:'t',company_id:'c',tax_type_id:'vat',establishment_country_id:'it',status:'DRAFT' as const,version:1,registrations:[]};assert.equal(m.companyTaxReadback(root,{...root},'t','c'),true);assert.equal(m.companyTaxReadback(root,{...root,status:'ACTIVE'},'t','c'),false);assert.equal(m.companyTaxReadback(root,{...root,tenant_id:'foreign'},'t','c'),false);assert.equal(m.companyTaxReadback(root,{...root,version:2},'t','c'),false);});

test('calendar validation rejects impossible dates and reversed inclusive periods',async()=>{const m=await import('../lib/company-tax.ts');assert.equal(m.companyTaxDate('2026-02-30'),false);assert.equal(m.companyTaxDate('2026-11-26'),true);assert.equal(m.companyTaxRange('2026-11-26','2026-11-25'),false);assert.equal(m.companyTaxRange('2026-11-26','2026-11-26'),true);assert.equal(m.companyTaxRange('2026-11-26',null),true);});

test('menu reset preserves pending command and original token while isolating subjects',async()=>{const m=await import('../lib/company-tax.ts');const marker={editor:{expectedVersion:4},pending:{body:{expectedVersion:4}}};const rows=new Map([[m.companyTaxKey('u','t','a'),JSON.stringify({editor:{}})],[m.companyTaxKey('u','t','b'),JSON.stringify(marker)],[m.companyTaxKey('u','other','a'),'{}']]);const storage={get length(){return rows.size;},key:(i:number)=>[...rows.keys()][i]??null,getItem:(k:string)=>rows.get(k)??null,removeItem:(k:string)=>{rows.delete(k);}};m.clearCompanyTaxDrafts(storage,'u','t');assert.equal(rows.has(m.companyTaxKey('u','t','a')),false);assert.deepEqual(JSON.parse(rows.get(m.companyTaxKey('u','t','b'))!),marker);assert.equal(rows.size,2);});
