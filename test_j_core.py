"""Synthetic tests: no secrets, model calls or live database changes."""
import ast
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from j_core import upgrade_store, LimitReached, redact_secret

ROOT=Path(__file__).parent
# Extract the legacy Store definition without importing provider SDKs.
tree=ast.parse((ROOT/'telegram_agent_bot.py').read_text())
node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Store')
ns={'os':os,'sqlite3':sqlite3,'Path':Path,'ROOT':ROOT}
exec(compile(ast.Module(body=[node],type_ignores=[]),'Store','exec'),ns)
State=upgrade_store(ns['Store'])

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old={k:os.environ.get(k) for k in ('J_DATA_DIR','J_ENV','DATABASE_URL')}
        os.environ['J_DATA_DIR']=self.temp.name
        os.environ.pop('J_ENV',None); os.environ.pop('DATABASE_URL',None)
        self.store=State()
    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()
        for k,v in self.old.items():
            if v is None: os.environ.pop(k,None)
            else: os.environ[k]=v
    def change(self,**values):
        c=dict(kind='preference',key='answer length',value='Short answers',explicit=True,status='active')
        c.update(values); return c
    def test_recall_after_unrelated_turns_and_restart(self):
        self.store.finalize(1,'Keep answers short','ok',[self.change()],'',{})
        for i in range(2,18): self.store.finalize(i,'unrelated test','ok',[],'',{})
        self.assertEqual(self.store.relevant('How should you answer?')[0]['value'],'Short answers')
        self.store.db.close(); self.store=State()
        self.assertEqual(len(self.store.memory_rows()),1)
    def test_correction_supersedes(self):
        self.store.finalize(1,'short','ok',[self.change()],'',{})
        old=self.store.memory_rows()[0]['id']
        self.store.finalize(2,'detailed','ok',[self.change(value='Detailed answers',target_id=old)],'',{})
        self.assertEqual(len(self.store.memory_rows()),1)
        self.assertEqual(self.store.memory_rows()[0]['value'],'Detailed answers')
        self.assertEqual(len(self.store.memory_rows(True)),2)
    def test_replay_does_not_duplicate_rule_or_memory(self):
        for _ in range(2): self.store.finalize(1,'short','ok',[self.change()],'Be concise',{})
        self.assertEqual(self.store.directive()[0],2)
        self.assertEqual(len(self.store.memory_rows()),1)
    def test_transaction_failure_rolls_back_all_writes(self):
        with self.assertRaises(TypeError): self.store.finalize(1,'short','ok',[self.change()],'Be concise',{'bad':object()})
        self.assertFalse(self.store.seen(1))
        self.assertEqual(self.store.directive()[0],1)
        self.assertEqual(len(self.store.memory_rows()),0)
    def test_inference_not_stored(self):
        self.store.finalize(1,'maybe','ok',[self.change(kind='commitment',explicit=False)],'',{})
        self.assertEqual(self.store.memory_rows(),[])
    def test_delete_correction_chain(self):
        self.store.finalize(1,'short','ok',[self.change()],'',{})
        self.store.finalize(2,'long','ok',[self.change(value='Long answers')],'',{})
        self.store.forget_memory(self.store.memory_rows()[0]['id'])
        self.assertEqual(self.store.memory_rows(True),[])
    def test_call_cap_and_actual_usage(self):
        identity=self.store.reserve_call('test','response',daily_requests=1)
        meta=SimpleNamespace(prompt_token_count=100,candidates_token_count=20,thoughts_token_count=10,total_token_count=130)
        self.store.finish_call(identity,meta,'completed',12)
        with self.assertRaises(LimitReached): self.store.reserve_call('test','response',daily_requests=1)
        self.assertEqual(self.store.usage_summary()['total_tokens_recorded'],130)
        self.assertAlmostEqual(self.store.usage_summary()['estimated_usd_recorded'],.00007)
    def test_unknown_usage_blocks_new_calls(self):
        identity=self.store.reserve_call('test','response')
        self.store.finish_call(identity,None,'failed',12)
        with self.assertRaises(LimitReached): self.store.reserve_call('test','response')
        self.assertEqual(self.store.usage_summary()['calls_with_unknown_usage'],1)
    def test_token_threshold(self):
        identity=self.store.reserve_call('test','response')
        self.store.finish_call(identity,SimpleNamespace(prompt_token_count=10,candidates_token_count=5,thoughts_token_count=0,total_token_count=15),'completed',1)
        with self.assertRaises(LimitReached): self.store.reserve_call('test','response',daily_tokens=15)
    def test_directive_install_idempotent(self):
        self.store.install_directive('Continuity v5'); self.store.install_directive('Continuity v5')
        self.assertEqual(self.store.directive()[0],2)
    def test_secret_patterns(self):
        self.assertTrue(redact_secret('AIza'+'a'*35))
        self.assertTrue(redact_secret('123456789:'+'x'*35))
        self.assertFalse(redact_secret('ordinary user text'))

if __name__=='__main__': unittest.main()
