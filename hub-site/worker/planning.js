const PLAN_KEY = PREFIX + "planning.json";
const PLAN_SEED = [
  { id: "career", kind: "project", area: "Work", title: "Find work with more schedule control", status: "active", evidence: "confirmed", reviewed: "2026-11-09", source: "Nov 9 career discussion and Hub Daily Pulse", outcome: "Compare work options against the schedule and income you actually need.", next: "Write three schedule nonnegotiables and score one job posting.", itemIds: ["0877655e-e923-4aad-b570-bc0beac025b3"], questions: "Which hours protect parenting time? What income floor makes a move viable?" },
  { id: "parenting", kind: "project", area: "Parenting", title: "Better Father Hub", status: "active", evidence: "confirmed", reviewed: "2026-11-04", source: "Better Father Hub notes in the Inbox", outcome: "Build a repeatable check-in and agree on a school-night routine together.", itemIds: ["26f5ba59-6292-4423-ad1a-1ce9daa6622d", "feb8abde-bdd6-4ce0-abb6-7f6d0b9e65dd"], actionItem: "26f5ba59-6292-4423-ad1a-1ce9daa6622d", questions: "What routine feels fair and useful to both of you?" },
  { id: "coaching", kind: "project", area: "Wrestling", title: "Confirm wrestling coaching onboarding", status: "waiting", evidence: "assumption", reviewed: "2026-11-09", source: "Nov 9 Daily Pulse reports certificates sent. Receipt is unverified.", outcome: "Know which onboarding steps remain and who owns them.", blocker: "Certificate receipt and any remaining onboarding steps need confirmation.", questions: "Who confirms receipt and clearance to coach?" },
  { id: "finance", kind: "project", area: "Finances", title: "Clarify tax and debt next steps", status: "active", evidence: "confirmed", reviewed: "2026-11-09", source: "Tax and bankruptcy records in the Inbox", outcome: "Get the filing requirements and sequence directly from the appropriate professional.", itemIds: ["7332a279-682b-4c77-9780-cbdb26151f74", "9c23e1d3-87b3-422d-bc70-7a7854714cd2"], actionItem: "7332a279-682b-4c77-9780-cbdb26151f74", blocker: "Bankruptcy consultation follows the tax clarification.", decisions: "Handle the tax clarification first. See linked Hub records for the current status." },
  { id: "zeus", kind: "project", area: "Hub & Zeus", title: "Verify Zeus can read back Hub records", status: "active", evidence: "confirmed", reviewed: "2026-11-09", source: "Zeus readback follow-up in the Inbox", outcome: "Verify a Hub record can be independently read back by Zeus.", itemIds: ["06a33d16-dd9e-4a4a-9a99-ee62997d771f"], actionItem: "06a33d16-dd9e-4a4a-9a99-ee62997d771f", resource: "memory" },
  { id: "housing", kind: "goal", horizon: "long", area: "Life rebuild", title: "Build a path to stable housing", status: "active", evidence: "confirmed", reviewed: "2026-11-09", source: "Housing goal and live rental-history record", outcome: "Know what is on the rental record and what needs correction or follow-up.", itemIds: ["eb33502f-e9b1-45c6-b488-c8460f9169b4"] },
  { id: "credit", kind: "goal", horizon: "long", area: "Finances", title: "Rebuild credit and financial breathing room", status: "active", evidence: "confirmed", reviewed: "2026-11-04", source: "Nov 4 credit-rebuild discussion", outcome: "Build a realistic budget and choose the next credit step once the financial picture is clear." },
  { id: "presence", kind: "goal", horizon: "long", area: "Parenting", title: "Be a present and dependable dad", status: "active", evidence: "confirmed", reviewed: "2026-11-04", source: "Better Father Hub directive", outcome: "Keep regular check-ins and follow through on the commitments we make together.", itemIds: ["feb8abde-bdd6-4ce0-abb6-7f6d0b9e65dd"] },
  { id: "job-filter", kind: "goal", horizon: "short", area: "Work", title: "Define what a better-fit job needs to offer", status: "active", evidence: "assumption", reviewed: "2026-11-09", source: "Proposed finish line based on the Nov 9 Daily Pulse", outcome: "Write the must-haves, flex points, and dealbreakers for a job change.", itemIds: ["0877655e-e923-4aad-b570-bc0beac025b3"] },
];

async function readPlan(storage) {
  const object = await storage.get(PLAN_KEY);
  return { etag: object?.etag, records: object ? await object.json() : PLAN_SEED };
}

function planRecord(input, id, storageItems) {
  const result = { id };
  for (const [field, values] of Object.entries({
    kind: ["goal", "project"], status: ["active", "waiting", "paused", "done"], evidence: ["confirmed", "assumption"],
  })) {
    if (!values.includes(input[field])) throw new Error("Choose a valid " + field + ".");
    result[field] = input[field];
  }
  if (result.kind === "goal") {
    if (!["short", "long"].includes(input.horizon)) throw new Error("Choose a time horizon.");
    result.horizon = input.horizon;
  }
  for (const [field, max] of Object.entries({title: 110, area: 40, outcome: 420, next: 420, blocker: 420, notes: 1500, decisions: 1500, questions: 1500, source: 240})) {
    result[field] = cleanText(input[field] ?? "", max, field, field === "title");
  }
  for (const field of ["deadline", "reviewed"]) {
    const date = input[field] ?? "";
    if (date && (!validDate(date) || (field === "reviewed" && date > localDate()))) throw new Error("Choose a valid " + field + " date.");
    result[field] = date;
  }
  if (!Array.isArray(input.itemIds) || input.itemIds.length > 4 || input.itemIds.some(id => !validId(id) || !storageItems.has(id))) {
    throw new Error("Choose up to four existing Hub items.");
  }
  result.itemIds = [...new Set(input.itemIds)];
  result.actionItem = input.actionItem ?? "";
  if (result.actionItem && !result.itemIds.includes(result.actionItem)) throw new Error("Link the next-action item to this record first.");
  result.resource = input.resource === "memory" ? "memory" : "";
  if (!Array.isArray(input.steps) || input.steps.length > 12) throw new Error("Use up to twelve progress steps.");
  result.steps = input.steps.map(step => ({ label: cleanText(step?.label, 160, "Progress step"), done: step?.done === true }));
  return result;
}

async function mutatePlan(storage, input) {
  const plan = await readPlan(storage);
  const prior = plan.records.find(record => record.id === input.id);
  if ((input.id && !prior) || (prior && (prior.rev ?? 0) !== input.rev)) throw new Error("This record changed. Refresh and reopen it before saving.");
  const records = [...plan.records];
  if (input.action === "removePlanRecord") {
    if (!prior) throw new Error("Choose a saved record to remove.");
    records.splice(records.indexOf(prior), 1);
  } else {
    if (!prior && records.length >= 50) throw new Error("Keep up to 50 planning records. Remove one before adding another.");
    const itemIds = new Set((await readItems(storage)).map(item => item.id));
    const next = planRecord(input, prior?.id ?? crypto.randomUUID(), itemIds);
    next.rev = (prior?.rev ?? 0) + 1;
    if (prior) records[records.indexOf(prior)] = next;
    else records.push(next);
  }
  const saved = await storage.put(PLAN_KEY, JSON.stringify(records), {
    onlyIf: plan.etag ? { etagMatches: plan.etag } : { etagDoesNotMatch: "*" },
    httpMetadata: { contentType: "application/json" },
  });
  if (!saved) throw new Error("The plan changed during this save. Refresh and try again.");
  return records;
}
