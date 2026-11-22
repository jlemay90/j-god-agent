"""Provider-free RUN controller regression suite."""
import os
import tempfile
import unittest
from pathlib import Path
from run_controller import Controller, CycleResult, RunError


class Clock:
    def __init__(self): self.now = 1000.0
    def __call__(self): return self.now


class RunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'private.sqlite'
        self.clock = Clock()
        self.c = Controller(self.path, clock=self.clock)

    def tearDown(self):
        self.c.close()
        self.temp.cleanup()

    def worker(self, req):
        return CycleResult({'n': req.cycle}, f'checkpoint {req.cycle}')

    def test_five_cycles_and_checkpoint_event_counts(self):
        mid = self.c.create('test', max_cycles=5)
        result = self.c.run(mid, self.worker)
        self.assertEqual((result['completed'], result['status'], result['state']), (5, 'completed', {'n': 5}))
        self.assertEqual([e['cycle'] for e in self.c.events(mid) if e['event'] == 'cycle_completed'], [1,2,3,4,5])
        self.assertEqual(len({e['token'] for e in self.c.events(mid) if e['event'] == 'cycle_started'}), 5)

    def test_restart_reads_durable_checkpoint(self):
        mid = self.c.create('persist', max_cycles=5)
        def crash_on_third(req):
            if req.cycle == 3: raise RuntimeError('crash')
            return self.worker(req)
        with self.assertRaises(RuntimeError): self.c.run(mid, crash_on_third)
        self.c.close()
        self.c = Controller(self.path, clock=self.clock)
        s = self.c.status(mid)
        self.assertEqual((s['completed'], s['state'], s['status']), (2, {'n':2}, 'needs_review'))
        self.assertEqual(s['in_flight_cycle'], 3)
        with self.assertRaises(RunError): self.c.run(mid, self.worker)
        self.c.resolve_interrupted(mid, outcome='no_effect', receipt='Externally verified failed before any side effects')
        end = self.c.run(mid, self.worker)
        self.assertEqual((end['completed'], end['status']), (5, 'completed'))

    def test_in_flight_never_auto_replayed(self):
        mid = self.c.create('guard')
        req = self.c._claim(mid)
        other = Controller(self.path, clock=self.clock)
        try:
            with self.assertRaises(RunError): other.run(mid, self.worker)
            self.assertEqual(other.status(mid)['completed'], 0)
        finally: other.close()
        self.c.mark_interrupted_for_review(mid)
        self.assertEqual(self.c.status(mid)['status'], 'needs_review')

    def test_verified_completed_external_action_not_replayed(self):
        mid = self.c.create('external', max_cycles=3)
        req = self.c._claim(mid)
        self.c.mark_interrupted_for_review(mid)
        self.c.resolve_interrupted(mid, outcome='completed',
                                   receipt='Provider verified remote operation with matching idempotency key',
                                   verified_state={'n': 1}, verified_cost_usd=.01)
        seen = []
        def remaining(r):
            seen.append(r.cycle)
            return self.worker(r)
        result = self.c.run(mid, remaining)
        self.assertEqual(seen, [2, 3])
        self.assertEqual(result['completed'], 3)
        self.assertAlmostEqual(result['spent_usd'], .01)
        self.assertEqual(len([e for e in self.c.events(mid) if e['event']=='interruption_verified_completed']), 1)

    def test_reconciliation_needs_external_receipt(self):
        mid = self.c.create('receipt')
        self.c._claim(mid)
        self.c.mark_interrupted_for_review(mid)
        with self.assertRaises(ValueError):
            self.c.resolve_interrupted(mid, outcome='completed', receipt='no state')
        with self.assertRaises(ValueError):
            self.c.resolve_interrupted(mid, outcome='no_effect', receipt='')
        self.assertEqual(self.c.status(mid)['status'], 'needs_review')

    def test_deadline_checked_between_cycles(self):
        mid = self.c.create('time', max_cycles=10, max_seconds=10)
        def slow(req):
            self.clock.now += 11
            return self.worker(req)
        r = self.c.run(mid, slow)
        self.assertEqual((r['completed'], r['status']), (1, 'completed'))

    def test_spending_budget_caps_next_cycle_not_in_flight(self):
        mid = self.c.create('money', max_cycles=9, max_cost_usd=.15)
        def counted(req): return CycleResult({'n':req.cycle}, 'verified usage record', .06)
        result = self.c.run(mid, counted)
        self.assertEqual(result['completed'], 3)
        self.assertGreaterEqual(result['spent_usd'], .15)

    def test_pause_resume_preserves_deadline(self):
        mid = self.c.create('pause', max_seconds=30)
        self.c.pause(mid)
        self.assertEqual(self.c.status(mid)['status'], 'paused')
        self.c.resume(mid)
        self.assertEqual(self.c.run(mid, self.worker)['completed'], 5)

    def test_no_callback_rejected(self):
        mid = self.c.create('no tools')
        with self.assertRaises(ValueError): self.c.run(mid, None)
        self.assertEqual(self.c.status(mid)['completed'], 0)

    def test_bad_result_fails_closed(self):
        mid = self.c.create('bad worker')
        with self.assertRaises(ValueError): self.c.run(mid, lambda r: {'receipt':'fake'})
        self.assertEqual(self.c.status(mid)['status'], 'needs_review')
        self.assertEqual(self.c.status(mid)['completed'], 0)

    def test_state_and_limits_validated(self):
        with self.assertRaises(ValueError): self.c.create('invalid', max_cycles=0)
        with self.assertRaises(ValueError): self.c.create('invalid', max_seconds=float('nan'))
        with self.assertRaises(ValueError): self.c.create('invalid', initial_state={'n':float('nan')})
        with self.assertRaises(ValueError): self.c.create('invalid', initial_state={'n':'x'*20000})

    def test_double_completion_rejected(self):
        mid = self.c.create('idempotency')
        req = self.c._claim(mid)
        self.c._complete(req, self.worker(req))
        with self.assertRaises(RunError): self.c._complete(req, self.worker(req))
        self.assertEqual(self.c.status(mid)['completed'], 1)

    def test_clock_expired_before_second_session(self):
        mid = self.c.create('expires', max_seconds=3)
        req = self.c._claim(mid)
        self.c._complete(req, self.worker(req))
        self.clock.now += 5
        r = self.c.run(mid, self.worker)
        self.assertEqual(r['completed'], 1)
        self.assertEqual(r['status'], 'completed')


if __name__ == '__main__': unittest.main()
