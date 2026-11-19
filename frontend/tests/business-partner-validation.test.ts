import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createTranslator} from 'next-intl';
import {ApiError} from '../lib/api.ts';
import {partnerHarness,find,session as baseSession} from './business-partner-harness.ts';

const session={...baseSession,permissions:['business-partners.read','business-partners.create','business-partners.update']};

const byId=(tree:any,id:string)=>find(tree,n=>n.props?.id===id);
const form=(tree:any)=>find(tree,n=>n.type==='form');
const action=(tree:any,id:string)=>find(tree,n=>n.props?.['data-action']===id);
for(const locale of ['it','en']) test(`server fiscal errors identify the exact row and field and preserve the draft (${locale})`,async()=>{
 const messages=JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8'));
 const translate=createTranslator({locale,messages,namespace:'errors'});
 const p={session,scope:(s:string)=>s,onError:(e:any)=>translate(e.code),id:null,onClose(){},onSaved(){throw Error('invalid record saved');}};
 const failure=Object.assign(new ApiError('invalid_italian_vat',400),{field:'taxIdentifiers[1].value'});
 const h=partnerHarness('business-partner-workspace',locale,()=>{throw failure;});
 let tree=h.tree('BusinessPartnerEditor',p);
 byId(tree,'bp-legal_name').props.onChange({target:{value:'Officina prova'}});
 for(let i=0;i<2;i++) {tree=h.tree('BusinessPartnerEditor',p);action(tree,'add-tax').props.onClick();}
 tree=h.tree('BusinessPartnerEditor',p);
 byId(tree,'bp-tax-0-value').props.onChange({target:{value:'12345678901'}});
 tree=h.tree('BusinessPartnerEditor',p);
 byId(tree,'bp-tax-1-value').props.onChange({target:{value:'IT12345678901'}});
 tree=h.tree('BusinessPartnerEditor',p);await form(tree).props.onSubmit({preventDefault(){}});
 tree=h.tree('BusinessPartnerEditor',p);
 assert.equal(byId(tree,'bp-tax-1-value').props['aria-invalid'],true,'the rejected input must be identified');
 assert.equal(byId(tree,'bp-tax-1-value').props['aria-describedby'],'bp-tax-1-value-error');
 assert.equal(byId(tree,'bp-tax-0-value').props['aria-invalid'],undefined,'another row must not be marked');
 const html=h.render('BusinessPartnerEditor',p);
 assert.match(html,locale==='it'?/Identificativo fiscale 2 — Partita IVA/:/Tax identifier 2 — VAT number/);
 assert.match(html,locale==='it'?/Inserisci una partita IVA italiana di 11 cifre\./:/Enter an Italian VAT number with 11 digits\./);
 assert.doesNotMatch(html,/Verifica i dati inseriti|Check the entered data/);
 assert.equal(byId(tree,'bp-tax-1-value').props.value,'IT12345678901');
 byId(tree,'bp-tax-1-value').props.onChange({target:{value:'12345678902'}});
 tree=h.tree('BusinessPartnerEditor',p);
 assert.equal(byId(tree,'bp-tax-1-value').props['aria-invalid'],undefined,'a changed draft must not retain stale diagnostics');
});

test('local contact validation identifies the failing contact and the actual syntax rule',async()=>{
 const p={session,scope:(s:string)=>s,onError:(e:any)=>e.code,id:null,onClose(){},onSaved(){}};
 const h=partnerHarness();let tree=h.tree('BusinessPartnerEditor',p);
 action(tree,'add-contact').props.onClick();tree=h.tree('BusinessPartnerEditor',p);
 find(tree,n=>n.props?.value==='EMAIL'&&n.props?.onValueChange).props.onValueChange('PHONE');
 tree=h.tree('BusinessPartnerEditor',p);byId(tree,'bp-contact-0-value').props.onChange({target:{value:'not-a-phone'}});
 tree=h.tree('BusinessPartnerEditor',p);await form(tree).props.onSubmit({preventDefault(){}});
 tree=h.tree('BusinessPartnerEditor',p);
 assert.equal(h.calls.length,0);
 assert.equal(byId(tree,'bp-contact-0-value').props['aria-invalid'],true);
 assert.match(h.render('BusinessPartnerEditor',p),/Contact 1 — Phone.*invalid_contact_phone/);
});

test('unknown server field paths are not rendered or associated with arbitrary DOM elements',async()=>{
 const p={session,scope:(s:string)=>s,onError:()=> 'Safe translated error',id:null,onClose(){},onSaved(){}};
 const h=partnerHarness('business-partner-workspace','en',()=>{throw Object.assign(new ApiError('invalid_field_value',400),{field:'secret.internal<path>'});});
 let tree=h.tree('BusinessPartnerEditor',p);await form(tree).props.onSubmit({preventDefault(){}});
 assert.match(h.render('BusinessPartnerEditor',p),/Safe translated error/);
 assert.doesNotMatch(h.render('BusinessPartnerEditor',p),/secret\.internal/);
});
