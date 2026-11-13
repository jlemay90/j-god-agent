const INDEX_HTML = "";
const APP_ICON_BASE64 = "";
const PREFIX = "hub/v1/";
const ITEMS_PREFIX = PREFIX + "items/";
const FOCUS_KEY = PREFIX + "focus.json";
const PULSE_KEY = PREFIX + "pulse.json";
const GOAL_KEY = PREFIX + "goal.json";
const CHECKINS_PREFIX = PREFIX + "checkins/";
const MEMORY_KEY = PREFIX + "project-memory.json";
const TYPES = new Set(["Task", "Sales", "Money", "Reminder", "Journal", "Idea", "Note"]);
const QUEUES = new Set(["Inbox", "Now", "Next", "Waiting", "Verify", "Backlog"]);

function json(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "private, no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function error(message, status = 400) {
  return json({ ok: false, error: message }, status);
}

function bucket(env) {
  if (!env?.BUCKET) throw new Error("Hub storage is unavailable.");
  return env.BUCKET;
}

async function readObject(storage, key) {
  const object = await storage.get(key);
  return object ? await object.json() : null;
}

async function writeObject(storage, key, value) {
  await storage.put(key, JSON.stringify(value), {
    httpMetadata: { contentType: "application/json" },
  });
}

function cleanText(value, max, label, required = true) {
  if (typeof value !== "string") throw new Error(label + " must be text.");
  const text = value.trim();
  if (required && !text) throw new Error(label + " is required.");
  if (text.length > max) throw new Error(label + " is too long.");
  return text;
}

function validId(value) {
  return typeof value === "string" && /^[0-9a-f-]{36}$/i.test(value);
}

function localDate() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

function validDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(value + "T12:00:00Z");
  return !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === value;
}

async function readCheckins(storage, goal) {
  const cutoff = new Date(localDate() + "T12:00:00Z");
  cutoff.setUTCDate(cutoff.getUTCDate() - 45);
  const listing = await storage.list({ prefix: CHECKINS_PREFIX, startAfter: CHECKINS_PREFIX + cutoff.toISOString().slice(0, 10), limit: 100 });
  const keys = new Set(listing.objects.map(({ key }) => key));
  if (goal?.startDate && goal.startDate < cutoff.toISOString().slice(0, 10)) {
    const cycle = await storage.list({ prefix: CHECKINS_PREFIX, startAfter: CHECKINS_PREFIX + goal.startDate, limit: 31 });
    cycle.objects.filter(({ key }) => key < CHECKINS_PREFIX + goal.deadline).forEach(({ key }) => keys.add(key));
  }
  const days = await Promise.all([...keys].map(key => readObject(storage, key)));
  return days.filter(Boolean).sort((a, b) => b.date.localeCompare(a.date));
}

async function saveGoal(storage, args) {
  const old = await readObject(storage, GOAL_KEY);
  const goal = { ...old, id: old?.id ?? crypto.randomUUID() };
  for (const [field, max] of Object.entries({ title: 300, why: 600, measure: 600, nextStep: 500, cue: 300, obstacle: 300, response: 500, service: 400 })) {
    if (args[field] !== undefined) goal[field] = cleanText(args[field], max, field, field === "title");
  }
  if (!goal.title) throw new Error("Name your goal first.");
  goal.startDate = old?.startDate ?? args.startDate ?? localDate();
  if (!validDate(goal.startDate) || goal.startDate > localDate()) throw new Error("Choose a valid start date up to today.");
  const end = new Date(goal.startDate + "T12:00:00Z"); end.setUTCDate(end.getUTCDate() + 30);
  goal.deadline = old?.deadline ?? end.toISOString().slice(0, 10);
  if (!old) {
    goal.milestones = (args.milestones ?? []).slice(0, 8).map((value) => ({ id: crypto.randomUUID(), label: cleanText(value, 300, "Milestone"), done: false }));
  }
  goal.updatedAt = new Date().toISOString();
  await writeObject(storage, GOAL_KEY, goal);
  return goal;
}

async function setMilestone(storage, args) {
  if (!validId(args.id) || typeof args.done !== "boolean") throw new Error("Choose a milestone and its status.");
  const goal = await readObject(storage, GOAL_KEY);
  const milestone = goal?.milestones?.find(value => value.id === args.id);
  if (!milestone) throw new Error("Milestone was not found.");
  milestone.done = args.done;
  milestone.updatedAt = new Date().toISOString();
  await writeObject(storage, GOAL_KEY, goal);
  return milestone;
}

async function saveCheckin(storage, args) {
  const today = localDate();
  if (!validDate(args.date) || args.date > today) throw new Error("Use today's date or a past date.");
  const age = (new Date(today + "T12:00:00Z") - new Date(args.date + "T12:00:00Z")) / 86400000;
  if (age > 45) throw new Error("Check-ins can be recorded for the last 45 days.");
  const key = CHECKINS_PREFIX + args.date + ".json";
  const day = { ...(await readObject(storage, key) ?? {}), date: args.date };
  for (const [field, max] of Object.entries({ nextAction: 500, moveStatus: 150, tinyStart: 300, win: 700, friction: 700, tomorrow: 500, presentMoment: 500, motivationNote: 500, motivationNext: 300, motivationCue: 200 })) {
    if (args[field] !== undefined) day[field] = cleanText(args[field], max, field, false);
  }
  if (args.motivationOutcome !== undefined) {
    if (!['progress', 'waiting', 'stuck'].includes(args.motivationOutcome)) throw new Error('Choose a valid outcome.');
    day.motivationOutcome = args.motivationOutcome;
    day.motivationRecordedAt = new Date().toISOString();
  }
  for (const field of ["morning", "midday", "evening", "goalActionDone"]) {
    if (args[field] !== undefined) {
      if (typeof args[field] !== "boolean") throw new Error(field + " must be true or false.");
      day[field] = args[field];
    }
  }
  if (args.energy !== undefined) {
    if (!["low", "steady", "strong"].includes(args.energy)) throw new Error("Choose an energy level.");
    day.energy = args.energy;
  }
  day.updatedAt = new Date().toISOString();
  await writeObject(storage, key, day);
  return day;
}

async function saveMemory(storage, args) {
  const old = await readObject(storage, MEMORY_KEY);
  if (old && args.revision !== old.revision) throw new Error("The project record changed. Read the latest version before editing.");
  const memory = { summary: cleanText(args.summary, 5000, "Project summary"), revision: (old?.revision ?? 0) + 1, updatedAt: new Date().toISOString() };
  for (const field of ["decisions", "backlog", "nextSteps"]) {
    if (!Array.isArray(args[field]) || args[field].length > 30) throw new Error(field + " must contain up to 30 entries.");
    memory[field] = args[field].map(value => cleanText(value, 700, field));
  }
  if (old) await writeObject(storage, PREFIX + "memory-history/" + crypto.randomUUID() + ".json", old);
  await writeObject(storage, MEMORY_KEY, memory);
  return memory;
}

async function readItems(storage) {
  const listing = await storage.list({ prefix: ITEMS_PREFIX, limit: 1000 });
  if (listing.truncated) throw new Error("Hub has too many items to load safely.");
  const items = await Promise.all(listing.objects.map(async ({ key }) => readObject(storage, key)));
  return items.filter(Boolean).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

/*PLANNING_WORKER*/

async function readState(storage) {
  const goal = await readObject(storage, GOAL_KEY);
  const [focus, pulse, items, checkins, projectMemory, plan] = await Promise.all([
    readObject(storage, FOCUS_KEY),
    readObject(storage, PULSE_KEY),
    readItems(storage),
    readCheckins(storage, goal),
    readObject(storage, MEMORY_KEY),
    readPlan(storage),
  ]);
  return {
    focus: Array.isArray(focus?.values) ? focus.values.slice(0, 3) : ["", "", ""],
    focusUpdatedAt: focus?.updatedAt ?? null,
    pulse: pulse ?? null,
    items,
    goal,
    checkins,
    today: localDate(),
    projectMemory,
    planning: plan.records,
  };
}

async function addItem(storage, args) {
  const text = cleanText(args?.text, 500, "Item");
  const type = args?.type ?? "Task";
  if (!TYPES.has(type)) throw new Error("Choose a supported item type.");
  const item = {
    id: crypto.randomUUID(),
    text,
    type,
    queue: "Inbox",
    done: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  await writeObject(storage, ITEMS_PREFIX + item.id + ".json", item);
  return item;
}

async function setItemDone(storage, args) {
  if (!validId(args?.id) || typeof args?.done !== "boolean") throw new Error("Valid item ID and done status are required.");
  const key = ITEMS_PREFIX + args.id + ".json";
  const item = await readObject(storage, key);
  if (!item) throw new Error("Item was not found.");
  if (!args.done && item.done && item.queue === "Now") {
    const now = (await readItems(storage)).filter(value => !value.done && value.queue === "Now");
    if (now.length >= 3) throw new Error("Now already has three open moves. Move one out before reopening this one.");
  }
  item.done = args.done;
  item.updatedAt = new Date().toISOString();
  item.doneAt = args.done ? item.updatedAt : null;
  await writeObject(storage, key, item);
  return item;
}

async function setItemQueue(storage, args) {
  if (!validId(args.id) || !QUEUES.has(args.queue)) throw new Error("Choose a valid item and queue.");
  const key = ITEMS_PREFIX + args.id + ".json", item = await readObject(storage, key);
  if (!item) throw new Error("Item was not found.");
  if (args.queue === "Now" && item.queue !== "Now") {
    const now = (await readItems(storage)).filter(value => !value.done && value.queue === "Now" && value.id !== item.id);
    if (now.length >= 3) throw new Error("Now already has three open moves. Move one out before adding another.");
  }
  item.queue = args.queue;
  for (const field of ["whyNow", "startStep", "source", "finishCondition"]) {
    if (args[field] !== undefined) item[field] = cleanText(args[field], 700, field, false);
  }
  item.updatedAt = new Date().toISOString();
  await writeObject(storage, key, item);
  return item;
}

async function setFocus(storage, args) {
  if (!Array.isArray(args?.values) || args.values.length !== 3) throw new Error("Top 3 must contain three entries.");
  const values = args.values.map((value, index) => cleanText(value, 240, "Top 3 item " + (index + 1), false));
  const focus = { values, updatedAt: new Date().toISOString() };
  await writeObject(storage, FOCUS_KEY, focus);
  return focus;
}

async function publishPulse(storage, args) {
  if (typeof args?.date !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(args.date)) throw new Error("Use a YYYY-MM-DD date.");
  if (!Array.isArray(args.top3) || args.top3.length < 1 || args.top3.length > 3) throw new Error("Provide one to three top priorities.");
  const pulse = {
    date: args.date,
    headline: cleanText(args.headline, 240, "Headline"),
    top3: args.top3.map((value, index) => cleanText(value, 500, "Priority " + (index + 1))),
    summary: cleanText(args.summary, 4000, "Summary"),
    fullText: cleanText(args.fullText ?? "", 24000, "Full brief", false),
    publishedAt: new Date().toISOString(),
  };
  for (const field of ["nextAction", "tinyStart", "goalConnection", "experiment"]) {
    if (args[field] !== undefined) pulse[field] = cleanText(args[field], 700, field, false);
  }
  await writeObject(storage, PULSE_KEY, pulse);
  return pulse;
}

async function api(request, env, path) {
  if (!request.headers.get("oai-authenticated-user-id")) return error("Sign in to your private Hub.", 401);
  const storage = bucket(env);
  if (path === "/api/state" && request.method === "GET") return json({ ok: true, state: await readState(storage) });
  if (path !== "/api/action" || request.method !== "POST") return error("Not found.", 404);
  const origin = request.headers.get("origin");
  if (!origin || origin !== new URL(request.url).origin) return error("This action must come from the Hub.", 403);
  if (!request.headers.get("content-type")?.startsWith("application/json")) return error("Use JSON.", 415);
  const body = await request.text();
  if (body.length > 32000) return error("Request is too large.", 413);
  let input;
  try { input = JSON.parse(body); } catch { return error("Invalid JSON."); }
  try {
    let result;
    if (input.action === "addItem") result = await addItem(storage, input);
    else if (input.action === "setItemDone") result = await setItemDone(storage, input);
    else if (input.action === "setFocus") result = await setFocus(storage, input);
    else if (input.action === "saveGoal") result = await saveGoal(storage, input);
    else if (input.action === "saveCheckin") result = await saveCheckin(storage, input);
    else if (input.action === "setMilestone") result = await setMilestone(storage, input);
    else if (input.action === "saveMemory") result = await saveMemory(storage, input);
    else if (input.action === "setItemQueue") result = await setItemQueue(storage, input);
    else if (["savePlanRecord", "removePlanRecord"].includes(input.action)) result = await mutatePlan(storage, input);
    else return error("Unknown action.");
    return json({ ok: true, result });
  } catch (cause) {
    return error(cause.message);
  }
}

/*ZEUS_BRIDGE*/

const MCP_TOOLS = [
  {
    name: "ask_zeus",
    description: "Send an owner-authorized message to Zeus and return his actual reply through the existing private bridge. Uses the existing model budget. Supply a fresh UUID requestId per new message; retry the identical message with the same UUID. Replies are available in get_hub_state. Suggested Hub changes are never applied by this tool.",
    inputSchema: { type: "object", properties: { message: { type: "string", minLength: 1, maxLength: 2000 }, requestId: { type: "string", format: "uuid" }, panel: { type: "string", enum: ["today", "inbox", "build"], default: "today" } }, required: ["message", "requestId"], additionalProperties: false },
  },
  {
    name: "get_hub_state",
    description: "Read the owner's shared J Command Hub priorities, open and completed items, and latest published Daily Pulse. Use this before preparing the morning brief.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
  },
  {
    name: "publish_daily_pulse",
    description: "Publish a concise, verified Daily Pulse to the private Hub after preparing the morning brief. Use the owner's local date and include the same top priorities and summary sent in the morning message.",
    inputSchema: {
      type: "object",
      properties: {
        date: { type: "string", description: "Local date, YYYY-MM-DD." },
        headline: { type: "string" },
        top3: { type: "array", items: { type: "string" }, minItems: 1, maxItems: 3 },
        summary: { type: "string" },
        fullText: { type: "string", description: "Optional full morning brief." },
        nextAction: { type: "string", description: "One suggested next action based on verified priorities and the owner's goal." },
        tinyStart: { type: "string", description: "A concrete small beginning; do not invent missing contact or account details." },
        goalConnection: { type: "string", description: "How the suggested action supports the 30-day goal, or why an urgent responsibility comes first." },
        experiment: { type: "string", description: "One small, reversible process improvement based on the owner's check-ins. Label suggestions as suggestions." },
      },
      required: ["date", "headline", "top3", "summary"],
      additionalProperties: false,
    },
  },
  {
    name: "add_hub_item",
    description: "Add a task, reminder, sales follow-up, or note to the owner's shared Hub when the user explicitly asks to capture it.",
    inputSchema: {
      type: "object",
      properties: {
        text: { type: "string" },
        type: { type: "string", enum: [...TYPES] },
      },
      required: ["text"],
      additionalProperties: false,
    },
  },
  {
    name: "set_hub_item_queue",
    description: "Organize an item into Inbox, Now, Next, Waiting, Verify, or Backlog. For Now include whyNow, a concrete startStep, source/date, and finishCondition. Waiting is a dependency, not an executable next move. Queue changes do not assert completion or edit other sources.",
    inputSchema: { type: "object", properties: { id: { type: "string" }, queue: { type: "string", enum: [...QUEUES] }, ...Object.fromEntries(["whyNow", "startStep", "source", "finishCondition"].map(field => [field, { type: "string" }])) }, required: ["id", "queue"], additionalProperties: false },
  },
  {
    name: "update_hub_project_memory",
    description: "Update the shared project record with verified decisions, open requirements, and next steps. Read get_hub_state first, preserve unresolved requests, use the current revision, and distinguish proposals from accepted decisions. Prior versions are retained for recovery.",
    inputSchema: { type: "object", properties: { summary: { type: "string" }, revision: { type: "integer" }, ...Object.fromEntries(["decisions", "backlog", "nextSteps"].map(field => [field, { type: "array", items: { type: "string" }, maxItems: 30 }])) }, required: ["summary", "decisions", "backlog", "nextSteps"], additionalProperties: false },
  },
  {
    name: "save_hub_goal",
    description: "Save or edit the owner's 30-day goal only when explicitly requested. Preserve its start date and milestone progress when editing. A goal is a plan, not a guaranteed outcome.",
    inputSchema: { type: "object", properties: Object.fromEntries(["title", "why", "measure", "nextStep", "cue", "obstacle", "response", "service"].map(name => [name, { type: "string" }])), additionalProperties: false },
  },
  {
    name: "save_hub_checkin",
    description: "Record the owner's stated daily plan, progress, friction, or presence reflection. Use partial updates. Never infer that a task was completed from a timer, positive wording, or elapsed time.",
    inputSchema: {
      type: "object",
      properties: {
        date: { type: "string", description: "America/Chicago date, YYYY-MM-DD." },
        ...Object.fromEntries(["nextAction", "tinyStart", "win", "friction", "tomorrow", "presentMoment"].map(name => [name, { type: "string" }])),
        ...Object.fromEntries(["morning", "midday", "evening", "goalActionDone"].map(name => [name, { type: "boolean" }])),
        energy: { type: "string", enum: ["low", "steady", "strong"] },
      },
      required: ["date"], additionalProperties: false,
    },
  },
  {
    name: "set_hub_item_done",
    description: "Mark a shared Hub item complete or reopen it when the user confirms its status.",
    inputSchema: {
      type: "object",
      properties: {
        id: { type: "string" },
        done: { type: "boolean" },
      },
      required: ["id", "done"],
      additionalProperties: false,
    },
  },
];

function mcpResult(id, result) {
  return json({ jsonrpc: "2.0", id, result });
}

function mcpError(id, code, message) {
  return json({ jsonrpc: "2.0", id, error: { code, message } });
}

async function mcp(request, env) {
  if (request.method !== "POST") return error("Use POST.", 405);
  const body = await request.text();
  if (body.length > 48000) return mcpError(null, -32600, "Request is too large.");
  let call;
  try { call = JSON.parse(body); } catch { return mcpError(null, -32700, "Invalid JSON."); }
  const id = call?.id ?? null;
  if (call?.method === "server/discover") return mcpResult(id, { supportedVersions: ["2026-07-28"], capabilities: { tools: {} } });
  if (call?.method === "initialize") return mcpResult(id, { protocolVersion: "2026-07-28", capabilities: { tools: {} }, serverInfo: { name: "j-command-hub", version: "1.0.0" } });
  if (call?.method === "tools/list") return mcpResult(id, { tools: MCP_TOOLS });
  if (call?.method !== "tools/call") return mcpError(id, -32601, "Method not found.");
  const name = call.params?.name;
  const args = call.params?.arguments ?? {};
  try {
    const storage = bucket(env);
    let result;
    if (name === "get_hub_state") {
      const state = await readState(storage);
      result = { ...state, items: state.items.slice(0, 300), zeusConversations: await zeusConversations(storage, request.headers.get('oai-authenticated-user-id')) };
    } else if (name === "ask_zeus") {
      result = await askZeusFromMcp(request, env, args);
    } else if (name === "publish_daily_pulse") result = await publishPulse(storage, args);
    else if (name === "add_hub_item") result = await addItem(storage, args);
    else if (name === "set_hub_item_done") result = await setItemDone(storage, args);
    else if (name === "save_hub_goal") result = await saveGoal(storage, args);
    else if (name === "save_hub_checkin") result = await saveCheckin(storage, args);
    else if (name === "update_hub_project_memory") result = await saveMemory(storage, args);
    else if (name === "set_hub_item_queue") result = await setItemQueue(storage, args);
    else return mcpResult(id, { content: [{ type: "text", text: "Unknown Hub tool." }], isError: true });
    return mcpResult(id, { content: [{ type: "text", text: JSON.stringify(result) }] });
  } catch (cause) {
    return mcpResult(id, { content: [{ type: "text", text: cause.message }], isError: true });
  }
}

export default {
  async fetch(request, env) {
    try {
      const path = new URL(request.url).pathname;
      if (request.method === 'GET' && path === '/manifest.webmanifest') return new Response(JSON.stringify({ id: '/', name: 'J Command Hub', short_name: 'J Hub', start_url: '/#today', scope: '/', display: 'standalone', background_color: '#0b1420', theme_color: '#0b1420', icons: [{ src: '/app-icon.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' }], shortcuts: [{ name: 'Capture a thought', url: '/#inbox' }, { name: 'Goals & Projects', url: '/#planning' }] }), { headers: { 'content-type': 'application/manifest+json', 'cache-control': 'private, no-cache' } });
      if (request.method === 'GET' && path === '/app-icon.png') return new Response(Uint8Array.from(atob(APP_ICON_BASE64), c => c.charCodeAt(0)), { headers: { 'content-type': 'image/png', 'cache-control': 'private, max-age=3600' } });
      if (request.method === 'GET' && path === '/sw.js') return new Response("self.addEventListener('install',()=>self.skipWaiting());self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));self.addEventListener('fetch',event=>{if(event.request.mode==='navigate')event.respondWith(fetch(event.request).catch(()=>new Response('<!doctype html><meta name=viewport content=\"width=device-width,initial-scale=1\"><title>J Hub · Offline</title><body style=\"background:#0b1420;color:#f3f1e9;font:18px system-ui;padding:30px\"><h1>You are offline.</h1><p>Reconnect to open your private Hub and save changes.</p><a style=\"color:#7ce5c4\" href=\"/\">Try again</a></body>',{headers:{'content-type':'text/html'}})))});", { headers: { 'content-type': 'application/javascript', 'cache-control': 'no-cache' } });
      if (path === "/" && request.method === "GET") {
        return new Response(INDEX_HTML, {
          headers: { "content-type": "text/html; charset=utf-8", "cache-control": "private, no-store", "x-content-type-options": "nosniff" },
        });
      }
      if (path === "/mcp") return await mcp(request, env);
      if (path.startsWith("/api/zeus/")) return await zeusApi(request, env, path);
      if (path.startsWith("/api/")) return await api(request, env, path);
      return new Response("Not found", { status: 404 });
    } catch (cause) {
      return error(cause.message === "Hub storage is unavailable." ? cause.message : "Hub request failed.", 503);
    }
  },
};
