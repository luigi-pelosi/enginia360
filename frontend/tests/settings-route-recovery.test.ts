import test from 'node:test';
import assert from 'node:assert/strict';
import {harness, session, find} from './workspace-harness.ts';
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('neutral route removes an unauthorized URL instead of persisting Settings recovery',()=>{
 const replaced:string[]=[];const storage=new Map<string,string>();
 const browser={location:{pathname:'/',search:'?view=settings'},history:{replaceState(_state:unknown,_title:string,url:string){replaced.push(url);}}};
 const h=harness('en',{0:session,1:false,5:[],6:'settings',7:'t',25:true},{items:[],total:0},storage,browser);
 h.components.default();h.effects[6]();
 assert.deepEqual(replaced,['/']);assert.equal(storage.size,0);
});
for(const requested of ['settings','settings-system','settings-master-data','settings-business-partners','settings-catalog','catalog','payments']) test(`company reader rejects ${requested} in URL/history and stale recovery`,async()=>{
 const operator={...session,permissions:['companies.read','countries.create']};
 const resources=[{key:'users',fields:[]},{key:'companies',fields:[]}];
 const storage=new Map([[`workspace:u:t:${requested}`,JSON.stringify({search:'denied',page:4})],[`workspace:u:t:record:${requested}`,JSON.stringify({kind:'create',values:{key:'obsolete'}})]]);
 const listeners=new Map<string,()=>void>();
 const browser={location:{pathname:'/',search:`?view=${requested}`},history:{pushState(){},replaceState(){}},addEventListener:(name:string,handler:()=>void)=>listeners.set(name,handler),removeEventListener:(name:string)=>listeners.delete(name)};
 const response=(path:string)=>path==='/resources'?resources:{items:[],total:0};
 const h=harness('en',{0:operator,1:false,5:resources,6:requested,7:'t',25:true},response,storage,browser);
 h.components.default();h.effects[3]();h.effects[8]();await tick();
 assert.equal((h.updates[6] as (current:string)=>string)(requested),'companies');
 assert.equal(h.updates[12],undefined);assert.equal(h.updates[16],undefined);
 h.effects[7]();listeners.get('popstate')!();assert.equal(h.updates[6],'companies');
 assert.equal(h.apiCalls.some(path=>path.startsWith('/data/')),false);
});
for(const isSuperAdmin of [false,true]) test(`Settings URL, back/forward and stale-editor recovery without metadata (root=${isSuperAdmin})`,async()=>{
 const operator={...session,isSuperAdmin,tenantId:isSuperAdmin?null:'t',permissions:[]};
 const tenant=isSuperAdmin?'':'t';
 const storage=new Map([[`workspace:u:${tenant}:settings`,JSON.stringify({search:'retained',page:2})],[`workspace:u:${tenant}:record:settings`,JSON.stringify({kind:'create',values:{key:'obsolete'}})]]);
 const listeners=new Map<string,()=>void>();
 const browser={location:{pathname:'/',search:'?view=settings'},history:{pushState(){},replaceState(){}},addEventListener:(name:string,handler:()=>void)=>listeners.set(name,handler),removeEventListener:(name:string)=>listeners.delete(name)};
 const response=(path:string)=>path==='/resources'?[]:path==='/session'?operator:{items:[],total:0};
 const h=harness('en',{0:operator,1:false,5:[],6:'',7:tenant,25:true},response,storage,browser);
 h.components.default();
 h.effects[3]();await tick();
 assert.equal((h.updates[6] as (current:string)=>string)(''),isSuperAdmin?'settings':'','direct URL only restores authorized route');
 assert.equal(h.updates[12],isSuperAdmin?'retained':undefined);assert.equal(h.updates[11],isSuperAdmin?2:undefined);
 h.effects[7]();assert.ok(listeners.has('popstate'));listeners.get('popstate')!();
 assert.equal(h.updates[6],isSuperAdmin?'settings':'','history accepts only authorized routes');
 const recovered=harness('en',{0:operator,1:false,5:[],6:'settings',7:tenant,25:true},response,storage,browser);
 recovered.components.default();recovered.effects[5]();recovered.effects[8]();await tick();
 assert.equal(recovered.updates[16],undefined,'stale settings editor never reopens');
 assert.equal(recovered.apiCalls.some(path=>path.includes('/data/settings')),false);
});
test('fresh session leaves Settings after obsolete permissions disappear',async()=>{
 const current={...session,permissions:['settings.read','settings.update']};
 const h=harness('en',{0:current,1:false,5:[],6:'settings',7:'t',16:{resource:{key:'users',fields:[]},row:{id:'u',tenant_id:'t'}}},session);
 const tree=h.components.default();
 const editor=find(tree,n=>n.type?.name==='RecordEditor');assert.ok(editor);
 await editor.props.onSaved({id:'u'},'users');
 assert.equal(h.apiCalls[0],'/session');assert.equal(h.updates[6],'','revocation falls back to neutral no-access route');
});
for(const remaining of [[],['companies.read'],['catalog-numbering.read']]) test(`session revocation selects only the first still-authorized route (${remaining.join(',')||'none'})`,async()=>{
 const operator={...session,permissions:['countries.read']};const fresh={...session,permissions:remaining};
 const resources=['users','companies','countries','catalog-numbering'].map(key=>({key,fields:[]}));
 const h=harness('en',{0:operator,1:false,5:resources,6:'settings',7:'t',16:{resource:{key:'users',fields:[]},row:{id:'u',tenant_id:'t'}}},fresh);
 const tree=h.components.default();const editor=find(tree,n=>n.type?.name==='RecordEditor');assert.ok(editor);
 await editor.props.onSaved({id:'u'},'users');
 assert.equal(h.updates[6],remaining[0]==='catalog-numbering.read'?undefined:remaining.length?'companies':'','keep Settings only if a descendant remains readable');
 assert.equal(h.apiCalls.some(path=>path.startsWith('/data/settings')),false);
});
for(const locale of ['it','en']) test(`all existing settings tiles and independent numbering paths survive without settings metadata (${locale})`,()=>{
 const grants=['business-partner-numbering.read','catalog-numbering.read','catalog-units.read','countries.read','cities.read','currencies.read'];
 const operator={...session,permissions:grants};
 const resources=['countries','cities','currencies','catalog-units','catalog-numbering'].map(key=>({key,fields:[]}));
 const text=(node:any):string=>typeof node==='string'?node:node?.props?[node.props.children].flat(Infinity).map(text).join(' '):'';
 for(const [active,labels] of [
  ['settings',locale==='it'?['Anagrafiche','Sistema']:['Master data','System']],
  ['settings-system',locale==='it'?['Nazioni','Città','Valute','Unità di misura']:['Countries','Cities','Currencies','Units of measure']],
  ['settings-master-data',['Business Partner',locale==='it'?'Catalogo':'Catalog']],
  ['settings-business-partners',[locale==='it'?'Numerazione':'Numbering']],
  ['settings-catalog',[locale==='it'?'Numerazione':'Numbering']],
 ] as [string,string[]][]) {
  const h=harness(locale,{0:operator,1:false,5:resources,6:active,7:'t'});
  const tree=h.components.default();const content=text(tree);
  for(const label of labels) assert.ok(content.includes(label),`${active}: missing ${label}`);
 }
});
