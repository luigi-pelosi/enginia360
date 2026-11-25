import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogHarness,catalogSession,findCatalog} from './catalog-harness.ts';
import {catalogRoutes,catalogResources,navigationPath} from '../lib/model.ts';
test('child-only reader can traverse exact catalog settings parents without BP grants',()=>{
 const h=catalogHarness();const w=h.workspace({});const s={...catalogSession,permissions:['catalog-numbering.read']};
 for(const key of navigationPath('catalog-numbering'))assert.equal(w.canOpenResource(s,key),true,key);
 for(const key of ['catalog','catalog-units','catalog-types','catalog-categories','settings-business-partners','business-partner-numbering'])assert.equal(w.canOpenResource(s,key),false,key);
});
for(const locale of ['it','en'])test(`workspace renders complete localized catalog breadcrumbs and its owned component (${locale})`,()=>{
 const h=catalogHarness('catalog-types',()=>null,new Map(),locale);const resources=[{key:'settings',fields:[]},...catalogRoutes.map(key=>({key,fields:[]}))];const w=h.workspace({0:catalogSession,1:false,5:resources,6:'catalog-units',7:'t'});const tree=w.default();
 const catalog=findCatalog(tree,n=>n.props?.resource==='catalog-units');assert.ok(catalog,'dedicated workspace is mounted');assert.equal(catalog.props.tenantId,'t');
 const heading=catalog.props.heading;const allText=(n:any):string=>typeof n==='string'?n:n?.props?[n.props.children].flat(Infinity).map(allText).join(' '):'';
 const text=allText(heading);for(const label of locale==='it'?['Impostazioni','Sistema','Unità di misura']:['Settings','System','Units of measure'])assert.ok(text.includes(label),label);
 assert.equal(findCatalog(tree,n=>n.props?.className==='page-heading'),undefined,'only the child owns the heading/create row');
});
test('all catalog destinations are represented as virtual frontend routes rather than generic data CRUD',()=>{
 const h=catalogHarness();const resources=[{key:'settings',fields:[]},...catalogRoutes.map(key=>({key,fields:[]}))];const w=h.workspace({0:catalogSession,1:false,5:resources,6:'catalog',7:'t'});const tree=w.default();
 const text=(n:any):string=>typeof n==='string'?n:n?.props?[n.props.children].flat(Infinity).map(text).join(' '):'';
 assert.ok(text(tree).includes('Categorie'));assert.ok(!text(tree).includes('Tipologie articolo'));assert.equal(findCatalog(tree,n=>n.props?.resource==='catalog'),undefined);
 assert.equal(catalogResources.length,7);
});
