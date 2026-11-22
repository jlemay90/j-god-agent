"""Private, append-only run ledger and deduplicated alert outbox.

Never put this SQLite file in the public repository. The 0600 permission
applies to the DB, not the safety of backups. No private source bodies are
stored; receipts contain evidence IDs and aggregate findings only.
"""
from __future__ import annotations
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Chicago")

class LedgerError(Exception):
    pass

class Ledger:
    def __init__(self, path: str):
        self.path = Path(path)
        if not self.path.is_absolute():
            raise LedgerError("use absolute private DB path")
        if self.path.exists() and self.path.is_symlink():
            raise LedgerError("symlink DB disallowed")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if (self.path.parent.stat().st_mode & 0o077):
            raise LedgerError("private ledger parent must not allow group/other access")
        self._init()

    def _connect(self):
        c = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        c.row_factory=sqlite3.Row
        c.execute("PRAGMA busy_timeout=5000")
        return c

    def _init(self):
        old = os.umask(0o077)
        try:
            with self._connect() as c:
                c.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                  slot TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE,
                  started_at_utc TEXT NOT NULL, finished_at_utc TEXT,
                  status TEXT NOT NULL, summary TEXT, evidence_digest TEXT);
                CREATE TABLE IF NOT EXISTS alerts (
                  key TEXT PRIMARY KEY, category TEXT NOT NULL,
                  created_at_utc TEXT NOT NULL, status TEXT NOT NULL,
                  accepted_message_id TEXT, last_attempt_utc TEXT);
                """)
        finally:
            os.umask(old)
        if self.path.stat().st_mode & 0o077:
            os.chmod(self.path,0o600)

    def claim(self, now:datetime):
        slot=now.astimezone(TZ).strftime("%Y-%m-%d")
        start=now.astimezone(timezone.utc).isoformat()
        rid=str(uuid.uuid4())
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("SELECT * FROM runs WHERE slot=?",(slot,)).fetchone()
            if row:
                c.execute("COMMIT")
                return {"claimed":False,"slot":slot,"run_id":row["run_id"],"status":row["status"]}
            c.execute("INSERT INTO runs (slot,run_id,started_at_utc,status) VALUES (?,?,?,?)",
                      (slot,rid,start,"RUNNING"))
            c.execute("COMMIT")
        return {"claimed":True,"slot":slot,"run_id":rid,"status":"RUNNING"}

    def finish(self,slot:str,run_id:str,status:str,now:datetime,summary:dict):
        if status not in {"COMPLETED","BLOCKED","FAILED"}:
            raise LedgerError("invalid terminal status")
        safe=json.dumps(summary,separators=(",",":"),sort_keys=True)
        if len(safe)>14000:
            raise LedgerError("receipt too large")
        stamp=now.astimezone(timezone.utc).isoformat()
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("SELECT run_id,status FROM runs WHERE slot=?",(slot,)).fetchone()
            if not row or row["run_id"]!=run_id or row["status"]!="RUNNING":
                c.execute("ROLLBACK")
                raise LedgerError("stale run revision")
            c.execute("UPDATE runs SET status=?,finished_at_utc=?,summary=? WHERE slot=?",
                      (status,stamp,safe,slot))
            c.execute("COMMIT")

    def latest(self):
        with self._connect() as c:
            row=c.execute("SELECT * FROM runs ORDER BY slot DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def alert_once(self,key:str,category:str,now:datetime):
        if not key or len(key)>140 or category not in {"MISSED_RUN","FAILED_RUN","IMPORTANT_FINDING","DELIVERY_FAILURE"}:
            raise LedgerError("invalid alert")
        stamp=now.astimezone(timezone.utc).isoformat()
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT OR IGNORE INTO alerts (key,category,created_at_utc,status) VALUES (?,?,?,?)",
                      (key,category,stamp,"PENDING"))
            row=c.execute("SELECT * FROM alerts WHERE key=?",(key,)).fetchone()
            c.execute("COMMIT")
        return dict(row)

    def mark_alert(self,key:str,status:str,now:datetime,message_id:str|None=None):
        if status not in {"PROVIDER_ACCEPTED","BLOCKED","FAILED"}:
            raise LedgerError("invalid alert delivery status")
        with self._connect() as c:
            c.execute("UPDATE alerts SET status=?,accepted_message_id=?,last_attempt_utc=? WHERE key=?",
                      (status,message_id,now.astimezone(timezone.utc).isoformat(),key))
            if c.total_changes!=1:
                raise LedgerError("missing alert")

    def pending_alerts(self,limit:int=10):
        with self._connect() as c:
            rows=c.execute("SELECT * FROM alerts WHERE status!='PROVIDER_ACCEPTED' ORDER BY created_at_utc LIMIT ?",(limit,)).fetchall()
        return [dict(r) for r in rows]
