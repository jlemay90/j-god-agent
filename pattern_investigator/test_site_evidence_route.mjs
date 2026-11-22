import test from "node:test";
import assert from "node:assert/strict";
import {readPatternEvidence,EVIDENCE_PATH} from "./site_evidence_route.mjs";

const origin="https://j-command-hub.jlemay90.chatgpt.site";
const secret="q".repeat(48);
const example={
  id:"abc-123", text:"Sensitive family note: DO NOT EXPOSE",
  patternEvidence:[{
    authorized:true,sensitive:false,theme:"repeating_task",
    event_id:"event-1",goal:"growth",polarity:"supports",
    basis:"owner_report",occurred_at:"2026-11-22T10:00:00Z",
    summary:"Also never expose this raw text"
  }]
};
function harness({enabled=true,items=[example],allow="abc-123",failure=false}={}) {
 let reads=0;
 const env={HUB_PATTERN_READ_ENABLED:enabled?"true":"false",
            HUB_PATTERN_ALLOWED_ITEM_IDS:allow,HUB_PATTERN_LINK_SECRET:secret,
            HUB_SITE_REVISION:"private-source-test"};
 const dependencies={storage:{},clock:()=>new Date("2026-11-22T20:00:00Z"),
  readItems:async()=>{reads++;if(failure)throw Error("read failed");return items;}};
 const request=({auth=secret,method="GET",suffix=""}={})=>
    new Request(origin+EVIDENCE_PATH+suffix,{method,
      headers:auth===null?{}:{authorization:"Bearer "+auth}});
 return {env,dependencies,request,get reads(){return reads;}};
}
test("scope-checked live read returns ONLY approved, curated observations",async()=>{
 const h=harness({items:[example,{id:"other",patternEvidence:[example.patternEvidence[0]],text:"other private note"}]});
 const res=await readPatternEvidence(h.request(),h.env,h.dependencies);
 assert.equal(res.status,200);
 const result=await res.json();
 assert.equal(result.observations.length,1);
 assert.equal(result.observations[0].source_kind,"owner_reported");
 assert.equal(result.observations[0].summary,"Curated owner-approved Hub evidence");
 assert.equal(result.source,"owner_authenticated_curated_hub_pattern_evidence");
 assert.equal(result.scope,"pattern_read_only_v1");
 assert.equal(h.reads,1);
 assert.equal(JSON.stringify(result).includes("Sensitive family note"),false);
 assert.equal(JSON.stringify(result).includes("never expose this raw"),false);
});
test("missing/wrong auth rejects without reading data",async()=>{
 for(const auth of [null,"wrong"]) {
  const h=harness();
  const res=await readPatternEvidence(h.request({auth}),h.env,h.dependencies);
  assert.equal(res.status,403);
  assert.equal(h.reads,0);
 }
});
test("disabled, unconfigured allowlist reject before opening storage",async()=>{
 for(const options of [{enabled:false},{allow:""},{allow:"@@bad"}]) {
  const h=harness(options);
  const res=await readPatternEvidence(h.request(),h.env,h.dependencies);
  assert.equal(res.status,503);
  assert.equal(h.reads,0);
 }
});
test("method and query blocked before storage",async()=>{
 for(const config of [{method:"POST"},{suffix:"?all=1"}]) {
  const h=harness();
  const res=await readPatternEvidence(h.request(config),h.env,h.dependencies);
  assert.ok([400,405].includes(res.status));
  assert.equal(h.reads,0);
 }
});
test("sensitive and non-consented evidence not returned",async()=>{
 const bad={...example,patternEvidence:[
   {...example.patternEvidence[0],sensitive:true},
   {...example.patternEvidence[0],authorized:false},
   {...example.patternEvidence[0],theme:"bad spaces"}]};
 const h=harness({items:[bad]});
 const res=await readPatternEvidence(h.request(),h.env,h.dependencies);
 assert.equal(res.status,200);
 assert.equal((await res.json()).observations.length,0);
});
test("storage unavailable never invents a successful read",async()=>{
 const h=harness({failure:true});
 const res=await readPatternEvidence(h.request(),h.env,h.dependencies);
 assert.equal(res.status,503);
 assert.equal((await res.json()).ok,false);
});
