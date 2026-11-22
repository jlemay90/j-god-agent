"""J RUN v0.1: bounded, checkpointed mission loops with fail-closed recovery.

This is deliberately provider-independent. There is NO network, model, shell, or
payment adapter in this module. A host must inject an independently authorized
worker, and it must enforce its own per-call timeout and side-effect policies.
"""
from __future__ import annotations

import copy
import json
import math
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class RunError(RuntimeError):
    """The requested operation is unavailable or unsafe."""


@dataclass(frozen=True)
class CycleResult:
    state: dict
    receipt: str
    cost_usd: float = 0.0


@dataclass(frozen=True)
class CycleRequest:
    mission_id: str
    cycle: int
    idempotency_key: str
    state: dict


class Controller:
    def __init__(self, db_path: str | Path, clock: Callable[[], float] = time.time):
        self.clock = clock
        self.db = sqlite3.connect(str(db_path), timeout=2, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=2000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS missions (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL,
                max_cycles INTEGER NOT NULL, max_seconds REAL NOT NULL,
                max_cost_usd REAL NOT NULL, completed INTEGER NOT NULL DEFAULT 0,
                spent_usd REAL NOT NULL DEFAULT 0, state_json TEXT NOT NULL,
                created_at REAL NOT NULL, started_at REAL, deadline_at REAL,
                in_flight_token TEXT, in_flight_cycle INTEGER
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL,
                event TEXT NOT NULL, cycle INTEGER, token TEXT,
                receipt TEXT NOT NULL DEFAULT '', at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_by_mission ON events(mission_id, id);
        """)

    def close(self):
        self.db.close()

    def _event(self, mission_id, event, cycle=None, token=None, receipt=''):
        self.db.execute(
            'INSERT INTO events(mission_id,event,cycle,token,receipt,at) VALUES (?,?,?,?,?,?)',
            (mission_id, event, cycle, token, receipt, self.clock()))

    def _transaction(self, fn):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            value = fn()
            self.db.execute('COMMIT')
            return value
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def create(self, title: str, *, max_cycles: int = 5, max_seconds: float = 3600,
               max_cost_usd: float = 0.0, initial_state: dict | None = None):
        if not isinstance(title, str) or not title.strip() or len(title) > 180:
            raise ValueError('title must be 1-180 characters')
        if type(max_cycles) is not int or not 1 <= max_cycles <= 1000:
            raise ValueError('max_cycles must be an integer from 1 to 1000')
        for key, value, upper in [('max_seconds', max_seconds, 86400),
                                  ('max_cost_usd', max_cost_usd, 1000)]:
            if type(value) not in (int, float) or not math.isfinite(value) or not (0 <= value <= upper):
                raise ValueError(f'{key} must be finite and between 0 and {upper}')
        if max_seconds == 0:
            raise ValueError('max_seconds must be positive')
        state = {} if initial_state is None else initial_state
        if not isinstance(state, dict):
            raise ValueError('initial_state must be an object')
        body = json.dumps(state, allow_nan=False)
        if len(body) > 16000:
            raise ValueError('state exceeds size cap')
        mission_id = str(uuid.uuid4())
        self.db.execute('INSERT INTO missions(id,title,status,max_cycles,max_seconds,max_cost_usd,state_json,created_at) VALUES (?,?,?,?,?,?,?,?)',
                        (mission_id, title.strip(), 'ready', max_cycles, float(max_seconds), float(max_cost_usd), body, self.clock()))
        self._event(mission_id, 'created')
        return mission_id

    def status(self, mission_id: str):
        row = self.db.execute('SELECT * FROM missions WHERE id=?', (mission_id,)).fetchone()
        if row is None:
            raise RunError('unknown mission')
        data = dict(row)
        data['state'] = json.loads(data.pop('state_json'))
        return data

    def events(self, mission_id: str):
        self.status(mission_id)
        return [dict(row) for row in self.db.execute(
            'SELECT event,cycle,token,receipt,at FROM events WHERE mission_id=? ORDER BY id', (mission_id,))]

    def _claim(self, mission_id: str):
        def claim():
            mission = self.status(mission_id)
            if mission['in_flight_token']:
                raise RunError('in-flight cycle detected: do not replay; verify outcome before recovery')
            if mission['status'] != 'ready':
                return None
            now = self.clock()
            started = mission['started_at'] if mission['started_at'] is not None else now
            deadline = mission['deadline_at'] if mission['deadline_at'] is not None else started + mission['max_seconds']
            if (mission['completed'] >= mission['max_cycles'] or
                    mission['spent_usd'] >= mission['max_cost_usd'] and mission['max_cost_usd'] > 0 or
                    now >= deadline):
                self.db.execute('UPDATE missions SET status=?,started_at=?,deadline_at=? WHERE id=?',
                                ('completed', started, deadline, mission_id))
                self._event(mission_id, 'stopped_by_limit')
                return None
            token = str(uuid.uuid4())
            cycle = mission['completed'] + 1
            self.db.execute('UPDATE missions SET status=?,started_at=?,deadline_at=?,in_flight_token=?,in_flight_cycle=? WHERE id=?',
                            ('running', started, deadline, token, cycle, mission_id))
            self._event(mission_id, 'cycle_started', cycle, token)
            return CycleRequest(mission_id, cycle, token, copy.deepcopy(mission['state']))
        return self._transaction(claim)

    def _complete(self, request: CycleRequest, result: CycleResult):
        if not isinstance(result, CycleResult) or not isinstance(result.state, dict):
            raise ValueError('worker must return CycleResult with object state')
        if not isinstance(result.receipt, str) or not result.receipt.strip() or len(result.receipt) > 1000:
            raise ValueError('worker receipt must be nonempty and <=1000 characters')
        if type(result.cost_usd) not in (float, int) or not math.isfinite(result.cost_usd) or result.cost_usd < 0:
            raise ValueError('worker cost must be finite and nonnegative')
        body = json.dumps(result.state, allow_nan=False)
        if len(body) > 16000:
            raise ValueError('result state exceeds size cap')
        def commit():
            m = self.status(request.mission_id)
            if m['status'] != 'running' or m['in_flight_token'] != request.idempotency_key or m['in_flight_cycle'] != request.cycle:
                raise RunError('cycle claim changed; refuse unsafe checkpoint')
            spent = m['spent_usd'] + result.cost_usd
            reached = (request.cycle >= m['max_cycles'] or self.clock() >= m['deadline_at'] or
                       m['max_cost_usd'] > 0 and spent >= m['max_cost_usd'])
            self.db.execute('UPDATE missions SET state_json=?,completed=?,spent_usd=?,status=?,in_flight_token=NULL,in_flight_cycle=NULL WHERE id=?',
                            (body, request.cycle, spent, 'completed' if reached else 'ready', request.mission_id))
            self._event(request.mission_id, 'cycle_completed', request.cycle, request.idempotency_key, result.receipt)
            if reached:
                self._event(request.mission_id, 'stopped_by_limit')
        self._transaction(commit)

    def _block(self, request: CycleRequest, reason: str):
        def commit():
            m = self.status(request.mission_id)
            if m['status'] != 'running' or m['in_flight_token'] != request.idempotency_key:
                return
            self.db.execute('UPDATE missions SET status=? WHERE id=?', ('needs_review', request.mission_id))
            self._event(request.mission_id, 'needs_review', request.cycle, request.idempotency_key, reason)
        self._transaction(commit)

    def run(self, mission_id: str, worker: Callable[[CycleRequest], CycleResult]):
        """Run bounded cycles. No retries: uncertain external outcomes require review.

        The injected worker must impose per-call timeouts and authorization checks.
        max_seconds is verified BETWEEN cycles; no preemption of a blocked worker.
        """
        if not callable(worker):
            raise ValueError('an explicitly supplied worker callback is required')
        while True:
            request = self._claim(mission_id)
            if request is None:
                return self.status(mission_id)
            try:
                result = worker(request)
                self._complete(request, result)
            except BaseException as exc:
                self._block(request, 'Worker or checkpoint error: '+type(exc).__name__)
                raise
            if self.status(mission_id)['status'] != 'ready':
                return self.status(mission_id)

    def pause(self, mission_id: str):
        def modify():
            m = self.status(mission_id)
            if m['in_flight_token']:
                raise RunError('cannot pause in-flight action without verifying it')
            if m['status'] != 'ready':
                raise RunError('only ready missions can be paused')
            self.db.execute("UPDATE missions SET status='paused' WHERE id=?", (mission_id,))
            self._event(mission_id, 'paused')
        self._transaction(modify)

    def resume(self, mission_id: str):
        def modify():
            m = self.status(mission_id)
            if m['in_flight_token']:
                raise RunError('cannot resume an in-flight action without external outcome verification')
            if m['status'] != 'paused':
                raise RunError('only paused missions can resume')
            self.db.execute("UPDATE missions SET status='ready' WHERE id=?", (mission_id,))
            self._event(mission_id, 'resumed')
        self._transaction(modify)

    def mark_interrupted_for_review(self, mission_id: str):
        """Only call after verifying the original worker has actually stopped."""
        def modify():
            m = self.status(mission_id)
            if m['status'] != 'running' or not m['in_flight_token']:
                raise RunError('no in-flight cycle')
            self.db.execute("UPDATE missions SET status='needs_review' WHERE id=?", (mission_id,))
            self._event(mission_id, 'interrupted_needs_review', m['in_flight_cycle'], m['in_flight_token'])
        self._transaction(modify)

    def resolve_interrupted(self, mission_id: str, *, outcome: str, receipt: str,
                            verified_state: dict | None = None, verified_cost_usd: float = 0.0):
        """Reconcile an interrupted cycle using an *external* outcome receipt.

        `no_effect` permits a new attempt ONLY after proving no outside action
        occurred. `completed` counts the previously in-flight cycle and stores
        its independently verified resulting state, avoiding a duplicate call.
        Never call based solely on an AI guess or a stale status read.
        """
        if outcome not in ('no_effect', 'completed'):
            raise ValueError('outcome must be no_effect or completed')
        if not isinstance(receipt, str) or not receipt.strip() or len(receipt) > 1000:
            raise ValueError('external verification receipt required')
        if outcome == 'completed':
            if not isinstance(verified_state, dict):
                raise ValueError('verified_state is required for a completed external action')
            body = json.dumps(verified_state, allow_nan=False)
            if len(body) > 16000:
                raise ValueError('verified_state exceeds size cap')
            if type(verified_cost_usd) not in (int, float) or not math.isfinite(verified_cost_usd) or verified_cost_usd < 0:
                raise ValueError('verified_cost_usd must be finite and nonnegative')
        def modify():
            m = self.status(mission_id)
            if m['status'] != 'needs_review' or not m['in_flight_token']:
                raise RunError('no interrupted cycle awaiting review')
            if outcome == 'no_effect':
                self.db.execute("UPDATE missions SET status='ready',in_flight_token=NULL,in_flight_cycle=NULL WHERE id=?", (mission_id,))
                self._event(mission_id, 'interruption_verified_no_effect', m['in_flight_cycle'], m['in_flight_token'], receipt)
            else:
                count = m['in_flight_cycle']
                spent = m['spent_usd'] + verified_cost_usd
                reached = (count >= m['max_cycles'] or self.clock() >= m['deadline_at'] or
                           m['max_cost_usd'] > 0 and spent >= m['max_cost_usd'])
                self.db.execute('UPDATE missions SET status=?,completed=?,spent_usd=?,state_json=?,in_flight_token=NULL,in_flight_cycle=NULL WHERE id=?',
                                ('completed' if reached else 'ready', count, spent, body, mission_id))
                self._event(mission_id, 'interruption_verified_completed', count, m['in_flight_token'], receipt)
        self._transaction(modify)
