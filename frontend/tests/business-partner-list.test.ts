import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const props={session:{...session,permissions:['business-partners.read','business-partners.create','business-partners.update']},scope:(p:string)=>p+(p.includes('?')?'&':'?')+'tenantId=t',onError:()=> 'Error'};
test('main BP list fetches tenant-scoped data, navigates to dedicated create/details and back without writes',async()=>{
 const row={id:'bp1',code:'BP-000001',kind:'ORGANIZATION',status:'ACTIVE',legal_name:'Officina Uno'};
 const h=partnerHarness('business-partner-workspace','it',()=>({items:[row],total:1,page:1,pageSize:25}));
 h.tree('BusinessPartnerWorkspace',props);await h.flush();
 assert.equal(h.calls[0].path,'/data/business-partners?page=1&pageSize=25&search=&tenantId=t');
 let tree=h.tree('BusinessPartnerWorkspace',props);
 find(tree,n=>n.props?.['aria-label']==='Modifica Officina Uno').props.onClick();
 tree=h.tree('BusinessPartnerWorkspace',props);assert.equal(tree.type,h.components.BusinessPartnerEditor);assert.equal(tree.props.id,'bp1');tree.props.onClose();
 tree=h.tree('BusinessPartnerWorkspace',props);
 find(tree,n=>Array.isArray(n.props?.children)&&n.props.children.includes('Nuovo Business Partner')).props.onClick();
 tree=h.tree('BusinessPartnerWorkspace',props);assert.equal(tree.props.id,null);tree.props.onClose();
 assert.ok(h.calls.every(c=>c.method==='GET'));assert.match(h.render('BusinessPartnerWorkspace',props),/Officina Uno/);
});
test('search and pagination use the aggregate API search rather than filtering current page only',async()=>{
 const h=partnerHarness('business-partner-workspace','en',()=>({items:[{id:'bp1',kind:'PERSON',first_name:'Ada',last_name:'Rossi',code:'BP-1',status:'DRAFT'}],total:60,page:1,pageSize:25}));
 h.tree('BusinessPartnerWorkspace',props);await h.flush();let tree=h.tree('BusinessPartnerWorkspace',props);
 find(tree,n=>n.props?.children==='Next').props.onClick();h.tree('BusinessPartnerWorkspace',props);await h.flush();assert.match(h.calls.at(-1)!.path,/page=2&/);
 tree=h.tree('BusinessPartnerWorkspace',props);find(tree,n=>n.props?.['aria-label']==='Search code, name, tax ID or contact').props.onChange({target:{value:'a+b@example.com'}});
 h.tree('BusinessPartnerWorkspace',props);await h.flush();await new Promise(resolve=>setTimeout(resolve,330));h.tree('BusinessPartnerWorkspace',props);await h.flush();
 assert.match(h.calls.at(-1)!.path,/page=1&.*search=a%2Bb%40example.com&tenantId=t/);
});
test('read-only list has details and no create action even when numbering grants exist',async()=>{
 const readonly={...props,session:{...session,permissions:['business-partners.read','business-partner-numbering.update']}};
 const h=partnerHarness('business-partner-workspace','en',()=>({items:[{id:'bp',code:'1',kind:'PERSON',status:'BLOCKED',first_name:'Ada',last_name:'Rossi'}],total:1,page:1,pageSize:25}));
 h.tree('BusinessPartnerWorkspace',readonly);await h.flush();const html=h.render('BusinessPartnerWorkspace',readonly);
 assert.match(html,/Details Ada Rossi/);assert.doesNotMatch(html,/New Business Partner|Delete/);
});
test('numbering grants never authorize partner data or operational numbering navigation',async()=>{
 const limited={...props,session:{...session,permissions:['business-partner-numbering.read']}};
 const h=partnerHarness('business-partner-workspace','it');
 h.tree('BusinessPartnerWorkspace',limited);await h.flush();
 assert.deepEqual(h.calls,[]);
 assert.doesNotMatch(h.render('BusinessPartnerWorkspace',limited),/Nuovo Business Partner|Cerca codice|>Numerazione</);
});
test('partner readers without numbering.read have no numbering action',()=>{
 const h=partnerHarness('business-partner-workspace','en');
 assert.doesNotMatch(h.render('BusinessPartnerWorkspace',props),/>Numbering</);
});
