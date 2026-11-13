const planningStatuses = { active: 'Active', waiting: 'Waiting', paused: 'Paused', done: 'Done' };
const planningTemplates = {
  'Decision': { outcome: 'Compare the realistic options and choose the next step.', steps: ['Write must-haves and dealbreakers', 'Check the missing facts', 'Record the decision and why'] },
  'Follow-up': { outcome: 'Get a clear answer and record who owns the next step.', steps: ['Find the original source or contact', 'Make the follow-up', 'Record the answer and next step'] },
  'Build & test': { outcome: 'Use the result on a real task and verify what works.', steps: ['Define one real test', 'Run it and record friction', 'Fix the issue and retest'] },
};
const planItems = () => new Map(shared.items.map(item => [item.id, item]));
const planIsStale = record => !record.reviewed || record.reviewed < datePlus(shared.today, -7);
const planIsOpen = record => ['active', 'waiting'].includes(record.status);

function planButton(text, className, action) {
  const button = make('button', text, className);
  button.type = 'button';
  button.onclick = action;
  return button;
}

function planAction(record, items) {
  if (!record.actionItem) return record.next || '';
  const item = items.get(record.actionItem);
  return item && !item.done ? item.text : '';
}

function planProgress(steps = []) {
  const box = make('div', undefined, 'plan-progress');
  if (steps.length) {
    const done = steps.filter(step => step.done).length;
    const meter = make('progress');
    meter.max = steps.length;
    meter.value = done;
    meter.setAttribute('aria-label', 'Milestones complete');
    box.append(meter, make('span', done + '/' + steps.length + ' milestones'));
  } else {
    box.append(make('span', 'No milestones set'));
  }
  return box;
}

function openPlanItem(item) {
  $('planDialog').close();
  $('queueFilter').value = '';
  $('itemSearch').value = '';
  $('itemSearch').dataset.itemId = item.id;
  showTab('inbox');
  renderItems();
  renderQueueOverview();
  if (item.done) $('completedItems').closest('details').open = true;
  const row = $('hub-item-' + item.id);
  if (row) {
    row.tabIndex = -1;
    row.focus();
    row.scrollIntoView({ block: 'center' });
  }
}

function planCard(record, items) {
  const card = make('article', undefined, 'plan-record');
  const top = make('div', undefined, 'plan-tags');
  top.append(make('span', record.area || (record.kind === 'goal' ? 'Goal' : 'Project'), 'eyebrow'));
  top.append(make('span', record.evidence === 'confirmed' ? 'Confirmed intent' : 'Proposed · needs confirmation', 'badge' + (record.evidence === 'assumption' ? ' plan-warning' : '')));
  if (planIsStale(record)) top.append(make('span', 'Review due', 'badge plan-warning'));
  const heading = make('h3');
  heading.append(planButton(record.title, 'plan-record-link', () => editPlanRecord(record)));
  const next = planAction(record, items);
  const linkedItem = items.get(record.actionItem);
  const nextText = next || (linkedItem?.done ? 'Linked action completed. Choose a new next step.' : record.outcome || 'Add a clear next step.');
  card.append(top, heading, make('p', nextText, 'plan-preview'), planProgress(record.steps));
  const meta = [planningStatuses[record.status]];
  if (record.deadline) meta.push((record.deadline < shared.today && planIsOpen(record) ? 'Overdue ' : 'Due ') + dateLabel(record.deadline));
  if (record.blocker) meta.push('Blocker logged');
  card.append(make('p', meta.join(' · '), 'hint'));
  return card;
}

function renderPlanning() {
  const records = shared.planning;
  if (!Array.isArray(records)) return;
  $('planNew').disabled = false;
  $('planReview').disabled = false;
  $('planLoading').hidden = true;
  const items = planItems();
  const today = $('planToday');
  today.replaceChildren();
  const chosen = todayRecord().nextAction;
  if (chosen) {
    today.append(make('p', 'Your saved move', 'eyebrow'), make('p', chosen, 'plan-today-move'));
  } else {
    today.append(make('p', 'You haven’t chosen a move today.', 'plan-today-move'));
  }
  const pulse = shared.pulse;
  if (pulse?.date === shared.today && pulse.top3?.length) {
    const list = make('ol', undefined, 'priority-list');
    pulse.top3.forEach(action => list.append(make('li', action)));
    today.append(list);
  } else {
    today.append(make('p', pulse ? 'Last Daily Pulse · ' + dateLabel(pulse.date) + '. Review it on Today for context.' : 'A Daily Pulse will appear here when it’s published.', 'muted'));
  }

  const watch = $('planWatch');
  watch.replaceChildren();
  const open = records.filter(planIsOpen);
  const deadlines = open.filter(record => record.deadline).sort((a, b) => a.deadline.localeCompare(b.deadline));
  if (shared.goal?.deadline && shared.goal.milestones?.some(step => !step.done)) {
    deadlines.push({ title: '30-day Hub build', deadline: shared.goal.deadline });
    deadlines.sort((a, b) => a.deadline.localeCompare(b.deadline));
  }
  const blockers = open.filter(record => record.blocker || record.status === 'waiting');
  for (const [label, entries] of [['Deadline', deadlines], ['Blocker', blockers]]) {
    const list = make('ul', undefined, 'plan-watch-list');
    for (const record of entries.slice(0, 3)) {
      const row = make('li');
      const detail = label === 'Deadline' ? (record.deadline < shared.today ? 'Overdue · ' : 'Due · ') + dateLabel(record.deadline) : record.blocker || 'Waiting for a dependency';
      row.append(planButton(record.title, 'text-link', () => record.id ? editPlanRecord(record) : showTab('goal', true)), make('p', detail, 'hint'));
      list.append(row);
    }
    if (entries.length) watch.append(list);
  }
  if (!watch.childNodes.length) watch.append(make('p', 'No deadlines or blockers logged.', 'muted'));
  const staleCount = open.filter(planIsStale).length;
  if (staleCount) watch.append(make('p', staleCount + ' open ' + (staleCount === 1 ? 'record needs' : 'records need') + ' review.', 'hint'));

  const board = $('planBoard');
  board.replaceChildren();
  for (const [title, matches] of [
    ['Active projects', record => record.kind === 'project' && planIsOpen(record)],
    ['Short-term goals', record => record.kind === 'goal' && record.horizon === 'short' && planIsOpen(record)],
    ['Long-term goals', record => record.kind === 'goal' && record.horizon === 'long' && planIsOpen(record)],
  ]) {
    const group = make('section', undefined, 'plan-group');
    group.append(make('h2', title));
    if (title === 'Short-term goals' && shared.goal) {
      const goal = shared.goal;
      const card = make('article', undefined, 'plan-record plan-linked-goal');
      const heading = make('h3');
      heading.append(planButton(goal.title, 'plan-record-link', () => showTab('goal', true)));
      card.append(make('p', 'Live Hub goal · Open to edit', 'eyebrow'), heading, make('p', goal.nextStep || goal.measure || '', 'plan-preview'), planProgress(goal.milestones), make('p', goal.deadline ? 'Due ' + dateLabel(goal.deadline) : 'No deadline set', 'hint'));
      group.append(card);
    }
    records.filter(matches).forEach(record => group.append(planCard(record, items)));
    if (group.children.length === 1) group.append(make('p', 'Nothing in this section yet.', 'muted'));
    board.append(group);
  }
  const later = records.filter(record => !planIsOpen(record));
  if (later.length) {
    const group = make('details', undefined, 'card plan-later');
    group.append(make('summary', 'Paused & completed · ' + later.length));
    later.forEach(record => group.append(planCard(record, items)));
    board.append(group);
  }
}

function renderGoalAndProjectViews() {
  const records = Array.isArray(shared.planning) ? shared.planning : [];
  const items = planItems();
  for (const [kind, horizon, listId, emptyId] of [
    ['goal', 'short', 'shortGoals', 'shortGoalsEmpty'],
    ['goal', 'long', 'longGoals', 'longGoalsEmpty'],
  ]) {
    const list = $(listId);
    const matching = records.filter(record => record.kind === kind && record.horizon === horizon && planIsOpen(record));
    list.replaceChildren(...matching.map(record => planCard(record, items)));
    $(emptyId).hidden = matching.length > 0;
  }
  const projects = records.filter(record => record.kind === 'project');
  const active = projects.filter(planIsOpen);
  const archived = projects.filter(record => !planIsOpen(record));
  const list = $('projectList');
  list.replaceChildren(...active.map(record => planCard(record, items)));
  $('projectsEmpty').hidden = projects.length > 0;
  if (archived.length) {
    const details = make('details', undefined, 'card plan-later');
    details.append(make('summary', 'Paused & completed · ' + archived.length));
    archived.forEach(record => details.append(planCard(record, items)));
    list.append(details);
  }
  const goal = shared.goal;
  $('buildGoalTitle').textContent = goal?.title || '30-day Hub goal';
  $('buildGoalSummary').textContent = goal?.nextStep || goal?.measure || 'Open the existing Hub build record.';
}

function planDialog(title) {
  const dialog = $('planDialog');
  const form = $('planDialogForm');
  $('planDialogTitle').textContent = title;
  $('planDialogStatus').textContent = '';
  $('planDialogBody').replaceChildren();
  form.onsubmit = event => event.preventDefault();
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop = 0;
  return $('planDialogBody');
}

async function runPlanSave(button, operation) {
  button.disabled = true;
  $('planDialogStatus').textContent = '';
  try {
    await operation();
  } catch (error) {
    $('planDialogStatus').textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function planField(label, control) {
  const wrapper = make('label', label);
  wrapper.append(control);
  return wrapper;
}

function planOptions(values, selected) {
  const select = make('select');
  for (const [value, label] of values) select.add(new Option(label, value));
  select.value = selected;
  return select;
}

function planItemLabel(item) {
  return item.text.split('\n')[0].slice(0, 88) + (item.done ? ' · Done' : '');
}

function editPlanRecord(record = {}) {
  const body = planDialog(record.id ? 'Edit record' : 'Add a record');
  const items = planItems();
  const fields = {};
  const title = make('input');
  title.value = record.title || '';
  title.required = true;
  title.maxLength = 110;
  fields.title = title;
  body.append(planField('Title', title));
  const settings = make('div', undefined, 'plan-form-grid');
  for (const [field, label, values, fallback] of [
    ['kind', 'Record type', [['project', 'Project'], ['goal', 'Goal']], 'project'],
    ['horizon', 'Goal horizon', [['short', 'Short term'], ['long', 'Long term']], 'short'],
    ['status', 'Status', Object.entries(planningStatuses), 'active'],
    ['evidence', 'Evidence', [['assumption', 'Needs verification'], ['confirmed', 'Confirmed intent']], 'assumption'],
  ]) {
    fields[field] = planOptions(values, record[field] || fallback);
    settings.append(planField(label, fields[field]));
  }
  body.append(settings);
  const template = planOptions([['', 'Blank project'], ...Object.keys(planningTemplates).map(name => [name, name])], '');
  const templateRow = planField('Reusable project template', template);
  if (!record.id) body.append(templateRow);
  const syncKind = () => {
    const goal = fields.kind.value === 'goal';
    fields.horizon.parentElement.hidden = !goal;
    templateRow.hidden = goal;
  };
  fields.kind.onchange = syncKind;
  syncKind();

  for (const [field, label, max] of [
    ['area', 'Life area', 40], ['outcome', 'What would count as a result?', 420], ['next', 'Next action', 420], ['blocker', 'Blocker or dependency', 420],
  ]) {
    const control = make(field === 'area' ? 'input' : 'textarea');
    if (field !== 'area') control.rows = 2;
    control.maxLength = max;
    control.value = record[field] || '';
    fields[field] = control;
    body.append(planField(label, control));
  }
  const dates = make('div', undefined, 'plan-form-grid');
  for (const [field, label] of [['deadline', 'Deadline'], ['reviewed', 'Last verified or reviewed']]) {
    fields[field] = make('input');
    fields[field].type = 'date';
    fields[field].value = record[field] || '';
    dates.append(planField(label, fields[field]));
  }
  fields.reviewed.max = shared.today;
  body.append(dates, planButton('Mark reviewed today', 'secondary small', () => { fields.reviewed.value = shared.today; }));

  const detail = make('details', undefined, 'plan-details');
  detail.open = Boolean(record.notes || record.decisions || record.questions || record.source || record.itemIds?.length);
  detail.append(make('summary', 'Source, links, notes & decisions'));
  for (const [field, label, max] of [['source', 'Source or reason for confidence', 240], ['notes', 'Notes', 1500], ['decisions', 'Decisions made', 1500], ['questions', 'Open questions', 1500]]) {
    const control = make('textarea');
    control.rows = 2;
    control.maxLength = max;
    control.value = record[field] || '';
    fields[field] = control;
    detail.append(planField(label, control));
  }
  for (const id of record.itemIds || []) {
    const item = items.get(id);
    if (item) detail.append(planButton('Open Hub item · ' + planItemLabel(item), 'text-link plan-source-link', () => openPlanItem(item)));
  }
  if (record.resource === 'memory') detail.append(planButton('Open shared project memory →', 'text-link plan-source-link', () => {
    $('planDialog').close();
    showTab('resources');
    $('memoryForm').closest('details').open = true;
    $('memoryStatus').scrollIntoView({ block: 'center' });
  }));
  const linkOptions = [['', 'No item selected'], ...[...items.values()].map(item => [item.id, planItemLabel(item)])];
  const links = Array.from({ length: 4 }, (_, index) => {
    const select = planOptions(linkOptions, record.itemIds?.[index] || '');
    detail.append(planField('Linked Hub item ' + (index + 1), select));
    return select;
  });
  const actionLink = planOptions([], '');
  detail.append(planField('Use a linked item as the next action', actionLink));
  const syncLinks = (selected = actionLink.value) => {
    const options = [...new Set(links.map(select => select.value).filter(Boolean))];
    actionLink.replaceChildren(new Option('Use the written next action', ''), ...options.map(id => new Option(planItemLabel(items.get(id)), id)));
    actionLink.value = options.includes(selected) ? selected : '';
    fields.next.disabled = Boolean(actionLink.value);
  };
  links.forEach(select => { select.onchange = () => syncLinks(); });
  actionLink.onchange = () => syncLinks();
  syncLinks(record.actionItem);
  body.append(detail);

  const milestones = make('fieldset', undefined, 'plan-milestones');
  const stepList = make('div');
  const addStep = (step = {}) => {
    if (stepList.children.length >= 12) return;
    const row = make('div', undefined, 'plan-step');
    const done = make('input');
    done.type = 'checkbox';
    done.checked = Boolean(step.done);
    done.setAttribute('aria-label', 'Milestone complete');
    const text = make('input');
    text.value = step.label || '';
    text.maxLength = 160;
    text.placeholder = 'Milestone';
    text.setAttribute('aria-label', 'Milestone name');
    const remove = planButton('Remove', 'quiet', () => row.remove());
    remove.setAttribute('aria-label', 'Remove milestone');
    row.append(done, text, remove);
    stepList.append(row);
  };
  milestones.append(make('legend', 'Progress milestones'), stepList, planButton('＋ Add milestone', 'secondary small', () => addStep()));
  (record.steps || []).forEach(addStep);
  body.append(milestones);
  template.onchange = () => {
    const preset = planningTemplates[template.value];
    if (!preset) return;
    if (!fields.outcome.value) fields.outcome.value = preset.outcome;
    if (!stepList.children.length) preset.steps.forEach(label => addStep({ label }));
  };

  const actions = make('div', undefined, 'row wrap');
  const save = make('button', 'Save record', 'primary');
  save.type = 'submit';
  actions.append(save);
  if (record.id) actions.append(planButton('Remove record', 'quiet plan-danger', event => {
    const button = event.currentTarget;
    if (button.dataset.confirm !== 'yes') {
      button.dataset.confirm = 'yes';
      button.textContent = 'Confirm removal';
      $('planDialogStatus').textContent = 'This removes the planning record. Linked Hub items stay in the Inbox.';
      return;
    }
    runPlanSave(button, async () => {
      shared.planning = await request({ action: 'removePlanRecord', id: record.id, rev: record.rev ?? 0 });
      $('planDialog').close();
      renderPlanning();
      toast('Planning record removed.');
    });
  }));
  body.append(actions);
  $('planDialogForm').onsubmit = event => {
    event.preventDefault();
    runPlanSave(save, async () => {
      const data = Object.fromEntries(Object.entries(fields).map(([key, control]) => [key, control.value]));
      const steps = [...stepList.children].map(row => ({ done: row.children[0].checked, label: row.children[1].value.trim() })).filter(step => step.label);
      shared.planning = await request({ ...data, action: 'savePlanRecord', id: record.id, rev: record.rev ?? 0, itemIds: links.map(select => select.value).filter(Boolean), actionItem: actionLink.value, resource: record.resource, steps });
      $('planDialog').close();
      renderPlanning();
      toast('Saved to your shared plan.');
    });
  };
}

function reviewPlan() {
  const body = planDialog('Choose one move');
  body.append(make('p', 'Start with something you can act on. Check what’s waiting and verify uncertain records from the plan.', 'muted'));
  const items = planItems();
  const today = todayRecord();
  const candidates = new Map();
  const add = (action, label, start = '') => { if (action && !candidates.has(action)) candidates.set(action, { label, start }); };
  add(today.nextAction, 'Your saved move', today.tinyStart);
  shared.items.filter(item => !item.done && item.queue === 'Now').forEach(item => add(item.text, 'Hub focus', item.startStep));
  if (shared.pulse?.date === shared.today) shared.pulse.top3?.forEach(action => add(action, 'Today’s Daily Pulse'));
  shared.planning.filter(record => record.status === 'active' && record.evidence === 'confirmed' && !planIsStale(record))
    .sort((a, b) => (a.deadline || '9999').localeCompare(b.deadline || '9999'))
    .forEach(record => {
      const item = items.get(record.actionItem);
      if (record.blocker && !record.actionItem) return;
      if (!item || !['Waiting', 'Verify', 'Backlog'].includes(item.queue)) add(planAction(record, items), record.area || 'Your plan', item?.startStep);
    });
  if (shared.goal?.deadline >= shared.today && shared.goal.milestones?.some(step => !step.done)) add(shared.goal.nextStep, '30-day Hub build');

  const choice = planOptions([['', 'Write my own move'], ...[...candidates].map(([action, data]) => [action, data.label + ' · ' + action.slice(0, 78)])], '');
  const action = make('textarea');
  action.rows = 3;
  action.required = true;
  action.maxLength = 500;
  const start = make('input');
  start.maxLength = 300;
  choice.onchange = () => { action.value = choice.value; start.value = candidates.get(choice.value)?.start || ''; };
  if (candidates.size) {
    body.append(planField('Pick a starting point', choice));
    choice.value = candidates.keys().next().value;
    choice.onchange();
  }
  body.append(planField('What will you do?', action), planField('Smallest first step', start));
  if (today.nextAction) body.append(make('p', 'Saving replaces the current move on Today. Hub item completion stays as recorded.', 'hint'));
  const save = make('button', 'Set as my move today', 'primary');
  save.type = 'submit';
  body.append(save);
  $('planDialogForm').onsubmit = event => {
    event.preventDefault();
    runPlanSave(save, async () => {
      if (!action.value.trim()) throw new Error('Write one concrete move first.');
      if (shared.today !== centralDate()) throw new Error('The date changed. Refresh the Hub and review again.');
      const saved = await request({ action: 'saveCheckin', date: shared.today, nextAction: action.value, tinyStart: start.value, moveStatus: '' });
      shared.checkins = [saved, ...shared.checkins.filter(day => day.date !== saved.date)];
      dirty.delete('planForm');
      $('planDialog').close();
      render();
      toast('Your move is saved on Today.');
    });
  };
}

$('planNew').onclick = () => editPlanRecord();
$('goalsAdd').onclick = () => editPlanRecord({ kind: 'goal', horizon: 'short', evidence: 'assumption', status: 'active' });
$('projectsAdd').onclick = () => editPlanRecord({ kind: 'project', evidence: 'assumption', status: 'active' });
$('planReview').onclick = reviewPlan;
$('planClose').onclick = () => $('planDialog').close();
load();
