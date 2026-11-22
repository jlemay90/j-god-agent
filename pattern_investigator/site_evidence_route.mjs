/** Draft-only owner-scoped private Hub pattern-evidence route.
 * Do not deploy directly: compare with verified live Sites source / owner permissions.
 * No generic Hub text, full item list, or keys are returned.
 */
export const EVIDENCE_PATH = "/api/pattern-investigator/evidence";
const ID = /^[a-zA-Z0-9][\w:-]{0,99}$/;
const LABEL = /^[a-zA-Z0-9][\w.:-]{0,99}$/;
const ALLOWED_GOAL = new Set(["income","financial_stability","fatherhood","health","relationships","freedom","growth","creativity","peace","other"]);
function respond(status, value) {
  return new Response(JSON.stringify(value), {status, headers:{
    "content-type":"application/json; charset=utf-8",
    "cache-control":"private, no-store", "x-content-type-options":"nosniff",
  }});
}
function equal(a,b) {
  const aa = new TextEncoder().encode(a), bb = new TextEncoder().encode(b);
  let diff = aa.length ^ bb.length;
  for(let i=0;i<Math.max(aa.length,bb.length);i++) diff |= (aa[i]??0) ^ (bb[i]??0);
  return diff===0;
}
function parseAllowlist(value) {
  if(typeof value!=="string" || !value || value.length>6000) return null;
  const ids=value.split(",").map(x=>x.trim());
  if(ids.length>50 || !ids.length || ids.some(x=>!ID.test(x))) return null;
  return new Set(ids);
}
function curate(items, allow) {
  if(!Array.isArray(items) || items.length>3000) throw Error("storage unavailable");
  const output=[];
  for(const item of items) {
    if(!allow.has(item?.id) || !Array.isArray(item?.patternEvidence)) continue;
    if(item.patternEvidence.length>5) throw Error("too many");
    for(const [n,e] of item.patternEvidence.entries()) {
      if(e?.authorized!==true || e?.sensitive!==false) continue;
      if(!LABEL.test(e.theme??"") || !ID.test(e.event_id??"") ||
         !ALLOWED_GOAL.has(e.goal) || !["supports","contradicts"].includes(e.polarity) ||
         !["observed_event","owner_report"].includes(e.basis) ||
         typeof e.occurred_at!=="string" || !/^\d{4}-\d\d-\d\dT/.test(e.occurred_at)) continue;
      output.push({
        id: item.id + ":" + n, event_id:e.event_id,
        source_ref:"hub:item:"+item.id, source_kind:"owner_reported",
        occurred_at:e.occurred_at, theme:e.theme, basis:e.basis,
        polarity:e.polarity, summary:"Curated owner-approved Hub evidence",
        goal:e.goal, authorized:true, sensitive:false,
      });
      if(output.length>100) throw Error("too many");
    }
  }
  return output;
}
/** Route auth is independent from Sites SIWC token, which must be checked at the platform gate.
 * dependencies={storage,readItems,clock?}; no write capability or secret logging.
 */
export async function readPatternEvidence(request,env,dependencies) {
  const url=new URL(request.url);
  if(url.pathname!==EVIDENCE_PATH) return respond(404,{ok:false,code:"NOT_FOUND"});
  if(request.method!=="GET") return respond(405,{ok:false,code:"READ_ONLY"});
  if(url.search || url.hash) return respond(400,{ok:false,code:"NO_QUERY"});
  const allow=parseAllowlist(env?.HUB_PATTERN_ALLOWED_ITEM_IDS);
  if(env?.HUB_PATTERN_READ_ENABLED!=="true" || typeof env?.HUB_PATTERN_LINK_SECRET!=="string" ||
     env.HUB_PATTERN_LINK_SECRET.length<32 || !allow) {
    return respond(503,{ok:false,code:"NOT_CONFIGURED"});
  }
  const auth=request.headers.get("authorization")??"";
  if(!auth.startsWith("Bearer ") ||
     !equal(auth.slice(7),env.HUB_PATTERN_LINK_SECRET)) {
    return respond(403,{ok:false,code:"FORBIDDEN"});
  }
  if(!dependencies || !dependencies.storage || typeof dependencies.readItems!=="function") {
    return respond(503,{ok:false,code:"NO_TRUSTED_STORAGE"});
  }
  try{
    const items=await dependencies.readItems(dependencies.storage);
    const observations=curate(items,allow);
    return respond(200,{ok:true,source:"owner_authenticated_curated_hub_pattern_evidence",
      scope:"pattern_read_only_v1",checkedAt:(dependencies.clock?.()??new Date()).toISOString(),
      sourceRevision: typeof env?.HUB_SITE_REVISION==="string" ? env.HUB_SITE_REVISION : null,
      observations});
  }catch{
    return respond(503,{ok:false,code:"STORAGE_OR_VALIDATION_FAILED"});
  }
}
