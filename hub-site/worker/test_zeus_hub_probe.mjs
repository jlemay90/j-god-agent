import test from "node:test";
import assert from "node:assert/strict";
import {readOnlyHubProbe} from "./zeus_hub_probe.mjs";

const origin = "https://j-command-hub.jlemay90.chatgpt.site";
const marker = "ZEUS-HUB-LINK-20261122-K7M4";
const secret = "k".repeat(48);

function harness({enabled=true, items=[], pulse={date:"2026-11-22"}, readError=false}={}) {
  let reads = 0;
  let writes = 0;
  const deps = {
    storage: { label: "injected-test-storage" },
    pulseKey: "hub/v1/pulse.json",
    clock: () => new Date("2026-11-22T19:00:00Z"),
    readObject: async () => {reads++; if(readError) throw Error("storage down"); return pulse;},
    readItems: async () => {reads++; if(readError) throw Error("storage down"); return items;},
    writeObject: async () => { writes++; throw Error("write forbidden"); },
  };
  const env = {HUB_ZEUS_LINK_READ_ENABLED: enabled?"true":"false",HUB_ZEUS_LINK_SECRET:secret};
  const request = ({auth=secret,method="GET",path="/api/zeus-link/probe",query="?marker="+marker}={}) =>
    new Request(origin+path+query,{method,headers:auth?{authorization:"Bearer "+auth}:{}});
  return {env,deps,request,get reads(){return reads},get writes(){return writes}};
}

test("authenticated probe reads current injected storage but returns no personal item text", async () => {
  const h=harness({items:[{text:"private unrelated note"},{text:marker+" — test"}]});
  const response=await readOnlyHubProbe(h.request(),h.env,h.deps);
  assert.equal(response.status,200);
  assert.equal(response.headers.get("cache-control"),"private, no-store");
  const body=await response.json();
  assert.equal(body.source,"authenticated_live_hub_storage");
  assert.equal(body.scope,"read_only_probe_v1");
  assert.equal(body.checkedAt,"2026-11-22T19:00:00.000Z");
  assert.equal(body.pulseDate,"2026-11-22");
  assert.equal(body.itemCount,2);
  assert.equal(body.markerFound,true);
  assert.equal(JSON.stringify(body).includes("private unrelated note"),false);
  assert.equal(h.reads,2);
  assert.equal(h.writes,0);
});

test("missing or incorrect route secret rejects WITHOUT opening storage",async()=>{
  for(const auth of [null,"not-allowed",""]) {
    const h=harness();
    assert.equal((await readOnlyHubProbe(h.request({auth}),h.env,h.deps)).status,403);
    assert.equal(h.reads,0);
  }
});

test("feature disabled or missing route credential fail closed",async()=>{
  for(const enabled of [true,false]){
    const h=harness({enabled});
    if(enabled)h.env.HUB_ZEUS_LINK_SECRET="";
    const response=await readOnlyHubProbe(h.request(),h.env,h.deps);
    assert.equal(response.status,503);
    assert.equal(h.reads,0);
  }
});

test("unsupported method, route or marker rejected without storage read",async()=>{
  const h=harness();
  assert.equal((await readOnlyHubProbe(h.request({method:"POST"}),h.env,h.deps)).status,405);
  assert.equal((await readOnlyHubProbe(h.request({path:"/mcp"}),h.env,h.deps)).status,404);
  assert.equal((await readOnlyHubProbe(h.request({query:"?marker=evil"}),h.env,h.deps)).status,400);
  assert.equal((await readOnlyHubProbe(h.request({query:"?marker="+marker+"&other=1"}),h.env,h.deps)).status,400);
  assert.equal(h.reads,0);
});

test("storage outage is blocked, never a successful proof",async()=>{
  const h=harness({readError:true});
  const response=await readOnlyHubProbe(h.request(),h.env,h.deps);
  const body=await response.json();
  assert.equal(response.status,503);
  assert.equal(body.ok,false);
  assert.equal(body.status,"BLOCKED");
  assert.equal(h.writes,0);
});

test("only explicit, injected storage source is accepted",async()=>{
  const h=harness();
  delete h.deps.readItems;
  const response=await readOnlyHubProbe(h.request(),h.env,h.deps);
  assert.equal(response.status,503);
  assert.equal(h.reads,0);
});
