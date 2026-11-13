import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../dist/server/index.js", import.meta.url));
const { default: worker } = await import("data:text/javascript;base64," + source.toString("base64"));
const objects = new Map();
const revisions = new Map();
const bucket = {
  async get(key) { return objects.has(key) ? { etag: revisions.get(key), json: async () => JSON.parse(objects.get(key)) } : null; },
  async put(key, value, { onlyIf } = {}) {
    if (onlyIf?.etagDoesNotMatch === "*" && objects.has(key)) return null;
    if (onlyIf?.etagMatches && onlyIf.etagMatches !== revisions.get(key)) return null;
    objects.set(key, value);
    const etag = crypto.randomUUID();
    revisions.set(key, etag);
    return { etag };
  },
  async list({ prefix }) { return { objects: [...objects.keys()].filter(key => key.startsWith(prefix)).map(key => ({ key })), truncated: false }; },
};
const env = { BUCKET: bucket };
const origin = "https://hub.example";
const user = { "oai-authenticated-user-id": "owner-1" };
const call = (path, options = {}) => worker.fetch(new Request(origin + path, options), env);
const post = (action, headers = {}) => call("/api/action", { method: "POST", headers: { ...user, origin, "content-type": "application/json", ...headers }, body: JSON.stringify(action) });
const rpc = async (id, method, params = {}) => {
  const response = await call("/mcp", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id, method, params }) });
  return response.json();
};

assert.equal((await call("/api/state")).status, 401);
assert.equal((await post({ action: "addItem", text: "Test" }, { origin: "https://wrong.example" })).status, 403);
let state = await (await call("/api/state", { headers: user })).json();
assert.deepEqual(state.state.items, []);

const added = await (await post({ action: "addItem", text: "Call customer", type: "Sales" })).json();
assert.equal(added.ok, true);
assert.equal(added.result.done, false);
await post({ action: "setFocus", values: ["Call customer", "Review calendar", ""] });
state = await (await call("/api/state", { headers: user })).json();
assert.equal(state.state.items[0].text, "Call customer");
assert.equal(state.state.focus[1], "Review calendar");

const discovery = await rpc(1, "server/discover");
assert.deepEqual(discovery.result.supportedVersions, ["2026-07-28"]);
const tools = await rpc(2, "tools/list");
assert.ok(tools.result.tools.some(tool => tool.name === "publish_daily_pulse"));
const before = await rpc(3, "tools/call", { name: "get_hub_state", arguments: {} });
assert.match(before.result.content[0].text, /Call customer/);
const publish = await rpc(4, "tools/call", {
  name: "publish_daily_pulse",
  arguments: { date: "2026-10-27", headline: "Three clean moves", top3: ["Call customer", "Review calendar"], summary: "Start with the confirmed follow-ups." },
});
assert.equal(publish.result.isError, undefined);
state = await (await call("/api/state", { headers: user })).json();
assert.equal(state.state.pulse.top3[0], "Call customer");
assert.equal(state.state.items.length, 1);
const done = await rpc(5, "tools/call", { name: "set_hub_item_done", arguments: { id: added.result.id, done: true } });
assert.equal(done.result.isError, undefined);
state = await (await call("/api/state", { headers: user })).json();
assert.equal(state.state.items[0].done, true);

console.log("Shared Hub API and MCP read/write checks passed");

const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Chicago', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const goal = await (await post({ action: 'saveGoal', title: 'Finish the Hub', why: 'Make life easier', milestones: ['Reliable daily loop', 'Seven real use days'] })).json();
assert.equal(goal.ok, true);
assert.equal(goal.result.startDate, today);
const edited = await (await post({ action: 'saveGoal', title: 'Finish a useful Hub', startDate: '2026-01-01' })).json();
assert.equal(edited.result.id, goal.result.id);
assert.equal(edited.result.startDate, today);
assert.equal(edited.result.why, 'Make life easier');
await post({ action: 'saveCheckin', date: today, morning: true, nextAction: 'Test one real task', tinyStart: 'Open the Hub' });
await post({ action: 'saveCheckin', date: today, win: 'Found a confusing button', goalActionDone: true });
await post({ action: 'saveCheckin', date: today, win: 'Found a confusing button', goalActionDone: true });
state = await (await call('/api/state', { headers: user })).json();
assert.equal(state.state.checkins.length, 1, 'Repeat saves must update one date, not create extra progress days');
assert.equal(state.state.checkins[0].morning, true, 'Partial updates preserve earlier check-ins');
assert.equal(state.state.checkins[0].nextAction, 'Test one real task');
assert.equal((await post({ action: 'saveCheckin', date: '2026-02-31', win: 'invalid' })).status, 400);
assert.equal((await post({ action: 'saveCheckin', date: '2099-01-01', win: 'future' })).status, 400);
await post({ action: 'setMilestone', id: goal.result.milestones[0].id, done: true });
state = await (await call('/api/state', { headers: user })).json();
assert.equal(state.state.goal.milestones[0].done, true);
const memory = { action: 'saveMemory', summary: 'Shared verified project record', decisions: ['One daily task'], backlog: ['Approval inbox is proposed'], nextSteps: ['Test on mobile'] };
assert.equal((await post(memory)).status, 200);
assert.equal((await post({ ...memory, revision: 0 })).status, 400, 'Stale project edits are rejected');
assert.equal((await post({ ...memory, summary: 'Updated verified record', revision: 1 })).status, 200);
assert.ok([...objects.keys()].some(key => key.includes('memory-history/')), 'Previous project record is retained');
const queueItems = [];
for (let index = 0; index < 4; index++) queueItems.push((await (await post({ action: 'addItem', text: 'Queue item ' + index })).json()).result);
for (const item of queueItems.slice(0, 3)) assert.equal((await post({ action: 'setItemQueue', id: item.id, queue: 'Now' })).status, 200);
assert.equal((await post({ action: 'setItemQueue', id: queueItems[3].id, queue: 'Now' })).status, 400, 'Now is capped at three open moves');
assert.equal((await post({ action: 'setItemQueue', id: queueItems[3].id, queue: 'Waiting' })).status, 200);
const updatedTools = await rpc(10, 'tools/list');
for (const name of ['save_hub_goal', 'save_hub_checkin', 'update_hub_project_memory', 'set_hub_item_queue']) assert.ok(updatedTools.result.tools.some(tool => tool.name === name));
console.log('Goal persistence, merged check-ins, memory recovery, and queue limits passed');

// Motivation reflections share check-ins without claiming task completion.
const beforeLoop = await (await call('/api/state', {headers:user})).json();
const loopDate = beforeLoop.state.today;
const savedLoop = await (await post({action:'saveCheckin',date:loopDate,motivationOutcome:'stuck',motivationNote:'Could not find the original source.',motivationNext:'Open the sales log.',motivationCue:'After breakfast'})).json();
assert.equal(savedLoop.ok,true);
const afterLoop = await (await call('/api/state',{headers:user})).json();
assert.equal(afterLoop.state.checkins.find(day=>day.date===loopDate).motivationNext,'Open the sales log.');
assert.deepEqual(afterLoop.state.items,beforeLoop.state.items);
assert.equal((await (await post({action:'saveCheckin',date:loopDate,motivationOutcome:'invented'})).json()).ok,false);
const mobileManifest=await (await call('/manifest.webmanifest')).json();
assert.equal(mobileManifest.display,'standalone');
assert.equal((await call('/app-icon.png')).headers.get('content-type'),'image/png');
assert.equal((await call('/sw.js')).status,200);
console.log('Mobile manifest, shared motivation persistence and unchanged task completion passed');

const planningBefore = (await (await call('/api/state', { headers: user })).json()).state;
const coaching = planningBefore.planning.find(record => record.id === 'coaching');
assert.equal(coaching.evidence, 'assumption');
assert.equal(coaching.status, 'waiting');
const project = {
  action: 'savePlanRecord', kind: 'project', status: 'active', evidence: 'confirmed',
  title: 'A real project', itemIds: [added.result.id], actionItem: added.result.id,
  reviewed: today, steps: [{ label: 'Check the source', done: true }],
};
const createdPlan = await (await post(project)).json();
assert.equal(createdPlan.ok, true);
const savedProject = createdPlan.result.find(record => record.title === project.title);
assert.equal(savedProject.steps[0].done, true);
assert.equal((await post({ ...project, itemIds: [] })).status, 400);
const concurrent = await Promise.all([
  post({ ...project, id: savedProject.id, rev: savedProject.rev, title: 'Updated once' }),
  post({ ...project, id: savedProject.id, rev: savedProject.rev, title: 'Concurrent update' }),
]);
assert.deepEqual(concurrent.map(response => response.status).sort(), [200, 400]);
const removed = await (await post({ action: 'removePlanRecord', id: coaching.id, rev: 0 })).json();
assert.equal(removed.ok, true);
const planningAfter = (await (await call('/api/state', { headers: user })).json()).state;
assert.ok(!planningAfter.planning.some(record => record.id === coaching.id));
assert.deepEqual(planningAfter.items, planningBefore.items);
assert.deepEqual(planningAfter.goal, planningBefore.goal);
console.log('Planning links, removal, stale-write protection, and original Hub records passed');
