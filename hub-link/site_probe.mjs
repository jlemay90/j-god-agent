/**
 * Draft, READ-ONLY Zeus -> Hub probe for a verified private ChatGPT Sites worker.
 * This file is intentionally NOT routed into the existing live Site.
 * Port it only after inspecting the actual deployed worker source.
 *
 * Sites SIWC bypass authenticates the call at the platform gate but does NOT
 * supply a visitor identity. This handler requires an independent scoped
 * server-side credential stored in Sites Secrets.
 */

const PROBE_PATH = "/api/zeus-link/probe";
const MARKER = /^ZEUS-HUB-LINK-[0-9]{8}-[A-Z0-9]{4,16}$/;

function respond(value, status) {
  return new Response(JSON.stringify(value), { status, headers: {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "private, no-store",
    "x-content-type-options": "nosniff",
  }});
}

function safeEqual(left, right) {
  const a = new TextEncoder().encode(left);
  const b = new TextEncoder().encode(right);
  let mismatch = a.length ^ b.length;
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    mismatch |= (a[i] ?? 0) ^ (b[i] ?? 0);
  }
  return mismatch === 0;
}

/**
 * dependencies: { storage, readObject, readItems, pulseKey, clock? }.
 * Explicit injection avoids copying/replacing the current Hub's storage
 * and prevents accidental use of historical snapshots.
 */
export async function readOnlyHubProbe(request, env, dependencies) {
  const url = new URL(request.url);
  if (url.pathname !== PROBE_PATH) return respond({ ok: false, error: "Not found." }, 404);
  if (request.method !== "GET") return respond({ ok: false, error: "Read-only GET required." }, 405);
  if (env?.HUB_ZEUS_LINK_READ_ENABLED !== "true" ||
      typeof env.HUB_ZEUS_LINK_SECRET !== "string" ||
      env.HUB_ZEUS_LINK_SECRET.length < 32) {
    return respond({ ok: false, status: "BLOCKED", error: "Hub link not configured." }, 503);
  }

  // SIWC bypass is checked by Sites before this handler; it is NOT authority
  // to read data. Require an independent Hub-route-only secret as well.
  const auth = request.headers.get("authorization") ?? "";
  const prefix = "Bearer ";
  if (!auth.startsWith(prefix) || !safeEqual(auth.slice(prefix.length), env.HUB_ZEUS_LINK_SECRET)) {
    return respond({ ok: false, error: "Unauthorized." }, 403);
  }

  const marker = url.searchParams.get("marker");
  if (url.searchParams.size !== 1 || !marker || !MARKER.test(marker)) {
    return respond({ ok: false, error: "Invalid probe marker." }, 400);
  }
  if (!dependencies || typeof dependencies.readObject !== "function" ||
      typeof dependencies.readItems !== "function" || !dependencies.storage ||
      typeof dependencies.pulseKey !== "string") {
    return respond({ ok: false, status: "BLOCKED", error: "Missing trusted Hub storage binding." }, 503);
  }

  try {
    const [pulse, items] = await Promise.all([
      dependencies.readObject(dependencies.storage, dependencies.pulseKey),
      dependencies.readItems(dependencies.storage),
    ]);
    if (!Array.isArray(items)) throw new Error("items absent");
    // Return only non-sensitive freshness metadata and a yes/no marker check.
    return respond({
      ok: true,
      source: "authenticated_live_hub_storage",
      scope: "read_only_probe_v1",
      checkedAt: (dependencies.clock?.() ?? new Date()).toISOString(),
      pulseDate: typeof pulse?.date === "string" ? pulse.date.slice(0, 10) : null,
      itemCount: items.length,
      markerFound: items.some(item => typeof item?.text === "string" && item.text.includes(marker)),
    }, 200);
  } catch {
    return respond({ ok: false, status: "BLOCKED", error: "Live Hub storage read unavailable." }, 503);
  }
}
