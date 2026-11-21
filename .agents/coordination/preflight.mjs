/**
 * J Command OS / Issue #2 — phase-1 coordination preflight.
 * Pure, read-only checks. Does NOT reserve files or provide an atomic lock.
 * Canonical policy: ../skills/app-continuity/SKILL.md
 */
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const SHA = /^[0-9a-f]{40}$/i;
const ACTIVE = new Set(['claimed', 'in_progress', 'proposed', 'review']);
const TERMINAL = new Set(['merged', 'closed', 'abandoned', 'released']);
const REQUIRED_HANDOFF = ['summary', 'tests', 'unknowns', 'nextStep'];
const isPlainObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const validPath = (p) => typeof p === 'string' && p.length > 0 && !p.startsWith('/') && !p.includes('\\') && !p.split('/').some((s) => s === '' || s === '.' || s === '..');

/** Evaluate a proposed, isolated agent change against a freshly retrieved state snapshot. */
export function evaluateProposal(proposal, state) {
  const blockers = [];
  const add = (code, detail) => blockers.push({ code, detail });
  if (!isPlainObject(proposal) || !isPlainObject(state)) {
    return { status: 'BLOCK', blockers: [{ code: 'INVALID_INPUT', detail: 'Proposal and state must be objects.' }] };
  }

  for (const field of ['agent', 'task', 'branch']) {
    if (typeof proposal[field] !== 'string' || !proposal[field].trim()) add('MISSING_FIELD', 'proposal.' + field + ' is required');
  }
  if (typeof proposal.branch === 'string' && !/^agent\/[a-z0-9][a-z0-9._/-]*$/i.test(proposal.branch)) {
    add('UNSAFE_BRANCH', 'Use an isolated agent/<agent>/<topic> branch.');
  }
  if (proposal.action !== 'propose') add('ACTION_NOT_AUTHORIZED', 'Phase 1 only permits action=propose; never merge, deploy, or write a Hub record.');
  if (!SHA.test(proposal.baseSha ?? '')) add('INVALID_BASE', 'proposal.baseSha must be an actual 40-character Git commit SHA.');
  if (!SHA.test(state.currentBaseSha ?? '')) add('UNKNOWN_BASE', 'state.currentBaseSha must be read from the current repository, not inferred.');
  if (SHA.test(proposal.baseSha ?? '') && SHA.test(state.currentBaseSha ?? '') && proposal.baseSha.toLowerCase() !== state.currentBaseSha.toLowerCase()) {
    add('STALE_BASE', 'Proposed base SHA differs from the latest verified base SHA.');
  }

  if (!Array.isArray(proposal.files) || proposal.files.length === 0 || !proposal.files.every(validPath)) {
    add('INVALID_FILES', 'A nonempty list of safe, explicit relative file paths is required.');
  }
  if (!Array.isArray(state.activeClaims)) add('UNKNOWN_CLAIMS', 'Cannot safely evaluate conflicts without an active-claims snapshot.');
  if (!isPlainObject(state.recordRevisions)) add('UNKNOWN_RECORDS', 'Cannot safely evaluate Hub revisions without a current revision map.');

  if (!isPlainObject(proposal.handoff) || REQUIRED_HANDOFF.some((k) => typeof proposal.handoff[k] !== 'string' || !proposal.handoff[k].trim())) {
    add('MISSING_HANDOFF', 'Handoff must include nonempty: ' + REQUIRED_HANDOFF.join(', ') + '.');
  }

  if (Array.isArray(state.activeClaims) && Array.isArray(proposal.files)) {
    for (const claim of state.activeClaims) {
      if (!isPlainObject(claim) || typeof claim.branch !== 'string' || !claim.branch.trim() || typeof claim.status !== 'string') {
        add('UNKNOWN_CLAIM', 'Malformed claim encountered; cannot establish exclusive ownership.');
        continue;
      }
      if (TERMINAL.has(claim.status)) continue;
      if (!ACTIVE.has(claim.status)) {
        add('UNKNOWN_CLAIM_STATUS', 'Unrecognized claim status ' + JSON.stringify(claim.status) + ' on ' + claim.branch + '; only active or terminal statuses are permitted.');
        continue;
      }
      if (claim.branch === proposal.branch) continue;
      if (!Array.isArray(claim.files) || claim.files.length === 0 || !claim.files.every(validPath)) {
        add('UNKNOWN_CLAIM_SCOPE', 'Cannot evaluate active claim ' + String(claim.branch) + '.');
        continue;
      }
      const intersect = claim.files.filter((file) => proposal.files.includes(file));
      if (intersect.length > 0) add('FILE_CONFLICT', 'Branch ' + claim.branch + ' already claims ' + intersect.join(', ') + '.');
    }
  }

  const updates = proposal.recordUpdates === undefined ? [] : proposal.recordUpdates;
  if (!Array.isArray(updates)) add('INVALID_RECORD_UPDATES', 'recordUpdates must be an array.');
  else if (isPlainObject(state.recordRevisions)) {
    for (const update of updates) {
      if (!isPlainObject(update) || typeof update.key !== 'string' || !update.key.trim() || !Number.isSafeInteger(update.expectedRevision)) {
        add('INVALID_RECORD_UPDATE', 'Each record update requires a nonempty key and integer expectedRevision.');
        continue;
      }
      const latest = state.recordRevisions[update.key];
      if (!Number.isSafeInteger(latest)) add('UNKNOWN_RECORD_REVISION', 'No verified current revision for ' + update.key + '.');
      else if (latest !== update.expectedRevision) add('STALE_RECORD', update.key + ' expected revision ' + update.expectedRevision + ', current revision ' + latest + '.');
    }
  }

  return { status: blockers.length === 0 ? 'PASS' : 'BLOCK', blockers };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [proposalPath, statePath] = process.argv.slice(2);
  if (!proposalPath || !statePath) {
    process.stderr.write('Usage: node .agents/coordination/preflight.mjs <proposal.json> <verified-state.json>\n');
    process.exitCode = 2;
  } else {
    try {
      const result = evaluateProposal(JSON.parse(readFileSync(proposalPath, 'utf8')), JSON.parse(readFileSync(statePath, 'utf8')));
      process.stdout.write(JSON.stringify(result, null, 2) + '\n');
      if (result.status !== 'PASS') process.exitCode = 1;
    } catch (err) {
      process.stderr.write('Preflight aborted; no changes applied: ' + err.message + '\n');
      process.exitCode = 2;
    }
  }
}
