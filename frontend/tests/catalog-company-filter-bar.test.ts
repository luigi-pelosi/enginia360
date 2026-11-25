import test from 'node:test';
import assert from 'node:assert/strict';
import {harness} from './catalog-company-filter-harness.ts';
function bar(h:ReturnType<typeof harness>){return h.find(n=>n.props?.id==='company-catalog-filters');}
test('company filters use compact search-first shared bar and restore expansion without requesting data',async()=>{
 const storage=new Map<string,string>(),h=harness({storage});await h.settle();
 assert.ok(bar(h),'company filters must use the shared measured FilterBar instead of a six-field grid');
 const b=bar(h);assert.deepEqual(Array.from(b.props.fields,(f:any)=>f.key),['search','company','enabled','canSell','canPurchase','canTrackStock']);
 assert.deepEqual(Array.from(b.props.fields,(f:any)=>f.minWidth),[200,180,130,128,128,128]);
 const before=h.calls.length;b.props.onExpandedChange(true);await h.settle();assert.equal(h.calls.length,before);assert.equal(bar(h).props.expanded,true);
 const capability=bar(h).props.fields.find((f:any)=>f.key==='canPurchase').content;
 function find(n:any):any{if(!n||typeof n!=='object')return null;if(n.props?.onValueChange)return n;for(const x of [n.props?.children].flat(Infinity)){const hit=find(x);if(hit)return hit;}return null;}
 find(capability).props.onValueChange('NO');await h.settle();assert.ok(h.calls.at(-1).path.includes('canPurchase=NO'));h.unmount();
 const recovered=harness({storage});await recovered.settle();assert.equal(bar(recovered).props.expanded,true);assert.ok(recovered.calls.some(c=>c.path.includes('canPurchase=NO')));recovered.unmount();
});
