import test from 'node:test';
import assert from 'node:assert/strict';
import { evaluateProposal } from './preflight.mjs';

const A = 'a'.repeat(40);
const B = 'b'.repeat(40);
const proposal = () => ({
  agent: 'Agent B',
  task: 'Issue #2 phase-1 preflight',
  branch: 'agent/b/preflight',
  action: 'propose',
  baseSha: A,
  files: ['.agents/coordination/README.md'],
  recordUpdates: [{ key: 'hub-project-memory', expectedRevision: 7 }],
  handoff: { summary: 'Draft only', tests: 'Not run yet', unknowns: 'Live sync not checked', nextStep: 'Request review' },
});
const state = () => ({
  currentBaseSha: A,
  activeClaims: [{ branch: 'agent/a/bridge', files: ['hub-site/worker/zeus.js'], status: 'claimed' }],
  recordRevisions: { 'hub-project-memory': 7 },
});
const blocked = (result, code) => assert.ok(result.blockers.some((b) => b.code === code), JSON.stringify(result));

test('Agent A and Agent B can propose non-overlapping files', () => {
  assert.deepEqual(evaluateProposal(proposal(), state()), { status: 'PASS', blockers: [] });
});

test('Overlapping file claims cannot pass silently', () => {
  const p = proposal(); p.files = ['hub-site/worker/zeus.js'];
  blocked(evaluateProposal(p, state()), 'FILE_CONFLICT');
});

test('An outdated Git baseline is blocked', () => {
  const p = proposal(); p.baseSha = B;
  blocked(evaluateProposal(p, state()), 'STALE_BASE');
});

test('A stale Hub revision is blocked without touching Hub data', () => {
  const p = proposal(); p.recordUpdates[0].expectedRevision = 6;
  blocked(evaluateProposal(p, state()), 'STALE_RECORD');
});

test('Unverified Hub revision must fail closed', () => {
  const s = state(); s.recordRevisions = {};
  blocked(evaluateProposal(proposal(), s), 'UNKNOWN_RECORD_REVISION');
});

test('Missing agent handoff cannot pass', () => {
  const p = proposal(); delete p.handoff;
  blocked(evaluateProposal(p, state()), 'MISSING_HANDOFF');
});

test('Absent active claims snapshot fails closed', () => {
  const s = state(); delete s.activeClaims;
  blocked(evaluateProposal(proposal(), s), 'UNKNOWN_CLAIMS');
});

test('Direct main branch/deploy action is rejected', () => {
  const p = proposal(); p.branch = 'main'; p.action = 'deploy';
  const x = evaluateProposal(p, state());
  blocked(x, 'UNSAFE_BRANCH'); blocked(x, 'ACTION_NOT_AUTHORIZED');
});

test('Unsafe paths and incomplete active claim scopes fail closed', () => {
  const p = proposal(); p.files = ['../secrets'];
  blocked(evaluateProposal(p, state()), 'INVALID_FILES');
  const s = state(); s.activeClaims[0].files = undefined;
  blocked(evaluateProposal(proposal(), s), 'UNKNOWN_CLAIM_SCOPE');
});

test('Malformed active claims fail closed rather than silently passing', () => {
  const s = state(); s.activeClaims.push(null);
  blocked(evaluateProposal(proposal(), s), 'UNKNOWN_CLAIM');
});
