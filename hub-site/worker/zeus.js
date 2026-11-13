const ZEUS_PANELS = new Set(['today', 'inbox', 'build']);
const ZEUS_PREFIX = PREFIX + 'zeus/';
function zeusConfigured(env) { return !!(env.ZEUS_BRIDGE_URL && env.ZEUS_BRIDGE_SECRET?.length >= 32); }
async function zeusConversations(storage, owner) {
  if (!owner) return [];
  const ownerKey = await zeusDigest(owner);
  const threads = await Promise.all([...ZEUS_PANELS].map(async panel => {
    const turns = await readObject(storage, ZEUS_PREFIX + 'threads/' + ownerKey + '/' + panel + '.json') ?? [];
    return turns.slice(-3).map(turn => ({ panel, ...turn }));
  }));
  return threads.flat().sort((a, b) => b.createdAt.localeCompare(a.createdAt)).slice(0, 6);
}
async function askZeusFromMcp(request, env, args) {
  const owner = request.headers.get('oai-authenticated-user-id');
  if (!owner) throw new Error('Sign in to your private Hub.');
  const origin = new URL(request.url).origin;
  const response = await zeusApi(new Request(origin + '/api/zeus/chat', {
    method: 'POST',
    headers: { 'oai-authenticated-user-id': owner, origin, 'content-type': 'application/json' },
    body: JSON.stringify({ panel: args.panel ?? 'today', requestId: args.requestId, message: args.message }),
  }), env, '/api/zeus/chat');
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error ?? 'Zeus request failed.');
  return { ...result, source: 'Authenticated Zeus bridge', changesApplied: false };
}
function zeusSafeMessage(text) { return !/AIza[\w-]{20,}|\b\d{6,}:[\w-]{20,}|\bsk-[\w-]{16,}/.test(text); }
function zeusContext(state, panel) {
  const base = { schema: 1, section: panel, capturedAt: new Date().toISOString(), today: state.today };
  if (panel === 'today') return { ...base, chosenMove: state.checkins.find(x => x.date === state.today) ?? null, now: state.items.filter(x => !x.done && x.queue === 'Now').slice(0, 3), brief: state.pulse ? { date: state.pulse.date, stale: state.pulse.date !== state.today, summary: state.pulse.summary, nextAction: state.pulse.nextAction } : null };
  if (panel === 'inbox') return { ...base, items: state.items.filter(x => !x.done).slice(0, 30), truncated: state.items.filter(x => !x.done).length > 30 };
  return { ...base, goal: state.goal, project: state.projectMemory };
}
async function zeusDigest(value) { return [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)))].map(x => x.toString(16).padStart(2, '0')).join(''); }
async function zeusSignature(secret, timestamp, body) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return [...new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(timestamp + '.' + body)))].map(x => x.toString(16).padStart(2, '0')).join('');
}
function zeusProposal(value, message, panel) {
  const permitted = { today: 'save_move', inbox: 'add_item', build: 'add_build_idea' };
  if (!value || value.kind === 'none') return null;
  if (value.kind !== permitted[panel] || typeof value.evidence !== 'string' || !value.evidence.trim() || !message.includes(value.evidence)) throw new Error('Zeus returned an unsupported change. Nothing was changed.');
  return { kind: value.kind, value: cleanText(value.value, 500, 'Suggested change'), tinyStart: cleanText(value.tinyStart ?? '', 300, 'Small start', false), evidence: value.evidence };
}
async function zeusCall(env, envelope) {
  let stage = 'configuration';
  try {
  const url = new URL(env.ZEUS_BRIDGE_URL);
  if (url.protocol !== 'https:' || url.username || url.password || !/\.(replit\.dev|replit\.app)$/.test(url.hostname) || url.pathname !== '/hub/chat' || url.search || url.hash) throw new Error('Zeus connection needs a valid server configuration.');
  const body = JSON.stringify(envelope), timestamp = String(Math.floor(Date.now() / 1000));
  stage = 'signing';
  const signature = await zeusSignature(env.ZEUS_BRIDGE_SECRET, timestamp, body);
  stage = 'transport';
  const response = await fetch(url.href, { method: 'POST', redirect: 'manual', signal: AbortSignal.timeout(90000), headers: { 'content-type': 'application/json', 'x-zeus-timestamp': timestamp, 'x-zeus-signature': signature }, body });
  if (response.status >= 300 && response.status < 400) {
    const destination = new URL(response.headers.get('location') || '/', url);
    console.error('zeus_bridge_redirect', JSON.stringify({ status: response.status, origin: destination.origin, path: destination.pathname }));
    throw new Error('Zeus server redirected the request. Nothing was forwarded to another destination.');
  }
  if (response.status === 409) throw new Error('Zeus could not finish the previous attempt. Edit your message to start a new request.');
  if (!response.ok) throw new Error(response.status === 429 ? 'Zeus reached its usage limit. Your message is still here.' : 'Zeus is unavailable. Your message is still here; retry this same request.');
  stage = 'response';
  const data = await response.json();
  if (!data.ok || data.requestId !== envelope.requestId || typeof data.reply !== 'string') throw new Error('Zeus returned an invalid response. Nothing was changed.');
  return { reply: cleanText(data.reply, 4000, 'Zeus reply'), proposal: zeusProposal(data.proposal, envelope.message, envelope.panel), model: String(data.model ?? 'Gemini').slice(0, 80), ruleRevision: data.ruleRevision ?? null };
  } catch (cause) {
    console.error('zeus_bridge_failure', JSON.stringify({ stage, kind: cause.name }));
    if (cause.message?.startsWith('Zeus')) throw cause;
    throw new Error('Zeus connection failed at ' + stage + '. Your message is still here.');
  }
}
async function zeusApi(request, env, path) {
  const owner = request.headers.get('oai-authenticated-user-id');
  if (!owner) return error('Sign in to your private Hub.', 401);
  const storage = bucket(env), url = new URL(request.url), ownerKey = await zeusDigest(owner);
  if (path === '/api/zeus/status' && request.method === 'GET') return json({ ok: true, configured: zeusConfigured(env), scope: 'Three separate Hub conversations. No Telegram transcript is supplied.' });
  if (path === '/api/zeus/history' && request.method === 'GET') {
    const panel = url.searchParams.get('panel');
    if (!ZEUS_PANELS.has(panel)) return error('Choose a supported Zeus section.');
    return json({ ok: true, turns: await readObject(storage, ZEUS_PREFIX + 'threads/' + ownerKey + '/' + panel + '.json') ?? [] });
  }
  if (!['/api/zeus/chat', '/api/zeus/apply'].includes(path) || request.method !== 'POST') return error('Not found.', 404);
  if (request.headers.get('origin') !== url.origin) return error('This action must come from the Hub.', 403);
  if (!request.headers.get('content-type')?.startsWith('application/json')) return error('Use JSON.', 415);
  const raw = await request.text(); if (raw.length > 6000) return error('Message is too large.', 413);
  let input; try { input = JSON.parse(raw); } catch { return error('Invalid JSON.'); }
  if (!ZEUS_PANELS.has(input.panel) || !validId(input.requestId)) return error('Choose a supported section and request ID.');
  const key = ZEUS_PREFIX + 'requests/' + ownerKey + '/' + input.requestId + '.json';
  let saved = await readObject(storage, key);
  if (saved && saved.panel !== input.panel) return error('This request belongs to a different section.', 409);
  if (path === '/api/zeus/apply') {
    if (!saved?.result?.proposal) return error('No supported change is ready to apply.', 409);
    if (saved.applied) return json({ ok: true, receipt: saved.applied });
    const p = saved.result.proposal; let receipt;
    if (p.kind === 'save_move') {
      const old = await readObject(storage, CHECKINS_PREFIX + saved.envelope.context.today + '.json');
      if (saved.envelope.context.today !== localDate() || (old?.updatedAt ?? null) !== (saved.envelope.context.chosenMove?.updatedAt ?? null)) return error('Your plan changed. Ask Zeus again using the current move.', 409);
      receipt = await saveCheckin(storage, { date: localDate(), nextAction: p.value, tinyStart: p.tinyStart });
    } else {
      const hash = await zeusDigest(ownerKey + ':' + input.requestId + ':zeus-item');
      const id = hash.slice(0, 8) + '-' + hash.slice(8, 12) + '-4' + hash.slice(13, 16) + '-a' + hash.slice(17, 20) + '-' + hash.slice(20, 32);
      receipt = await readObject(storage, ITEMS_PREFIX + id + '.json');
      if (!receipt) { receipt = { id, text: p.value, type: p.kind === 'add_build_idea' ? 'Idea' : 'Task', queue: 'Inbox', done: false, source: 'Zeus ' + input.panel + ' conversation · ' + new Date().toISOString(), createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }; await writeObject(storage, ITEMS_PREFIX + id + '.json', receipt); }
    }
    saved.applied = receipt; await writeObject(storage, key, saved);
    return json({ ok: true, receipt });
  }
  if (!zeusConfigured(env)) return error('Zeus chat is built but the private server connection has not been activated.', 503);
  let message; try { message = cleanText(input.message, 2000, 'Message'); } catch (cause) { return error(cause.message); }
  if (!zeusSafeMessage(message)) return error('That looks like a credential. Keep keys out of chat.');
  if (saved && saved.message !== message) return error('Use a new request ID for a different message.', 409);
  if (saved?.result) return json({ ok: true, requestId: input.requestId, ...saved.result, applied: !!saved.applied });
  const threadKey = ZEUS_PREFIX + 'threads/' + ownerKey + '/' + input.panel + '.json';
  const thread = await readObject(storage, threadKey) ?? [];
  if (!saved) {
    const context = zeusContext(await readState(storage), input.panel);
    const envelope = { requestId: input.requestId, panel: input.panel, message, context, history: thread.slice(-4).flatMap(t => [{ role: 'user', text: t.message }, { role: 'assistant', text: t.reply }]) };
    if (new TextEncoder().encode(JSON.stringify(envelope)).length > 28000) return error('This section contains too much context. Shorten the project record first.', 413);
    saved = { panel: input.panel, message, envelope, createdAt: new Date().toISOString() }; await writeObject(storage, key, saved);
  }
  try {
    saved.result = await zeusCall(env, saved.envelope); await writeObject(storage, key, saved);
    const latest = await readObject(storage, threadKey) ?? [];
    if (!latest.some(t => t.requestId === input.requestId)) await writeObject(storage, threadKey, [...latest, { requestId: input.requestId, message, ...saved.result, createdAt: saved.createdAt }].slice(-20));
    return json({ ok: true, requestId: input.requestId, ...saved.result });
  } catch (cause) { return error(cause.message?.startsWith('Zeus') ? cause.message : 'Zeus connection failed. Your message is still here; retry this same request.', 503); }
}
