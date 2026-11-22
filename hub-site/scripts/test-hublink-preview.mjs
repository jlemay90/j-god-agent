import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const built = await readFile(new URL("../dist/server/index.js", import.meta.url));
const {default: worker} = await import("data:text/javascript;base64," + built.toString("base64"));

const origin = "https://hub-preview.example";
const path = "/api/zeus-link/probe";
const marker = "ZEUS-HUB-LINK-20261122-K7M4";
const secret = "preview-only-dummy-route-key-1234567890-000";
const PREFIX = "hub/v1/";
const ITEM_PREFIX = PREFIX + "items/";
const itemOne = ITEM_PREFIX + "a.json";
const itemTwo = ITEM_PREFIX + "b.json";

function harness({enabled=true, outage=false, withMarker=true} = {}) {
  const objects = new Map([
    [PREFIX + "pulse.json", {date:"2026-11-22", headline:"Synthetic pulse"}],
    [itemOne, {id:"mock-a", text:"Synthetic unrelated note", createdAt:"2026-11-22T11:00:00Z"}],
    [itemTwo, {id:"mock-b", text:withMarker ? marker + " — synthetic" : "No marker here",
               createdAt:"2026-11-22T12:00:00Z"}],
  ]);
  let reads = 0, writes = 0;
  const bucket = {
    async get(key) {
      reads++;
      if (outage) throw new Error("Simulated storage outage");
      const val = objects.get(key);
      return val ? {json:async()=>structuredClone(val)} : null;
    },
    async list({prefix}) {
      reads++;
      if (outage) throw new Error("Simulated storage outage");
      return {objects:[...objects.keys()].filter(k=>k.startsWith(prefix)).map(key=>({key})),truncated:false};
    },
    async put() {writes++;throw new Error("Unacceptable preview write");},
    async delete() {writes++;throw new Error("Unacceptable preview delete");},
  };
  const env = {BUCKET:bucket,
    HUB_ZEUS_LINK_READ_ENABLED:enabled ? "true" : "false",
    HUB_ZEUS_LINK_SECRET:secret};
  function request({method="GET",auth=secret,query="?marker="+marker,route=path,headers={}}={}) {
    const h = new Headers(headers);
    if(auth !== null)h.set("authorization","Bearer "+auth);
    return worker.fetch(new Request(origin+route+query,{method,headers:h}),env);
  }
  return {request,objects,env,get reads(){return reads},get writes(){return writes}};
}

const ok = harness();
let result = await ok.request();
assert.equal(result.status,200,"authorized preview probe should pass route-secret check");
assert.equal(result.headers.get("cache-control"),"private, no-store");
const body = await result.json();
assert.equal(body.ok,true);
assert.equal(body.source,"authenticated_live_hub_storage"); // identifier is code constant; underlying store is MOCK, not live
assert.equal(body.scope,"read_only_probe_v1");
assert.equal(body.markerFound,true);
assert.equal(body.pulseDate,"2026-11-22");
assert.equal(body.itemCount,2);
assert.equal(ok.writes,0);
assert.ok(ok.reads>0);
assert.equal(JSON.stringify(body).includes("Synthetic unrelated note"),false);
assert.equal(JSON.stringify(body).includes("synthetic"),false);
console.log("PASS: preview route reads injected synthetic R2 data and returns bounded metadata only");

for(const auth of [null,"bad-secret",""]) {
  const h = harness();
  result = await h.request({auth});
  assert.equal(result.status,403);
  assert.equal(h.reads,0);
  assert.equal(h.writes,0);
}
console.log("PASS: missing and wrong scoped credentials denied before storage reads");

const off=harness({enabled:false});
assert.equal((await off.request()).status,503);
assert.equal(off.reads,0);
const malformed=harness();
assert.equal((await malformed.request({query:"?marker=../admin"})).status,400);
assert.equal((await malformed.request({query:"?marker="+marker+"&extra=1"})).status,400);
assert.equal((await malformed.request({method:"POST"})).status,405);
assert.equal(malformed.reads,0);
assert.equal(malformed.writes,0);
console.log("PASS: disabled endpoint, invalid parameters and wrong methods block without data reads");

const missing=harness({outage:true});
result=await missing.request();
assert.equal(result.status,503);
assert.equal((await result.json()).ok,false);
assert.equal(missing.writes,0);
console.log("PASS: simulated storage outage blocks without claiming success");

const noMatch=harness({withMarker:false});
assert.equal((await (await noMatch.request()).json()).markerFound,false);
assert.equal(noMatch.writes,0);
console.log("PASS: marker not present is accurately reported");

const original=harness();
assert.equal((await original.request({route:"/api/state",query:"",auth:null})).status,401,
  "original browser state route requires signed-in user");
const signed=await original.request({route:"/api/state",query:"",auth:null,
                                    headers:{"oai-authenticated-user-id":"synthetic-owner"}});
assert.equal(signed.status,200);
assert.equal((await signed.json()).state.items.length,2);
assert.equal(original.writes,0);
console.log("PASS: existing owner-only browser route preserved in bundled preview");

console.log("PREVIEW RECEIPT: 6 synthetic integration checks passed; no live site/source or real SIWC tested; zero writes");
