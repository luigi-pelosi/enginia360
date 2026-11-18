import test from 'node:test';
import assert from 'node:assert/strict';
import {api, ApiError} from '../lib/api.ts';

test('writes obtain fresh CSRF tokens and send same-origin cookies', async()=>{
 const original=globalThis.fetch;
 const calls:{path:string;options?:RequestInit}[]=[];
 let generation=0;
 globalThis.fetch=async(input,options)=>{
  const path=String(input);calls.push({path,options});
  if(path==='/api/auth/csrf')return Response.json({token:`token-${++generation}`});
  return new Response(null,{status:204});
 };
 try{
  await api('/data/companies','POST',{code:'TEST'});
  await api('/data/companies/test','DELETE');
  assert.deepEqual(calls.map(x=>x.path),['/api/auth/csrf','/api/data/companies','/api/auth/csrf','/api/data/companies/test']);
  assert.equal((calls[1].options?.headers as Record<string,string>)['X-CSRF-TOKEN'],'token-1');
  assert.equal((calls[3].options?.headers as Record<string,string>)['X-CSRF-TOKEN'],'token-2');
  assert.equal(calls[1].options?.credentials,'same-origin');
  assert.equal(calls[1].options?.body,'{"code":"TEST"}');
 }finally{globalThis.fetch=original}
});
test('contract errors preserve stable error codes and status',async()=>{
 const original=globalThis.fetch;
 globalThis.fetch=async()=>Response.json({code:'forbidden'},{status:403});
 try{await assert.rejects(api('/data/users'),(error:unknown)=>error instanceof ApiError&&error.code==='forbidden'&&error.status===403)}finally{globalThis.fetch=original}
});
