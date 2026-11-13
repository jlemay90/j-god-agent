const zeusPanelInfo = {
  today: { title: 'Talk to Zeus about this move', scope: 'Uses your saved move, Now items, and the latest brief with its date.', hint: 'Help me make this move smaller…' },
  inbox: { title: 'Talk to Zeus about your Inbox', scope: 'Uses up to 30 open Hub items. This conversation stays in Inbox.', hint: 'Add a task to… or help me sort this thought…' },
  build: { title: 'Talk to Zeus about the Hub build', scope: 'Uses the saved build goal and project record. This conversation stays with the build.', hint: 'What should we build next, and why?' },
};
const zeusDrafts = new Map();
let zeusReady = false;
async function zeusRequest(path, input) {
  const response = await fetch(path, input ? { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(input), cache: 'no-store' } : { cache: 'no-store' });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || 'Zeus could not respond. Your message is still here.');
  return data;
}
function zeusTurn(panel, box, turn) {
  const exchange = make('div', undefined, 'zeus-exchange');
  exchange.append(make('strong', 'You'), make('p', turn.message), make('strong', 'Zeus'), make('p', turn.reply));
  if (turn.proposal) {
    const proposal = make('div', undefined, 'zeus-proposal');
    proposal.append(make('small', 'Suggested change · nothing applied yet'), make('p', turn.proposal.value));
    if (turn.proposal.tinyStart) proposal.append(make('p', 'Begin: ' + turn.proposal.tinyStart));
    const apply = make('button', turn.applied ? '✓ Saved to Hub' : ({ save_move: 'Save as my move', add_item: 'Add task to Inbox', add_build_idea: 'Save build idea' })[turn.proposal.kind], 'secondary small');
    apply.type = 'button'; apply.disabled = !!turn.applied;
    apply.onclick = () => busy(apply, async () => {
      await zeusRequest('/api/zeus/apply', { panel, requestId: turn.requestId });
      turn.applied = true; apply.textContent = '✓ Saved to Hub';
      proposal.querySelector('small').textContent = 'Saved · Hub returned a receipt';
      await load(); toast('Saved to your shared Hub.');
    }).then(() => { if (turn.applied) apply.disabled = true; });
    proposal.append(apply); exchange.append(proposal);
  }
  box.append(exchange); box.scrollTop = box.scrollHeight;
}
function mountZeus(panel, target, after = false) {
  const info = zeusPanelInfo[panel], card = make('section', undefined, 'card zeus-card');
  const details = make('div'), heading = make('h2', info.title); details.append(heading);
  const scope = make('p', info.scope, 'hint'), status = make('p', 'Checking the private Zeus connection…', 'zeus-status');
  const log = make('div', undefined, 'zeus-log'); log.setAttribute('role', 'log'); log.setAttribute('aria-label', 'Zeus ' + panel + ' conversation');
  const form = make('form'), label = make('label', 'Message Zeus · ' + (panel === 'build' ? 'Hub build' : panel));
  const input = make('textarea'); input.rows = 2; input.maxLength = 2000; input.placeholder = info.hint; input.required = true; label.append(input);
  input.id = 'zeus-message-' + panel;
  const send = make('button', 'Ask Zeus', 'primary small'); send.type = 'submit'; send.disabled = true;
  const voice = make('button', '🎙 Speak', 'secondary voice-button'); voice.type = 'button'; voice.setAttribute('aria-label', 'Dictate a message to Zeus');
  const voiceHelp = make('p', 'Speak fills the box; you review and send. Your browser may process speech online. On Samsung, keyboard dictation also works in this box.', 'hint'); voiceHelp.setAttribute('role', 'status');
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null, listening = false;
  voice.onclick = () => {
    if (listening) { recognition.stop(); return; }
    if (!Recognition) { input.focus(); voiceHelp.textContent = 'Use the microphone on Samsung Keyboard or Gboard. If it is hidden, open the keyboard toolbar. You can also open this Hub in Chrome and try Speak again.'; return; }
    recognition = new Recognition(); recognition.lang = navigator.language || 'en-US'; recognition.continuous = false; recognition.interimResults = true;
    const previous = input.value.trim(); let failed = false;
    recognition.onstart = () => { listening = true; voice.textContent = '■ Stop listening'; voice.setAttribute('aria-pressed', 'true'); send.disabled = true; voiceHelp.textContent = 'Listening… Speak your message. Nothing is sent automatically.'; };
    recognition.onresult = event => {
      let speech = ''; for (let i = 0; i < event.results.length; i++) speech += event.results[i][0].transcript + ' ';
      input.value = (previous + (previous ? ' ' : '') + speech.trim()).slice(0, 2000);
    };
    recognition.onerror = event => { failed = true; voiceHelp.textContent = event.error === 'not-allowed' || event.error === 'service-not-allowed' ? 'Microphone access was blocked. Allow microphone access in your browser site settings, or tap the microphone on Samsung Keyboard / Gboard.' : event.error === 'no-speech' ? 'No speech heard. Tap Speak to try again, or use your keyboard microphone.' : 'Voice recognition is unavailable right now. Your text is kept. Try Chrome or your keyboard microphone.'; };
    recognition.onend = () => { listening = false; voice.textContent = '🎙 Speak'; voice.setAttribute('aria-pressed','false'); send.disabled = !zeusReady; if (!failed) voiceHelp.textContent = 'Review your words, then tap Ask Zeus. You can edit anything first.'; };
    try { recognition.start(); } catch { voiceHelp.textContent = 'Could not start the microphone. Try your keyboard microphone instead.'; }
  };
  document.addEventListener('visibilitychange', () => { if (document.hidden && listening) recognition.stop(); });
  const notice = make('p', 'Replies are saved in this private Hub conversation. Zeus may recall shared memories, but full Telegram history is not shown here. Suggested changes need your click to apply.', 'hint');
  const composeActions = make('div', undefined, 'voice-actions'); composeActions.append(voice, send);
  form.append(label, composeActions, voiceHelp); details.append(scope, status, log, form, notice); card.append(details);
  if (after) target.after(card); else target.append(card);
  const loadHistory = async () => {
    try { const data = await zeusRequest('/api/zeus/history?panel=' + panel); data.turns.forEach(turn => zeusTurn(panel, log, turn));  }
    catch (error) { status.textContent = error.message; }
  };
  void loadHistory();
  form.onsubmit = async event => {
    event.preventDefault(); if (!zeusReady || send.disabled) return;
    const message = input.value.trim(); if (!message) return;
    let draft = zeusDrafts.get(panel);
    if (!draft || draft.message !== message) { draft = { message, requestId: crypto.randomUUID() }; zeusDrafts.set(panel, draft); }
    send.disabled = true; input.disabled = true; status.textContent = 'Zeus is reading this section…';
    try {
      const data = await zeusRequest('/api/zeus/chat', { ...draft, panel });
      zeusTurn(panel, log, { ...data, message }); input.value = ''; zeusDrafts.delete(panel);
      status.textContent = 'Reply received · ' + data.model + ' · separate ' + panel + ' conversation';
    } catch (error) { status.textContent = error.message; }
    finally { send.disabled = !zeusReady; input.disabled = false; input.focus(); }
  };
  return { send, status };
}
const zeusCards = [
  mountZeus('today', document.querySelector('#homeZeus')),
  mountZeus('inbox', document.querySelector('#inboxZeus')),
  mountZeus('build', document.querySelector('.progress-rail'), true),
];
zeusRequest('/api/zeus/status').then(data => {
  zeusReady = data.configured;
  $('pocketBrainStatus').textContent = zeusReady ? 'Private bridge configured · reply availability is checked when you send.' : 'Private bridge not configured.';
  zeusCards.forEach(({ send, status }) => { send.disabled = !zeusReady; status.textContent = zeusReady ? 'Private connection configured · sends use the existing Zeus model budget.' : 'Chat panels are ready. Private Zeus connection awaits activation.'; });
}).catch(error => zeusCards.forEach(({ status }) => { status.textContent = error.message; }));
