import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogHarness,catalogSession,findCatalog} from './catalog-harness.ts';

for (const resource of ['catalog-brands','catalog-categories','catalog-types','catalog-units']) test(`${resource} switches use the shared full-width field`,async()=>{
 const session={...catalogSession,permissions:[...catalogSession.permissions,...['read','create','update'].map(a=>`${resource}.${a}`)]};
 const h=catalogHarness(resource,p=>p==='/session'?session:{items:[],total:0},undefined,'it',session);
 await h.settle(); await h.byId('catalog-new').props.onClick(); await h.settle();
 const ids=resource==='catalog-types'?['is_active','default_sellable','default_purchasable','default_track_stock']:resource==='catalog-units'?['is_active','is_base']:['is_active'];
 for(const id of ids){const field=findCatalog(h.tree,n=>n.props?.className==='field switch-field' && findCatalog(n,c=>c.props?.id===`catalog-${id}`)); assert.ok(field,`${id} must use shared full-width bordered field`);}
 h.unmount();
});
