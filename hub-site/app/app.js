const $ = (id) => document.getElementById(id);
const make = (tag, text, className) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (className) el.className = className; return el; };
const readLocal = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
const writeLocal = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch {} };
const centralDate = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Chicago', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const datePlus = (date, days) => { const d = new Date(date + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + days); return d.toISOString().slice(0, 10); };
const dateLabel = (date) => new Date(date + 'T12:00:00Z').toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
const queueNames = { Inbox: 'New captures', Now: 'My focus', Next: 'Up next', Waiting: 'Waiting on something', Verify: 'Needs checking', Backlog: 'For later' };
const queueHelp = { Inbox: 'Saved here, ready to review.', Now: 'The few things you are actively focusing on.', Next: 'Ready to pick up after your current focus.', Waiting: 'Progress depends on a person, event, or something outside your control.', Verify: 'Confirm a fact or missing detail before acting.', Backlog: 'Keep this without making it a current commitment.' };
const dirty = new Set();
let shared = { items: [], focus: ['', '', ''], pulse: null, goal: null, checkins: [], today: centralDate() };
let connected = false, loadedAt = null, toastTimer;
const projectGoal = {
  title: 'Make the Hub simpler and more useful in daily life.',
  why: 'Reduce friction, preserve important context, and make it easier to follow through.',
  measure: 'A dependable daily loop: capture, choose, act, and review without hunting.',
  nextStep: 'Use one existing feature for a real task and note any friction.',
  cue: 'After opening the Hub, choose one useful action.',
  obstacle: 'Adding features before validating the simplest useful workflow.',
  response: 'Try the existing workflow first and record what gets in the way.',
  service: 'Make everyday planning and follow-through easier.',
};
const milestoneLabels = [
  'Week 1 · One dependable daily loop: capture → choose → act → reflect; shared data and morning sync verified.',
  'Week 2 · Real use: log 7 separate action days and identify the 3 most frequent sources of friction.',
  'Week 3 · Remove repeated work: verify the most useful follow-up, memory, and assistant handoff loops.',
  'Week 4 · Finish a useful version: fix the observed friction, verify mobile use and recovery, and keep a short operating guide.',
];
const prompts = [
  'What would make this system worth opening tomorrow?', 'Make one real task easier before adding a new feature.',
  'Choose the smallest action that leaves evidence.', 'What are you avoiding because one detail is missing?',
  'Prepare tomorrow’s starting point before you stop.', 'Notice something good that did not need to be earned.',
  'Review the week: keep one thing, simplify one thing.', 'Use the Hub before changing the Hub.',
  'Which decision could a clear default remove?', 'Who would benefit from one clear follow-up today?',
  'Capture the distraction, then return to the chosen move.', 'Turn an obstacle into an if–then plan.',
  'What can be finished well enough and released?', 'Choose a useful pace you could repeat next week.',
  'Look at actual progress, not only what remains.', 'Which repeated step deserves a shortcut?',
  'Ask for the missing information instead of guessing.', 'Give one responsibility a clear next action.',
  'Leave room for a conversation you want to be present for.', 'Is the system helping you act, or asking for more upkeep?',
  'Review what helped on the harder days.', 'Remove a choice that rarely changes the outcome.',
  'Test the simplest complete path on your phone.', 'Check that your record can travel to another chat.',
  'Choose one rough edge to fix from real feedback.', 'Write a short guide your future self can use.',
  'Celebrate an action, a lesson, and an ordinary good moment.', 'Test recovery: can you return after time away?',
  'Choose what “finished for now” means from evidence.', 'Review the experiment and choose what is worth keeping.',
];
function toast(message) { $('toast').textContent = message; $('toast').classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').classList.remove('show'), 3500); }
function showTab(name, focus = false) {
  document.querySelectorAll('[data-page]').forEach(el => el.hidden = el.dataset.page !== name);
  const activeTab = name === 'planning' ? 'goals' : name === 'goal' || name === 'resources' || name === 'mobile' ? '' : name;
  document.querySelectorAll('[data-tab]').forEach(el => { if (el.dataset.tab === activeTab) el.setAttribute('aria-current', 'page'); else el.removeAttribute('aria-current'); });
  history.replaceState(null, '', '#' + name);
  window.scrollTo({ top: 0, behavior: 'instant' });
  if (focus) { const h = document.querySelector(`[data-page="${name}"] h1`); h.tabIndex = -1; h.focus({ preventScroll: true }); }
}
document.querySelectorAll('[data-tab]').forEach(el => el.onclick = () => {
  if (el.dataset.tab === 'inbox' && $('itemSearch').dataset.itemId) {
    delete $('itemSearch').dataset.itemId;
    renderItems();
  }
  showTab(el.dataset.tab, true);
  if (el.dataset.tab === 'inbox') $('captureText').focus({ preventScroll: true });
});
document.querySelectorAll('[data-go]').forEach(el => el.onclick = () => {
  showTab(el.dataset.go, true);
  if (el.dataset.go === 'inbox') $('captureText').focus({ preventScroll: true });
});
document.querySelectorAll('[data-home-go]').forEach(el => el.onclick = () => {
  const destination = el.dataset.homeGo;
  if (destination === 'christmas' || destination === 'ideas') {
    showTab('ideas', true);
    document.querySelector(`[data-ideas-filter="${destination}"]`).click();
    return;
  }
  showTab(destination, true);
});
document.querySelector('.brand').onclick = (event) => { event.preventDefault(); showTab('today'); };
document.querySelectorAll('form').forEach(form => form.addEventListener('input', () => dirty.add(form.id)));
async function request(action) {
  if (!connected) throw new Error('The shared Hub is not connected. Refresh before saving.');
  const response = await fetch('/api/action', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(action), cache: 'no-store' });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || 'The Hub could not save. Your text is still here.');
  return data.result;
}
async function busy(button, action) { button.disabled = true; try { await action(); } catch (error) { toast(error.message); } finally { button.disabled = false; } }
async function load() {
  try {
    const response = await fetch('/api/state', { cache: 'no-store' }), data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Shared record unavailable');
    shared = { ...shared, ...data.state }; connected = true; loadedAt = new Date();
    $('statusDot').classList.add('live'); $('connectionText').textContent = 'Private shared Hub · refreshed ' + loadedAt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }); render();
  } catch (error) {
    connected = false; $('statusDot').classList.remove('live'); $('connectionText').textContent = 'Shared Hub unavailable · ' + error.message;
    if (!loadedAt) { $('nextMove').textContent = 'Reconnect to load your saved plan.'; $('pulseHeadline').textContent = 'The brief could not load.'; }
  }
}
const todayRecord = () => shared.checkins.find(day => day.date === shared.today) ?? {};
const goalDays = () => shared.goal ? Math.max(0, Math.floor((new Date(shared.today + 'T12:00Z') - new Date(shared.goal.startDate + 'T12:00Z')) / 86400000)) : 0;
function suggestedMove() {
  const day = todayRecord();
  if (!day.nextAction && day.moveStatus) return { action: '', tiny: '', source: day.moveStatus };
  if (day.nextAction) return { action: day.nextAction, tiny: day.tinyStart || '', source: 'Your saved move', savedDate: day.date };
  const pulse = shared.pulse;
  if (pulse?.date === shared.today) return { action: pulse.nextAction || shared.focus.find(Boolean) || pulse.top3?.[0] || '', tiny: pulse.tinyStart || '', source: 'Morning suggestion' };
  return { action: 'Confirm what still needs attention before choosing today’s move.', tiny: 'Open your saved priorities and confirm one unfinished obligation.', source: 'Fresh context needed', needsRefresh: true };

}
function itemForAction(action) {
  return shared.items.find(item => !item.done && item.text.trim().toLowerCase() === (action || '').trim().toLowerCase());
}
function render() {
  const day = todayRecord(), move = suggestedMove();
  document.querySelectorAll('[data-resolve-move]').forEach(button => button.disabled = !move.action || !!move.needsRefresh);
  $('moveActionStatus').textContent = day.moveStatus || '';
  $('nextMove').textContent = move.action || 'Choose one useful action. It can be small.'; $('moveSource').textContent = move.source;
  $('goalConnection').textContent = shared.pulse?.date === shared.today ? shared.pulse.goalConnection || '' : '';
  if (!dirty.has('planForm')) { $('planAction').value = move.action; $('tinyStart').value = day.tinyStart || move.tiny; }
  if (!dirty.has('checkinForm')) {
    ['win', 'friction', 'tomorrow', 'presentMoment'].forEach(key => $(key).value = day[key] || ''); $('goalActionDone').checked = !!day.goalActionDone;
  }
  if (day.energy && !session) $('energy').value = day.energy;
  $('checkinStatus').textContent = day.evening ? 'Reflection saved to your shared record.' : 'Only what you report is counted as progress.';
  $('morningCheck').classList.toggle('checked', !!day.morning); $('morningCheck').textContent = day.morning ? '✓ Goal reviewed today' : '☀ Read my goal';
  $('middayCheck').classList.toggle('checked', !!day.midday); $('middayCheck').textContent = day.midday ? '✓ A moment taken today' : '◌ Take a present moment';
  $('practicePrompt').textContent = prompts[Math.min(goalDays(), 29)];
  renderChoices(); renderPulse(); renderGoal(); renderItems(); renderQueueOverview(); renderInsights(); renderLegacy(); renderTimer(); renderCommandStation(); renderResources();
  renderMemory();
  renderPlanning(); renderIdeas(); renderGoalAndProjectViews(); renderHomeRecords();
  if ($('pocketMove')) renderPocket();
  if (!dirty.has('focusForm')) [0, 1, 2].forEach(index => $('focus' + index).value = shared.focus[index] || '');
}
function renderIdeas() {
  const ideas = shared.items.filter(item => item.type === 'Idea');
  const christmas = shared.items.filter(item => /^\s*#Christmas\b/.test(item.text || ''));
  const paint = (target, records) => {
    target.replaceChildren();
    for (const item of records) {
      const card = make('article', undefined, 'simple-record');
      const meta = make('div', undefined, 'simple-record-meta');
      meta.append(make('span', item.type || 'Note', 'eyebrow'), make('span', queueNames[item.queue] || item.queue || 'Saved', 'badge'));
      const footer = make('div', undefined, 'simple-record-footer');
      footer.append(make('span', item.updatedAt ? 'Updated ' + dateLabel(item.updatedAt.slice(0, 10)) : 'Saved in the shared Hub', 'hint'));
      const open = make('button', 'Open original →', 'text-link');
      open.type = 'button';
      open.onclick = () => openHubItem(item);
      footer.append(open);
      card.append(meta, make('p', item.text, 'simple-record-text'), footer);
      target.append(card);
    }
  };
  paint($('ideaList'), ideas);
  paint($('christmasList'), christmas);
  $('ideaEmpty').hidden = ideas.length > 0;
  $('christmasEmpty').hidden = christmas.length > 0;
}
function openHubItem(item) {
  $('itemSearch').value = '';
  $('itemSearch').dataset.itemId = item.id;
  $('queueFilter').value = '';
  showTab('inbox', true);
  if (item.done) $('completedLabel').closest('details').open = true;
  renderItems();
  const row = $('hub-item-' + item.id);
  if (row) { row.tabIndex = -1; row.focus(); row.scrollIntoView({ block: 'center' }); }
}
function renderHomeRecords() {
  const query = $('homeSearch').value.trim().toLowerCase();
  const matches = query ? shared.items.filter(item => `${item.text || ''} ${item.type || ''}`.toLowerCase().includes(query)).slice(0, 6) : [];
  const results = $('homeSearchResults');
  results.replaceChildren();
  results.hidden = !query;
  if (query && !matches.length) results.append(make('p', 'No saved records match that.', 'home-search-empty'));
  for (const item of matches) {
    const button = make('button', undefined, 'home-search-result');
    button.type = 'button'; button.setAttribute('role', 'option');
    button.append(make('span', item.text, 'home-search-result-text'), make('small', item.type || 'Note'));
    button.onclick = () => openHubItem(item);
    results.append(button);
  }
  const recent = [...shared.items].sort((a, b) => {
    const aDate = Date.parse(a.updatedAt || a.createdAt || '') || 0;
    const bDate = Date.parse(b.updatedAt || b.createdAt || '') || 0;
    return bDate - aDate;
  }).slice(0, 4);
  const box = $('homeRecentList'); box.replaceChildren();
  if (!recent.length) {
    box.append(make('p', 'Your saved notes and ideas will show up here.', 'home-recent-empty'));
    return;
  }
  for (const item of recent) {
    const button = make('button', undefined, 'home-recent-item');
    button.type = 'button';
    const text = (item.text || '').replace(/\s+/g, ' ').trim();
    button.append(make('span', text.length > 130 ? text.slice(0, 127) + '…' : text, 'home-recent-text'));
    button.append(make('small', `${item.type || 'Note'} · ${item.done ? 'Completed' : queueNames[item.queue] || 'Saved'}`, 'home-recent-meta'));
    button.onclick = () => openHubItem(item);
    box.append(button);
  }
}
document.querySelectorAll('[data-ideas-filter]').forEach(button => button.onclick = () => {
  const christmas = button.dataset.ideasFilter === 'christmas';
  $('ideasView').hidden = christmas;
  $('christmasView').hidden = !christmas;
  const add = document.querySelector('[data-start-capture]');
  add.dataset.startCapture = christmas ? 'christmas' : 'idea';
  add.textContent = christmas ? '＋ Add to list' : '＋ New idea';
  document.querySelectorAll('[data-ideas-filter]').forEach(option => option.setAttribute('aria-pressed', String(option === button)));
});
document.querySelectorAll('[data-capture-type]').forEach(button => button.onclick = () => {
  $('captureType').value = button.dataset.captureType;
  document.querySelectorAll('[data-capture-type]').forEach(option => option.setAttribute('aria-pressed', String(option === button)));
});
document.querySelectorAll('[data-start-capture]').forEach(button => button.onclick = () => {
  const kind = button.dataset.startCapture;
  $('captureType').value = kind === 'idea' ? 'Idea' : 'Note';
  document.querySelectorAll('[data-capture-type]').forEach(option => option.setAttribute('aria-pressed', String(option.dataset.captureType === $('captureType').value)));
  if (kind === 'christmas' && !$('captureText').value.trim()) $('captureText').value = '#Christmas ';
  showTab('inbox', true);
  $('captureText').focus();
});
function renderCommandStation() {
  const move = suggestedMove(), item = itemForAction(move.action), loose = shared.items.filter(value => !value.done && ['Waiting', 'Verify'].includes(value.queue));
  $('nowTileText').textContent = move.action || 'Choose one useful action.';
  $('looseEndText').textContent = loose.length ? `${loose.length} ${loose.length === 1 ? 'item needs' : 'items need'} something to happen or a detail checked.` : 'Nothing is marked as waiting or needing checking.';
  $('contextStart').textContent = item?.startStep || move.tiny || 'Choose a small physical beginning.';
  $('contextFinish').textContent = item?.finishCondition || 'No finish condition is saved yet.';
  const currentPulse = shared.pulse?.date === shared.today;
  const source = item?.source || (currentPulse ? 'Daily Pulse · ' + shared.pulse.date : move.savedDate ? 'Your saved plan · ' + move.savedDate : 'Shared Hub · latest brief ' + (shared.pulse?.date || 'not available'));
  $('contextSource').replaceChildren();
  appendInline($('contextSource'), source);
  if (item?.updatedAt) $('contextSource').append(make('span', ' · Record updated ' + dateLabel(item.updatedAt.slice(0, 10))));
  const missing = [];
  if (!currentPulse) missing.push('A verified brief for today. The older brief is reference only.');
  if (!item?.source && !currentPulse) missing.push('Supporting source details for this move.');
  if (!item?.finishCondition) missing.push('A confirmed finish condition.');
  if (item?.updatedAt?.slice(0, 10) < shared.today) missing.push('Whether this older record still applies today.');
  $('contextWhy').textContent = item?.whyNow || (currentPulse ? shared.pulse.goalConnection || shared.pulse.summary : move.needsRefresh ? 'The latest brief is older than today. Confirming current status prevents an old obligation from becoming today’s instruction.' : 'You chose this move today. ' + (shared.goal?.why || 'Its supporting context still needs confirmation.'));
  $('contextMissing').textContent = missing.length ? missing.join(' ') : 'No missing details are flagged in the saved record. Verify any time-sensitive facts.';
  if (move.needsRefresh) $('contextStart').textContent = move.tiny;

}
function renderChoices() {
  const box = $('moveChoices'); box.replaceChildren();
  const options = [...shared.focus.filter(Boolean), ...shared.items.filter(item => !item.done && (!item.queue || ['Now', 'Next', 'Inbox'].includes(item.queue))).map(item => item.text), ...(shared.pulse?.date === shared.today ? shared.pulse.top3 : []), shared.goal?.nextStep].filter(Boolean);
  [...new Set(options)].slice(0, 12).forEach(value => { const button = make('button', value); button.type = 'button'; button.onclick = () => { $('planAction').value = value; $('tinyStart').value = ''; dirty.add('planForm'); toast('Selected. Save your move or start a block.'); }; box.append(button); });
}
function appendInline(parent, text) {
  const pattern = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`/g; let start = 0, match;
  while ((match = pattern.exec(text))) { parent.append(document.createTextNode(text.slice(start, match.index))); const el = make(match[2] ? 'a' : match[3] ? 'strong' : 'code', match[1] || match[3] || match[4]); if (match[2]) { el.href = match[2]; el.target = '_blank'; el.rel = 'noopener noreferrer'; } parent.append(el); start = pattern.lastIndex; }
  parent.append(document.createTextNode(text.slice(start)));
}
function renderMarkdown(box, value) {
  box.replaceChildren(); let list = null;
  value.split(/\r?\n/).forEach(line => { const text = line.trim(); if (!text) { list = null; return; } if (/^[-*_]{3,}$/.test(text)) { box.append(make('hr')); list = null; return; } const heading = text.match(/^#{1,6}\s+(.+)/), item = text.match(/^([-*]|\d+\.)\s+(.+)/); let el;
    if (heading) { el = make('h4'); appendInline(el, heading[1]); list = null; } else if (item) { const tag = /^\d/.test(item[1]) ? 'ol' : 'ul'; if (!list || list.tagName.toLowerCase() !== tag) { list = make(tag); box.append(list); } el = make('li'); appendInline(el, item[2]); list.append(el); return; } else { el = make('p'); appendInline(el, text); list = null; } box.append(el);
  });
}
function renderPulse() {
  const pulse = shared.pulse; $('pulseTop3').replaceChildren();
  const current = pulse?.date === shared.today;
  $('pulseDate').textContent = pulse ? (current ? 'Today' : 'Earlier · ' + dateLabel(pulse.date)) : 'No brief yet';
  $('pulseDate').classList.toggle('stale', !!pulse && !current);
  $('pulseHeadline').textContent = pulse?.headline || 'Your next published brief will appear here.'; $('pulseSummary').textContent = pulse?.summary || '';
  (pulse?.top3 || []).forEach(text => $('pulseTop3').append(make('li', text)));
  $('pulseDetails').hidden = !pulse?.summary && !pulse?.fullText;
  $('fullPulse').hidden = !pulse?.fullText; renderMarkdown($('pulseFullText'), pulse?.fullText || '');
  $('pulseFreshness').textContent = pulse ? (pulse.date === shared.today ? 'Today’s published brief. Connected sources are checked by the morning task.' : 'This is an earlier brief from ' + dateLabel(pulse.date) + '. Verify time-sensitive details before acting.') : 'The existing morning task publishes the brief. Refresh to load its latest result.';
}
const goalFields = { title: 'Title', why: 'Why', measure: 'Measure', nextStep: 'NextStep', cue: 'Cue', obstacle: 'Obstacle', response: 'Response', service: 'Service' };
function renderGoal() {
  const goal = shared.goal, elapsed = goalDays(), all = shared.checkins, recent = all.filter(day => day.date >= datePlus(shared.today, -6) && day.date <= shared.today);
  $('goalTitle').textContent = goal?.title || 'Choose your 30-day direction.'; $('goalWhy').textContent = goal?.why || 'Your project goal is ready to make your own.';
  $('goalDay').textContent = goal ? elapsed >= 30 ? '30-day review time' : 'Day ' + (elapsed + 1) + ' of 30' : 'Goal ready to save';
  $('deadline').textContent = goal ? 'Finish window · ' + dateLabel(goal.deadline) : '30 days from your start';
  const logged = goal ? all.filter(day => day.goalActionDone && day.date >= goal.startDate && day.date < goal.deadline).length : 0;
  $('goalMeter').style.width = Math.min(100, logged / 30 * 100) + '%'; $('goalCount').textContent = logged + (logged === 1 ? ' day' : ' days') + ' with a reported goal action. This measures showing up, not project completion.';
  if (!dirty.has('goalForm')) Object.entries(goalFields).forEach(([key, suffix]) => $('goalEdit' + suffix).value = goal?.[key] ?? projectGoal[key]);
  const box = $('milestones'); box.replaceChildren(); const milestones = goal?.milestones || [];
  $('milestoneCount').textContent = milestones.filter(item => item.done).length + ' / ' + milestones.length;
  if (!goal) box.append(make('p', 'Save the goal card to begin the four-week working checklist.', 'hint'));
  milestones.forEach(item => { const row = make('div', undefined, 'milestone'), label = make('label'), input = make('input'); input.type = 'checkbox'; input.checked = item.done; input.onchange = () => busy(input, async () => { await request({ action: 'setMilestone', id: item.id, done: input.checked }); await load(); toast('Milestone status saved.'); }); label.append(input, make('span', item.label)); row.append(label); box.append(row); });
  $('dayGrid').replaceChildren(); for (let index = 0; index < 30; index++) { const date = goal ? datePlus(goal.startDate, index) : null, done = date && all.some(day => day.date === date && day.goalActionDone), cell = make('span', done ? '✓' : String(index + 1), 'day-cell' + (done ? ' logged' : '') + (date === shared.today ? ' current' : '')); cell.setAttribute('aria-label', date ? dateLabel(date) + (done ? ': reported goal action' : ': no goal action logged') : 'Day ' + (index + 1) + ': goal not started'); cell.title = cell.getAttribute('aria-label'); $('dayGrid').append(cell); }
  $('daysSummary').textContent = goal ? logged + ' action days recorded. A missed day stays open; your record is never reset as a penalty.' : 'The calendar begins when your goal is saved.';
  $('weekActions').textContent = recent.filter(day => day.goalActionDone).length; $('weekReflections').textContent = recent.filter(day => day.evening).length;
  const nextMilestone = milestones.find(item => !item.done), phaseLabel = nextMilestone?.label || (!goal ? milestoneLabels[0] : '30-day review · choose what is worth keeping');
  $('currentPhase').textContent = phaseLabel;
  $('nextProof').textContent = phaseLabel.includes('·') ? phaseLabel.split('·').slice(1).join('·').trim() : 'Review the experiment and name the useful version you are keeping.';
  $('phaseMeter').style.width = Math.min(100, ((elapsed + 1) / 30) * 100) + '%';
  const historyBox = $('recentCheckins'); historyBox.replaceChildren(); all.filter(day => day.win || day.friction || day.presentMoment).slice(0, 7).forEach(day => { const row = make('div', undefined, 'recent'); row.append(make('time', dateLabel(day.date))); if (day.win) row.append(make('p', 'Moved: ' + day.win)); if (day.friction) row.append(make('p', 'Friction: ' + day.friction)); if (day.presentMoment) row.append(make('p', 'A moment: ' + day.presentMoment)); historyBox.append(row); }); if (!historyBox.childNodes.length) historyBox.append(make('p', 'Your first reflection will appear here.', 'hint'));
}
function renderItems() {
  const query = $('itemSearch').value.toLowerCase(), open = shared.items.filter(item => !item.done), done = shared.items.filter(item => item.done); $('inboxCount').textContent = open.length ? '(' + open.length + ')' : ''; $('completedLabel').textContent = 'Completed moves · ' + done.length;
  for (const [id, items] of [['sharedItems', open], ['completedItems', done]]) {
    const box = $(id); box.replaceChildren();
    items.filter(item => (!$('itemSearch').dataset.itemId || item.id === $('itemSearch').dataset.itemId) && item.text.toLowerCase().includes(query) && (!$('queueFilter').value || (item.queue || 'Inbox') === $('queueFilter').value)).slice(0, 60).forEach(item => {
      const row = make('div', undefined, 'item' + (item.done ? ' done' : '')), label = make('label'), input = make('input'); input.type = 'checkbox'; input.checked = item.done;
      row.id = 'hub-item-' + item.id;
      input.onchange = () => busy(input, async () => { try { await request({ action: 'setItemDone', id: item.id, done: input.checked }); await load(); toast('Shared status saved.'); } catch (error) { input.checked = item.done; throw error; } });
      label.append(input, make('span', item.text)); row.append(label, make('p', item.type + ' · ' + dateLabel(item.createdAt.slice(0, 10)), 'item-meta'));
      const queueLabel = make('div', undefined, 'item-actions');
      queueLabel.append(make('span', queueNames[item.queue || 'Inbox'], 'badge'));
      if (!item.done) {
        const change = (value, title) => { const button = make('button', title, 'secondary small'); button.disabled = item.queue === value; button.onclick = () => busy(button, async () => { await request({action:'setItemQueue',id:item.id,queue:value}); await load(); toast('Saved: ' + queueNames[value]); }); return button; };
        queueLabel.append(change('Now','Focus'),change('Backlog','Later'));
        const more = make('details',undefined,'item-more'); more.append(make('summary','More'));
        const extras = make('div',undefined,'row'); for (const value of ['Inbox','Next','Waiting','Verify']) extras.append(change(value,queueNames[value])); more.append(extras); queueLabel.append(more);
      }
      row.append(queueLabel);
      for (const [key, title] of [['whyNow', 'Why now'], ['startStep', 'Start'], ['source', 'Source'], ['finishCondition', 'Finished when']]) if (item[key]) row.append(make('p', title + ': ' + item[key], 'item-meta'));
      if (!item.done && !['Waiting', 'Verify', 'Backlog'].includes(item.queue)) { const choose = make('button', 'Make this my next move →', 'text-link'); choose.onclick = () => { $('planAction').value = item.text; $('tinyStart').value = item.startStep || ''; dirty.add('planForm'); showTab('today'); $('planAction').focus(); }; queueLabel.querySelector('details').append(choose); }
      box.append(row);
    });
    if (!box.childNodes.length) box.append(make('p', query || $('queueFilter').value ? 'No matching moves.' : id === 'sharedItems' ? 'Nothing waiting here. Capture a thought above.' : 'Completed moves will appear here.', 'hint'));
  }
}
function renderQueueOverview() {
  const box = $('queueOverview'); box.replaceChildren();
  const more = make('details', undefined, 'filter-more'); more.append(make('summary','More filters')); const extra = make('div',undefined,'filter-extras');
  for (const queueName of ['', 'Now', 'Backlog', 'Inbox', 'Next', 'Waiting', 'Verify']) {
    const count = shared.items.filter(item => !item.done && (item.queue || 'Inbox') === queueName).length;
    const button = make('button', undefined, 'queue-chip' + ($('queueFilter').value === queueName ? ' selected' : ''));
    button.type = 'button'; button.append(make('span', queueName ? queueNames[queueName] + ' · ' + count : 'All'));
    button.onclick = () => { $('queueFilter').value = $('queueFilter').value === queueName ? '' : queueName; renderItems(); renderQueueOverview(); $('sharedItems').scrollIntoView({ behavior: 'smooth', block: 'start' }); };
    if (['','Now','Backlog'].includes(queueName)) box.append(button); else extra.append(button);
  }
  more.append(extra); more.open = ['Inbox','Next','Waiting','Verify'].includes($('queueFilter').value); box.append(more);
}
function renderLegacy() {
  const legacy = readLocal('jhub-state', {}), box = $('legacyItems'); box.replaceChildren(); const tasks = Array.isArray(legacy.tasks) ? legacy.tasks : [];
  tasks.filter(item => !(legacy.done || []).includes(item.id)).forEach(item => { const row = make('div', undefined, 'recent'); row.append(make('p', item.text)); const button = make('button', 'Copy this text to shared Hub', 'text-link'); button.onclick = () => busy(button, async () => { if (shared.items.some(value => value.text === item.text)) return toast('This text is already in the shared Hub.'); await request({ action: 'addItem', text: item.text, type: 'Task' }); await load(); toast('Copied to shared Hub. Older note preserved.'); }); row.append(button); box.append(row); }); if (!box.childNodes.length) box.append(make('p', 'No open older captures on this device.', 'hint'));
}
function renderInsights() {
  const friction = shared.checkins.find(day => day.friction), experiment = shared.pulse?.date === shared.today && shared.pulse.experiment;
  $('learningTitle').textContent = experiment ? 'A small experiment to try' : friction ? 'Start with this friction' : 'Use it. Notice. Adjust.';
  $('learningText').textContent = experiment || (friction ? friction.friction : 'Use the Hub on one real task. Record the thing that slowed you down; that becomes evidence for the next improvement.');
}
function renderResources() {
  const move = suggestedMove(), waiting = shared.items.filter(item => !item.done && item.queue === 'Waiting'), verify = shared.items.filter(item => !item.done && item.queue === 'Verify');
  $('recoveryFreshness').textContent = shared.pulse ? (shared.pulse.date === shared.today ? 'Current today' : 'Brief from ' + dateLabel(shared.pulse.date)) : 'No published brief';
  $('recoveryHeadline').textContent = shared.pulse?.headline || 'Your current shared record is ready.';
  $('recoverySummary').textContent = shared.pulse?.summary || 'No Daily Pulse has been published yet. Use your saved items and project record below for the current context.';
  $('recoveryNow').textContent = move.action || 'Choose'; $('recoveryNow').title = move.action || 'Choose a move';
  $('recoveryWaiting').textContent = waiting.length; $('recoveryVerify').textContent = verify.length; $('recoveryMemory').textContent = shared.projectMemory?.revision ?? '—';
  const looseBox = $('recoveryLooseEnds'); looseBox.replaceChildren();
  [...waiting.map(item => [queueNames.Waiting, item.text]), ...verify.map(item => [queueNames.Verify, item.text])].slice(0, 4).forEach(([queue, text]) => { const row = make('div', undefined, 'loose-end'); row.append(make('b', queue), make('span', text)); looseBox.append(row); });
  if (!looseBox.childNodes.length) looseBox.append(make('p', 'Nothing is marked as waiting or needing checking. Older briefs may still contain unresolved items.', 'hint'));
  $('systemStatusTitle').textContent = connected ? 'Shared state is connected.' : 'Shared state needs a refresh.';
  const status = $('systemStatusList'); status.replaceChildren();
  const openCount = shared.items.filter(item => !item.done).length, nowCount = shared.items.filter(item => !item.done && item.queue === 'Now').length;
  [['Daily Pulse', shared.pulse ? dateLabel(shared.pulse.date) : 'Not published'], ['Open moves', String(openCount)], ['My focus', nowCount + ' of 3'], ['30-day goal', shared.goal ? 'Day ' + (goalDays() + 1) : 'Not saved'], ['Project memory', shared.projectMemory ? 'Revision ' + shared.projectMemory.revision : 'Not saved'], ['Last refresh', loadedAt ? loadedAt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : 'Not connected']].forEach(([label, value]) => { const row = make('div', undefined, 'status-row'); row.append(make('span', label), make('b', value)); status.append(row); });
}
async function savePlan() {
  const nextAction = $('planAction').value.trim(); if (!nextAction) throw new Error('Choose one action to begin.');
  await request({ action: 'saveCheckin', date: shared.today, nextAction, moveStatus: '', tinyStart: $('tinyStart').value.trim(), energy: $('energy').value }); dirty.delete('planForm'); await load();
}
document.querySelectorAll('[data-resolve-move]').forEach(button => button.onclick = () => busy(button, async () => {
  const move = suggestedMove(); if (!move.action || move.needsRefresh) return;
  let item = itemForAction(move.action);
  if (!item) { item = await request({ action: 'addItem', text: move.action, type: 'Note' }); shared.items.unshift(item); }
  const target = button.dataset.resolveMove;
  if (target === 'done') await request({ action: 'setItemDone', id: item.id, done: true });
  else await request({ action: 'setItemQueue', id: item.id, queue: target });
  const moveStatus = target === 'done' ? 'Marked completed. Choose your next move.' : target === 'Backlog' ? 'Saved for later. Choose your next move.' : 'Moved to Up next. Choose your next move.';
  await request({ action: 'saveCheckin', date: shared.today, nextAction: '', tinyStart: '', moveStatus });
  dirty.delete('planForm'); await load(); toast(moveStatus);
}));
$('planForm').onsubmit = event => { event.preventDefault(); busy(event.submitter, async () => { await savePlan(); toast('Your next move is saved.'); }); };
document.querySelectorAll('[data-start]').forEach(button => button.onclick = () => { $('tinyStart').value = button.dataset.start; dirty.add('planForm'); });
$('goalForm').onsubmit = event => { event.preventDefault(); busy(event.submitter, async () => { const values = Object.fromEntries(Object.entries(goalFields).map(([key, suffix]) => [key, $('goalEdit' + suffix).value.trim()])); await request({ action: 'saveGoal', ...values, ...(shared.goal ? {} : { milestones: milestoneLabels }) }); dirty.delete('goalForm'); await load(); toast('Your 30-day goal is saved.'); }); };
$('checkinForm').onsubmit = event => { event.preventDefault(); busy(event.submitter, async () => { const values = Object.fromEntries(['win', 'friction', 'tomorrow', 'presentMoment'].map(key => [key, $(key).value.trim()])); await request({ action: 'saveCheckin', date: shared.today, ...values, goalActionDone: $('goalActionDone').checked, evening: true }); dirty.delete('checkinForm'); await load(); toast('Reflection saved. Keep the useful parts of today.'); }); };
$('morningCheck').onclick = () => busy($('morningCheck'), async () => { if (!shared.goal) { showTab('goal'); return toast('Save your goal first.'); } await request({ action: 'saveCheckin', date: shared.today, morning: true }); await load(); toast(shared.goal.title); });
$('middayCheck').onclick = () => { $('presenceDialog').showModal(); };
$('presenceDialog').addEventListener('close', () => { if ($('presenceDialog').returnValue === 'done') busy($('middayCheck'), async () => { await request({ action: 'saveCheckin', date: shared.today, midday: true }); await load(); }); });
$('captureForm').onsubmit = event => { event.preventDefault(); busy(event.submitter, async () => { await request({ action: 'addItem', text: $('captureText').value.trim(), type: $('captureType').value || 'Note' }); $('captureText').value = ''; $('captureType').value = 'Note'; document.querySelectorAll('[data-capture-type]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.captureType === 'Note'))); dirty.delete('captureForm'); await load(); toast('Saved. You do not need to hold it in your head.'); }); };
$('focusForm').onsubmit = event => { event.preventDefault(); busy(event.submitter, async () => { await request({ action: 'setFocus', values: [0, 1, 2].map(index => $('focus' + index).value.trim()) }); dirty.delete('focusForm'); await load(); toast('Shared notes saved.'); }); };
 $('itemSearch').oninput = () => { delete $('itemSearch').dataset.itemId; renderItems(); }; $('homeSearch').oninput = renderHomeRecords; $('refresh').onclick = () => busy($('refresh'), load);
let session = readLocal('jhub-focus-session', null);
if (session && (!Number.isFinite(session.remaining) || !Number.isFinite(session.endsAt) || typeof session.action !== 'string')) session = null;
const duration = () => ({ low: 2, steady: 5, strong: 15 }[$('energy').value] || 5);
function renderTimer() {
  $('timerPanel').hidden = !session; $('startTimer').hidden = !!session;
  if (!session) { $('startTimer').textContent = 'Start with ' + duration() + ' minutes →'; return; }
  if (session.running) session.remaining = Math.max(0, session.endsAt - Date.now());
  if (session.remaining === 0 && session.running) { session.running = false; writeLocal('jhub-focus-session', session); $('timerMessage').textContent = 'The block has ended. Notice what moved, then log it when you are ready.'; }
  const seconds = Math.ceil(session.remaining / 1000); $('timerClock').textContent = Math.floor(seconds / 60).toString().padStart(2, '0') + ':' + (seconds % 60).toString().padStart(2, '0'); $('timerAction').textContent = session.action; $('pauseTimer').textContent = session.running ? 'Pause' : session.remaining > 0 ? 'Resume' : 'Block ended'; $('pauseTimer').disabled = session.remaining === 0;
}
$('energy').onchange = () => renderTimer();
$('startTimer').onclick = () => busy($('startTimer'), async () => { await savePlan(); const remaining = duration() * 60000; session = { action: $('tinyStart').value.trim() || $('planAction').value.trim(), remaining, endsAt: Date.now() + remaining, running: true }; writeLocal('jhub-focus-session', session); $('timerMessage').textContent = ''; renderTimer(); });
$('pauseTimer').onclick = () => { if (!session) return; if (session.running) { session.remaining = Math.max(0, session.endsAt - Date.now()); session.running = false; } else { session.endsAt = Date.now() + session.remaining; session.running = true; } writeLocal('jhub-focus-session', session); renderTimer(); };
$('stopTimer').onclick = () => { session = null; writeLocal('jhub-focus-session', null); renderTimer(); $('timerMessage').textContent = 'Block ended. Nothing was marked complete. Record what moved when you are ready.'; $('win').focus(); };
setInterval(renderTimer, 1000);
function assistantPrompt(kind = 'improve') {
  const goal = shared.goal, friction = shared.checkins.find(day => day.friction), nextMilestone = goal?.milestones?.find(item => !item.done);
  return `J Command Hub · ${kind === 'build' ? 'next build request' : 'help me make this easier'}\nSite: https://j-command-hub.jlemay90.chatgpt.site/\nDate: ${shared.today} (America/Chicago)\n\nGoal: ${goal?.title || projectGoal.title}\nWhy: ${goal?.why || projectGoal.why}\nFinish line: ${goal?.measure || projectGoal.measure}\nNext milestone: ${nextMilestone?.label || 'Review the current finish checklist.'}\nSaved next move: ${todayRecord().nextAction || '(none)'}\nLatest reported friction: ${friction?.friction || '(none recorded yet)'}\nShared project summary: ${shared.projectMemory?.summary || '(read the shared project record)'}\nAccepted decisions: ${(shared.projectMemory?.decisions || []).slice(0, 12).join('; ')}\n\nRead the shared Hub state first. Help me choose one small, useful improvement that removes real friction. Keep established resources and the existing morning schedule. Separate confirmed facts, proposals, and unfinished work. Do not infer that an action happened from a timer or a check-in. If this is an implementation request and tools are available, finish the bounded change, verify it, publish through Sites, and record the result. Otherwise produce a short implementation brief with acceptance checks. Keep a compact decision and next-step record so another model can continue. Ask at most one focused question if a necessary fact is missing.`;
}
async function copyPrompt(text) { $('bridgePreview').value = text; try { await navigator.clipboard.writeText(text); toast('Copied. Paste into your assistant conversation.'); } catch { showTab('resources'); $('bridgePreview').closest('details').open = true; $('bridgePreview').focus(); $('bridgePreview').select(); toast('Copy the selected request manually.'); } }
$('copyHelp').onclick = () => copyPrompt(assistantPrompt()); $('copyBuildHelp').onclick = () => copyPrompt(assistantPrompt('build'));
$('exportData').onclick = async () => { try { await load(); if (!connected) throw new Error('Reconnect before exporting the latest record.'); const blob = new Blob([JSON.stringify({ exportedAt: new Date().toISOString(), site: location.origin, state: shared }, null, 2)], { type: 'application/json' }), url = URL.createObjectURL(blob), link = make('a'); link.href = url; link.download = 'j-command-hub-' + shared.today + '.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); } catch (error) { toast(error.message); } };
$('bridgeCopy').onclick = () => { const mode = $('bridgeMode').value, requests = { build: 'Implement one bounded improvement and verify it.', decide: 'Help me compare the realistic options, choose a next step, and name the tradeoff.', unstuck: 'Help me identify the actual blocker and one small action I can take.', remember: 'Record my stated decision as a dated shared Note; distinguish it from a suggestion.' }; copyPrompt(assistantPrompt(mode) + '\n\nRequested help: ' + requests[mode] + '\nMy request: ' + $('bridgeText').value.trim()); };
function renderMemory() {
  const memory = shared.projectMemory;
  $('memoryStatus').textContent = memory ? 'Shared revision ' + memory.revision : 'Ready to consolidate';
  if (!dirty.has('memoryForm')) {
    $('memorySummary').value = memory?.summary || '';
    for (const field of ['decisions', 'backlog', 'nextSteps']) $('memory' + field).value = (memory?.[field] || []).join('\n');
  }
  $('bridgePreview').value = assistantPrompt();
}
$('memoryForm').onsubmit = event => { event.preventDefault(); busy(event.submitter, async () => { const input = { action: 'saveMemory', summary: $('memorySummary').value.trim(), revision: shared.projectMemory?.revision }; for (const field of ['decisions', 'backlog', 'nextSteps']) input[field] = $('memory' + field).value.split('\n').map(value => value.trim()).filter(Boolean); await request(input); dirty.delete('memoryForm'); await load(); toast('Shared project record saved.'); }); };
$('bridgeSave').onclick = () => busy($('bridgeSave'), async () => { const value = $('bridgeText').value.trim(); if (!value) throw new Error('Add the request you want the morning assistant to review.'); await request({ action: 'addItem', text: 'Assistant request (' + $('bridgeMode').value + '): ' + value, type: 'Idea' }); $('bridgeText').value = ''; await load(); toast('Saved for morning review. Use Copy for immediate help.'); });
const queueFilter = make('input'); queueFilter.type = 'hidden'; queueFilter.id = 'queueFilter'; queueFilter.value = ''; $('itemSearch').parentElement.after(queueFilter);
document.querySelectorAll('[data-command]').forEach(button => button.onclick = () => {
  const command = button.dataset.command;
  if (command === 'now') return $('moveHeading').scrollIntoView({ behavior: 'smooth', block: 'start' });
  if (command === 'capture') { showTab('inbox'); return $('captureText').focus(); }
  if (command === 'recover') { showTab('resources'); return $('recoveryCard').scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  const verifyCount = shared.items.filter(item => !item.done && item.queue === 'Verify').length;
  const waitingCount = shared.items.filter(item => !item.done && item.queue === 'Waiting').length;
  showTab('inbox'); $('queueFilter').value = verifyCount ? 'Verify' : waitingCount ? 'Waiting' : ''; renderItems(); renderQueueOverview();
});
document.querySelectorAll('[data-resource-action]').forEach(button => button.onclick = () => {
  if (button.dataset.resourceAction === 'today') return showTab('today', true);
  if (button.dataset.resourceAction === 'recovery') return $('recoveryCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
  $('assistantBridge').scrollIntoView({ behavior: 'smooth', block: 'start' }); $('bridgeText').focus();
});
$('resourceExport').onclick = () => $('exportData').click();
$('resourceRefresh').onclick = () => busy($('resourceRefresh'), load);
const initialTab = location.hash.slice(1); showTab(['today', 'ideas', 'goals', 'projects', 'inbox', 'goal', 'resources', 'planning'].includes(initialTab) ? initialTab : 'today'); renderTimer();
document.addEventListener('visibilitychange', () => { if (!document.hidden) { renderTimer(); if (!loadedAt || Date.now() - loadedAt.getTime() > 60000) load(); } });
window.addEventListener('online', () => load());
window.addEventListener('offline', () => { connected = false; $('statusDot').classList.remove('live'); $('connectionText').textContent = 'Offline · reconnect before saving. Your current text stays here.'; });

$('dashboardToggle').onclick = () => {
  const expanded = document.querySelector('[data-page="today"]').classList.toggle('focused') === false;
  $('dashboardToggle').setAttribute('aria-expanded', String(expanded));
  $('dashboardToggle').textContent = expanded ? 'Return to one move' : 'Open full dashboard';
};

// Reuse the existing saved move, timer and Zeus conversation.
function openZeus(draft) {
  const page = document.querySelector('[data-page]:not([hidden])')?.dataset.page;
  const panel = page === 'inbox' ? 'inbox' : page === 'goal' ? 'build' : 'today';
  if (panel === 'today') {
    showTab('today');
    $('homeZeusWrap').open = true;
  }
  if (panel === 'inbox') $('inboxZeusWrap').open = true;
  const input = $('zeus-message-' + panel);
  if (!input) return;
  if (draft && input.value.trim()) { toast('Your existing Zeus draft is kept. Send or clear it before preparing another.'); }
  else if (draft) input.value = draft;
  input.closest('.zeus-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
  input.focus({ preventScroll: true });
}
let momentumChoice;
const momentumModes = {
  stuck: { title: 'Find the next visible action.', step: 'Write the one missing detail that is stopping you. Open the source that could answer it.', why: 'A specific obstacle is easier to work with than an entire unfinished task.', prompt: 'Help me get unstuck on my current saved move. Ask at most one necessary question, then suggest one physical action I can do in two minutes. State what still needs checking.' },
  money: { title: 'Look for a real opportunity.', step: 'Review one saved customer or money follow-up. Check its current status and draft a useful next message.', why: 'Start with an existing relationship or obligation. Verify the facts before committing time or money.', prompt: 'Help me find one realistic income-related next step in my saved Hub items. Prioritize verified customer follow-ups or existing opportunities. Do not invent leads, amounts, deadlines or promised earnings. Suggest a small no-spend action and one fact to verify.' },
  idea: { title: 'Turn a friction into an experiment.', step: 'Name one repeated annoyance from this week. Write one small way to make it easier for yourself or someone else.', why: 'An idea becomes useful when you can test it with a small cost in time.', prompt: 'Use my saved goals and current work to suggest three practical ideas: one to save time, one to help a customer, and one to explore income. Label assumptions. For each give a 15-minute no-spend test and a stop condition. Let me choose.' },
  low: { title: 'Make the beginning almost effortless.', step: 'Open the thing you need and do only the first two minutes. You can stop when the block ends.', why: 'Reducing the first step can make beginning easier. Rest is also a valid choice.', prompt: 'I have low energy. Help me choose one essential task from my saved priorities, shrink the start to two minutes, and say what can wait. Keep it gentle and brief.' },
};
document.querySelectorAll('[data-momentum]').forEach(button => button.onclick = () => {
  const mode = button.dataset.momentum;
  momentumChoice = { ...momentumModes[mode], mode };
  document.querySelectorAll('[data-momentum]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
  $('momentumHeading').textContent = momentumChoice.title;
  $('momentumStep').textContent = momentumChoice.step;
  $('momentumWhy').textContent = momentumChoice.why;
  $('momentumResult').hidden = false;
  document.getElementById('opportunityList')?.remove();
  if (mode === 'money') {
    const list = make('div', undefined, 'opportunity-list'); list.id = 'opportunityList';
    list.append(make('h3', 'Follow-ups to review'), make('p', 'Check the source → choose one action → record what happened. Matches below need confirmation; they are not verified opportunities.', 'hint'));
    const salesSource = make('a', 'Open Spectrum Sales Log ↗', 'text-link'); salesSource.href = 'https://docs.google.com/document/d/174-5UJFX6OH9T25sroxX8XCKveNgQ4IrCNwBzdMZhf4/edit'; salesSource.target = '_blank'; salesSource.rel = 'noopener noreferrer'; list.append(salesSource);
    list.append(make('p', 'The Sales Log and recent emails are not automatically checked by this panel. Open the source before treating a follow-up as current.', 'hint'));
    const candidates = shared.items.filter(item => !item.done && (item.type === 'Sales' || /customer|follow.?up|invoice|commission|income|sales|spectrum|payment/i.test(item.text))).slice(0, 3);
    if (!candidates.length) list.append(make('p', 'No matching saved follow-ups yet. Capture one in Inbox, or ask Zeus to help identify an opportunity.', 'muted'));
    candidates.forEach(item => {
      const review = make('div', undefined, 'followup-review');
      const age = item.updatedAt ? (Date.now() - Date.parse(item.updatedAt)) / 86400000 : Infinity;
      review.append(make('span', age > 7 ? 'Stale Hub record · needs checking' : 'Needs checking', 'badge'));
      const pick = make('button', item.text, 'opportunity-pick');
      pick.onclick = () => { momentumChoice.action = item.text; momentumChoice.step = 'Check the latest status of this follow-up and write one useful next step.'; $('momentumStep').textContent = 'Selected: ' + item.text + ' — ' + momentumChoice.step; };
      review.append(pick, make('p', 'Evidence: saved as ' + item.type + ' or matched a sales/follow-up term. Last Hub edit: ' + (item.updatedAt ? dateLabel(item.updatedAt.slice(0,10)) : 'unknown') + '. Last source confirmation: unknown.', 'hint'));
      const source = make('p', undefined, 'hint'); appendInline(source, 'Source: ' + (item.source || 'No direct source saved. Check the Sales Log or original message.')); review.append(source);
      review.append(make('p', 'Action: confirm whether this still needs a reply or another step. Tap the item to prepare your small start.', 'hint'));
      list.append(review);
    });
    $('momentumWhy').after(list);
  }
});
$('momentumStart').onclick = () => {
  if (!momentumChoice) return;
  const move = suggestedMove();
  $('planAction').value = momentumChoice.action || (momentumChoice.mode === 'idea' || momentumChoice.mode === 'money' ? momentumChoice.step : !move.needsRefresh && move.action ? move.action : momentumChoice.step);
  $('tinyStart').value = momentumChoice.step; $('energy').value = 'low'; dirty.add('planForm'); renderTimer();
  showTab('today');
  $('planForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
  toast('Small start prepared. Save it or start the two-minute block.');
};
$('momentumAsk').onclick = () => { if (momentumChoice) openZeus(momentumChoice.prompt + (momentumChoice.action ? '\nSelected saved item: ' + momentumChoice.action : '')); };
let installPrompt;
window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); installPrompt = event; });
const installDialog = make('dialog');
const installForm = make('form'); installForm.method = 'dialog';
installForm.append(make('h2', 'Keep J Hub on your phone'), make('p', 'iPhone: open this Hub in Safari, tap Share, then Add to Home Screen.'), make('p', 'Android: open in Chrome, tap the browser menu, then Install app or Add to Home screen.'), make('p', 'Sign in with the same account. Your tasks and conversations use the existing private Hub. An internet connection is needed to load and save.', 'muted'));
const closeInstall = make('button', 'Got it', 'primary'); closeInstall.type = 'submit'; installForm.append(closeInstall); installDialog.append(installForm); document.body.append(installDialog);
$('installApp').onclick = async () => { if (installPrompt) { await installPrompt.prompt(); installPrompt = null; } else installDialog.showModal(); };
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});

// A distinct mobile home; all actions still use the same Hub APIs and records.
const pocket = make('section'); pocket.dataset.page = 'mobile'; pocket.hidden = true;
pocket.innerHTML = `<header class="pocket-intro"><p class="eyebrow">J · in your pocket</p><h1>Less juggling.<br><span>More living.</span></h1><p>Your next step. Your ideas. Your Zeus.</p></header><div class="pocket-shortcuts"><button id="pocketTalk">↗<b>Talk</b><small>Your Zeus / God Agent</small></button><button id="pocketCapture">＋<b>Capture</b><small>Save a loose thought</small></button></div><section class="pocket-next"><div class="section-top"><p class="eyebrow">One thing at a time</p><span id="pocketSource" class="badge"></span></div><h2 id="pocketMove">Loading your move…</h2><p id="pocketTiny" class="muted"></p><div class="pocket-actions"><button class="primary" data-pocket-resolve="done">✓ Done</button><button class="secondary" data-pocket-resolve="Backlog">For later</button><button class="secondary" data-pocket-resolve="Next">Lower priority</button></div><button id="pocketDetails" class="text-link">Choose a move / start a focus block →</button></section><div id="pocketMomentum"></div><div id="pocketZeus"></div><details class="pocket-connections"><summary>Your connected system</summary><p id="pocketHubStatus"></p><p><b>Brain / Zeus / God Agent</b><br><span id="pocketBrainStatus">Checking bridge configuration…</span></p><p><b>Zep memory</b><br>Zeus uses its existing Zep recall and ingestion pipeline. A reply does not prove every memory was retrieved. Last isolated API checks passed ingestion and cross-channel recall; strict old-fact exclusion still needs work.</p><p><b>Repositories</b><br>Existing source projects, opened with your own sign-in. This screen does not edit code.</p><a href="https://github.com/jlemay90/j-god-agent" target="_blank" rel="noopener noreferrer">God Agent · GitHub ↗</a><a href="https://replit.com/@justinlemay/j-god-agent" target="_blank" rel="noopener noreferrer">God Agent · Replit ↗</a><a href="https://t.me/Lemayzeusbot" target="_blank" rel="noopener noreferrer">Zeus · Telegram ↗</a><button id="pocketFull" class="text-link">Open the regular Hub dashboard →</button></details>`;
$('main').prepend(pocket);
$('pocketMomentum').append(document.querySelector('.momentum'));
function renderPocket() {
  const move = suggestedMove();
  $('pocketMove').textContent = move.action || 'Room for your next useful move.';
  $('pocketSource').textContent = move.source;
  $('pocketTiny').textContent = move.tiny || 'Choose something small enough to begin.';
  document.querySelectorAll('[data-pocket-resolve]').forEach(b => b.disabled = !connected || !move.action || !!move.needsRefresh);
  $('pocketHubStatus').textContent = connected ? 'Hub records · synced ' + loadedAt.toLocaleTimeString([], {hour:'numeric',minute:'2-digit'}) : 'Hub records · reconnect to load and save';
  if ($('loopWhy')) renderMotivationLoop();
}
document.querySelectorAll('[data-pocket-resolve]').forEach(button => button.onclick = () => busy(button, async () => {
  const original = document.querySelector('[data-resolve-move="' + button.dataset.pocketResolve + '"]');
  if (original && !original.disabled) await original.onclick();
  renderPocket();
}));
$('pocketTalk').onclick = () => openZeus();
$('pocketCapture').onclick = () => { showTab('inbox'); $('captureText').focus(); };
$('pocketDetails').onclick = () => { showTab('today'); $('planForm').scrollIntoView({block:'start'}); };
$('pocketFull').onclick = () => { showTab('today'); document.querySelector('[data-page="today"]').classList.remove('focused'); $('dashboardToggle').setAttribute('aria-expanded','true'); $('dashboardToggle').textContent = 'Return to one move'; };
document.querySelector('.brand').onclick = event => { event.preventDefault(); showTab('today'); };
renderPocket();

const loopCard = make('section', undefined, 'card motivation-loop');
loopCard.innerHTML = `<p class="eyebrow">Your reason to begin</p><h2 id="loopWhy">Make room for what matters to you.</h2><p class="muted">One small action is enough to get back in motion.</p><ol class="loop-rail" aria-label="Motivation loop"><li>Notice your cue</li><li>Remember your why</li><li>Try two minutes</li><li>Keep the proof</li></ol><p id="loopReturn" class="return-cue"></p><button id="loopBegin" class="primary wide">Make my next step smaller</button><details id="loopReflection"><summary>I tried something · keep the proof</summary><form id="motivationForm"><label>What happened?<select id="loopOutcome"><option value="progress">Moved it forward</option><option value="waiting">Waiting on a reply</option><option value="stuck">Got stuck / learned something</option></select></label><label>What did you do or learn?<textarea id="loopNote" rows="2" maxlength="500" placeholder="One sentence is enough" required></textarea></label><label>Leave yourself an easy next step<input id="loopNext" maxlength="300" placeholder="Open the reply and check the installation date" required></label><label>When will you return?<input id="loopCue" maxlength="200" placeholder="After breakfast, when I open the Hub" required></label><button class="primary wide" type="submit">Keep my progress + next step</button><p class="hint">Saves your latest reflection for today. This does not mark a task complete or schedule a notification.</p></form></details><div id="loopProof" role="status"></div><button id="loopAsk" class="text-link" hidden>Help me with this obstacle →</button>`;
$('pocketMomentum').before(loopCard);
function renderMotivationLoop() {
  $('loopWhy').textContent = shared.goal?.why || 'Make room for what matters to you.';
  const latest = [...shared.checkins].filter(day => day.motivationOutcome).sort((a,b) => b.date.localeCompare(a.date))[0];
  $('loopReturn').textContent = latest ? 'Your return cue: ' + latest.motivationCue + ' → ' + latest.motivationNext : 'Try this cue: when you open J, choose one small action before opening another app.';
  const proof = $('loopProof'); proof.replaceChildren();
  if (latest) {
    proof.append(make('p', ({progress:'You moved something forward.',waiting:'You know what you are waiting for.',stuck:'You found the next obstacle.'})[latest.motivationOutcome], 'proof-title'));
    proof.append(make('p', latest.motivationNote), make('p', 'Your record · ' + dateLabel(latest.date) + ' · a missed day does not erase this.', 'hint'));
    $('loopAsk').hidden = latest.motivationOutcome !== 'stuck';
    $('loopAsk').onclick = () => openZeus('Help me make this obstacle easier. My latest reflection: ' + latest.motivationNote + '\nMy intended next step: ' + latest.motivationNext + '\nSuggest one tiny action, and ask at most one question if needed.');
  }
}
$('loopBegin').onclick = () => { document.querySelector('[data-momentum="low"]').click(); $('momentumResult').scrollIntoView({behavior:'smooth',block:'center'}); };
$('motivationForm').onsubmit = event => {
  event.preventDefault();
  busy(event.submitter, async () => {
    await request({action:'saveCheckin',date:shared.today,motivationOutcome:$('loopOutcome').value,motivationNote:$('loopNote').value.trim(),motivationNext:$('loopNext').value.trim(),motivationCue:$('loopCue').value.trim()});
    await load(); $('loopReflection').open = false; $('loopProof').scrollIntoView({behavior:'smooth',block:'center'}); toast('Progress saved. Your next beginning is waiting for you.');
  });
};
renderMotivationLoop();
