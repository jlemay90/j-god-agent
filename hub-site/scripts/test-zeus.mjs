import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('../dist/server/index.js', import.meta.url));
const { default: worker } = await import('data:text/javascript;base64,' + source.toString('base64'));
const objects = new Map();
const bucket = { async get(key) { return objects.has(key) ? { json: async () => JSON.parse(objects.get(key)) } : null; }, async put(key, value) { objects.set(key,value); }, async list({prefix}) { return {objects:[...objects.keys()].filter(key=>key.startsWith(prefix)).map(key=>({key})), truncated:false}; } };
const env={BUCKET:bucket,ZEUS_BRIDGE_URL:'https://test.replit.dev/hub/chat',ZEUS_BRIDGE_SECRET:'test-only-signing-key-not-a-real-secret-123'};
const origin='https://hub.example';
const headers={'oai-authenticated-user-id':'owner-1',origin,'content-type':'application/json'};
const call=(path,body,h=headers)=>worker.fetch(new Request(origin+path, body?{method:'POST',headers:h,body:JSON.stringify(body)}:{headers:h}),env);
assert.equal((await call('/api/zeus/status',null,{})).status,401);
assert.equal((await call('/api/zeus/chat',{panel:'inbox',requestId:crypto.randomUUID(),message:'test'},{...headers,origin:'https://wrong.example'})).status,403);
assert.equal((await call('/api/zeus/chat',{panel:'invalid',requestId:crypto.randomUUID(),message:'test'})).status,400);
const originalFetch=globalThis.fetch;let captured=[],calls=0;
globalThis.fetch=async (url,options)=>{calls++;assert.equal(options.redirect,'manual');const body=JSON.parse(options.body);captured.push(body);assert.equal(options.headers['x-zeus-signature'].length,64);return new Response(JSON.stringify({ok:true,requestId:body.requestId,reply:'Here is a proposed task.',proposal:{kind:body.panel==='inbox'?'add_item':'none',value:'Read one page',tinyStart:'',evidence:body.message},model:'test-model',ruleRevision:6}),{status:200});};
try {
  const input={panel:'inbox',requestId:crypto.randomUUID(),message:'Add a task to read one page'};
  const a=await (await call('/api/zeus/chat',input)).json();assert.equal(a.ok,true);assert.equal(calls,1);
  const stateBefore=await (await call('/api/state')).json();assert.equal(stateBefore.state.items.length,0,'proposal must not write an item');
  await call('/api/zeus/chat',input);assert.equal(calls,1,'retry must replay cached result');
  const x=await (await call('/api/zeus/apply',{panel:'inbox',requestId:input.requestId})).json();assert.equal(x.ok,true);
  const y=await (await call('/api/zeus/apply',{panel:'inbox',requestId:input.requestId})).json();assert.equal(x.receipt.id,y.receipt.id);
  const stateAfter=await (await call('/api/state')).json();assert.equal(stateAfter.state.items.length,1);
  await call('/api/zeus/chat',{panel:'build',requestId:crypto.randomUUID(),message:'Explain our build goal'});
  assert.equal(captured[1].history.length,0,'Inbox messages must not enter build history');
  assert.equal(captured[1].context.section,'build');assert.ok(!('items' in captured[1].context));assert.ok(!('brief' in captured[1].context));
  const other=await (await call('/api/zeus/history?panel=inbox',null,{...headers,'oai-authenticated-user-id':'owner-2'})).json();assert.equal(other.turns.length,0);
  assert.equal((await call('/api/zeus/apply',{panel:'today',requestId:input.requestId})).status,409);
  const secretReply=JSON.stringify(a);assert.ok(!secretReply.includes(env.ZEUS_BRIDGE_SECRET));
  const rpc=async(name,args={},h=headers)=> (await call('/mcp',{jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}},h)).json();
  const missingOwner=await rpc('ask_zeus',{message:'test',requestId:crypto.randomUUID()},{});
  assert.equal(missingOwner.result.isError,true,'messaging requires authenticated owner identity');
  const exchange={message:'Synthetic connector round trip',requestId:crypto.randomUUID(),panel:'today'};
  const beforeCalls=calls;
  const first=await rpc('ask_zeus',exchange);
  const result=JSON.parse(first.result.content[0].text);
  assert.equal(result.requestId,exchange.requestId);assert.equal(result.changesApplied,false);
  assert.equal(calls,beforeCalls+1);
  const retry=await rpc('ask_zeus',exchange);
  assert.equal(JSON.parse(retry.result.content[0].text).reply,result.reply);
  assert.equal(calls,beforeCalls+1,'MCP retries must not spend another model call');
  const readback=JSON.parse((await rpc('get_hub_state')).result.content[0].text);
  assert.equal(readback.zeusConversations.find(t=>t.requestId===exchange.requestId).reply,result.reply);
  const otherReadback=JSON.parse((await rpc('get_hub_state',{}, {...headers,'oai-authenticated-user-id':'owner-2'})).result.content[0].text);
  assert.equal(otherReadback.zeusConversations.length,0,'connector conversation readback is owner scoped');
  const conflict=await rpc('ask_zeus',{...exchange,message:'Different text'});
  assert.equal(conflict.result.isError,true);assert.equal(calls,beforeCalls+1);
  // Regression: large canonical Hub memory and panel history must not be pasted into a short message.
  // This data intentionally exceeds the old worker's 28KB bridge envelope limit.
  const oversizedMemory = {
    summary: 'Historical project detail '.repeat(190),
    decisions: Array.from({length:30},(_,i)=>'Decision '+i+': '+'Keep relevant provenance and approved protections. '.repeat(14)),
    backlog: Array.from({length:29},(_,i)=>'Backlog '+i+': '+'Restore previous context carefully. '.repeat(18)),
    nextSteps: Array.from({length:30},(_,i)=>'Step '+i+': '+'Avoid sending old prompts wholesale. '.repeat(19)),
    revision:50,updatedAt:'2026-11-17T00:00:00.000Z'
  };
  const originalStored=JSON.stringify(oversizedMemory);
  assert.ok(Buffer.byteLength(originalStored)>28000);
  objects.set('hub/v1/project-memory.json',originalStored);
  const ownerKey=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode('owner-1'))).toString('hex');
  const staleHistory=Array.from({length:20},(_,i)=>({
    requestId:crypto.randomUUID(),message:'Old instruction '+i+' '+'Do not repeat this. '.repeat(150),
    reply:'Previous Zeus answer '+i+' '+'Old dialogue. '.repeat(220),
    createdAt:new Date(Date.now()-i*1000).toISOString()
  }));
  objects.set('hub/v1/zeus/threads/'+ownerKey+'/build.json',JSON.stringify(staleHistory));
  const beforeLarge=captured.length;
  const small={panel:'build',requestId:crypto.randomUUID(),message:'hello'};
  const healthy=await (await call('/api/zeus/chat',small)).json();
  assert.equal(healthy.ok,true,'a short message should not fail due to stored context size');
  assert.equal(captured.length,beforeLarge+1);
  const sent=captured.at(-1);
  assert.equal(sent.message,'hello','user message should never contain hidden instructions');
  assert.equal(sent.context.project.revision,50);
  assert.equal(sent.context.project.contextIsExcerpt,true);
  assert.ok(Buffer.byteLength(JSON.stringify(sent))<=12000,'payload should stay below safe budget');
  assert.ok(sent.history.length<=8,'history must be bounded');
  assert.equal(objects.get('hub/v1/project-memory.json'),originalStored,'canonical memory must remain intact');
  // Existing authorization rules are unaffected.
  assert.ok(!('items' in sent.context),'Build may not receive Inbox item collection');
  env.ZEUS_BRIDGE_SECRET='';assert.equal((await call('/api/zeus/chat',{panel:'today',requestId:crypto.randomUUID(),message:'Help'})).status,503);
} finally {globalThis.fetch=originalFetch;}
console.log('Zeus API: authentication, section isolation, proposal/apply, retries, owner isolation and offline state passed');
