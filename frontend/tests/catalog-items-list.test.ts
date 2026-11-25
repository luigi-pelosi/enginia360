import test from 'node:test';
import assert from 'node:assert/strict';
import {itemHarness,itemOptions,itemSession,root,findCatalog} from './catalog-items-harness.ts';

function collect(node:any,name:string):any[]{const result:any[]=[];function visit(n:any){if(!n||typeof n!=='object')return;if(n.type?.name===name)result.push(n);for(const child of [n.props?.children].flat(Infinity))visit(child);}visit(node);return result;}

test('item list orders columns and resolves inactive brands for read-only users',async()=>{
 const session={...itemSession,permissions:['catalog-items.read']};
 const records=[root({id:'a',item_type_id:'old',category_id:'child',base_uom_id:'old-unit',brand_id:'old-brand',status:'ACTIVE'}),root({id:'b',item_type_id:null,category_id:null,base_uom_id:null,brand_id:null,status:'SUSPENDED'}),root({id:'c',item_type_id:'missing',category_id:'missing',base_uom_id:'missing',brand_id:'missing-brand',status:'SUSPENDED'}),root({id:'d',brand_id:'brand',status:'ARCHIVED'})];
 const options={...itemOptions,units:[...itemOptions.units,{id:'old-unit',name:'Unità storica',code:'OLD',dimension:'MASS',conversion_scope:'UNIVERSAL',factor_to_base:'1',decimal_places:0,is_base:false,is_active:false}],categories:[...itemOptions.categories,{id:'child',name:'Storica',parent_id:'category',is_active:false}],brands:[...itemOptions.brands,{id:'old-brand',name:'Marchio storico',is_active:false}]};
 const h=itemHarness((path)=>path.startsWith('/catalog/items?')?{items:records,total:4,page:1,pageSize:25}:undefined,{session,options});await h.settle();
 const table=h.byId('catalog-item-table');
 assert.deepEqual(collect(table,'TableHead').map(n=>n.props.children),['Codice','Nome','Tipologia','Categoria','Unità di misura base','Marchio','Stato','Azioni']);
 for(const [index,expected] of ['Marchio storico','—','—','Brand'].entries()){
  const row=findCatalog(table,n=>n.props?.['data-record-id']===records[index].id);const cells=collect(row,'TableCell');
  assert.equal(cells[0].props.children,'A-1');assert.equal(cells[1].props.children,'Item A');assert.equal(cells[2].props.children,['Old type','—','—','Goods type'][index]);assert.equal(cells[3].props.children,['Category / Storica','—','—','Category'][index]);assert.match(String(cells[4].props.children),new RegExp(['Unità storica','—','—','Gram'][index]));assert.equal(cells[5].props.children,expected);
  const badge=findCatalog(cells[6],n=>n.type?.name==='Badge');assert.ok(badge);assert.equal(badge.props.children,['Attivo','Sospeso','Sospeso','Archiviato'][index]);
 }
 assert.equal(h.calls.filter(c=>c.path.startsWith('/catalog/item-options')).length,1);
 assert.equal(h.calls.filter(c=>c.path.startsWith('/catalog/items/')).length,0);
 assert.equal(h.action('Modifica Item A'),undefined);
});
