import asyncio
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from telegram_agent_bot import Store, Turn
from j_context import setup, recall, report, supplied_context, direct_read
from j_runtime import handle_turn, extra_command
from j_tools import requested_tools


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'DATABASE_URL':'', 'J_ENV':'test',
            'J_DATA_DIR':self.temp.name, 'GEMINI_MODEL':'test-model'})
        self.env.start()
        self.s = Store()

    def tearDown(self):
        self.s.db.close()
        self.env.stop()
        self.temp.cleanup()

    def add(self, i, text):
        self.s.finalize(i, text, 'Reference reply', [], '', {})

    def test_archive_survives_recent_window_and_reopen(self):
        for i in range(105):
            self.add(i, 'orchard project decision' if i == 0 else 'ordinary turn')
        self.assertEqual(self.s.execute('SELECT COUNT(*) FROM turns').fetchone()[0], 100)
        self.assertEqual(recall(self.s, 'orchard')[0]['update_id'], 0)
        self.s.db.close()
        self.s = Store()
        self.assertEqual(recall(self.s, 'orchard')[0]['update_id'], 0)

    def test_migration_idempotent_and_no_fake_dates(self):
        self.s.execute('INSERT INTO turns VALUES (?,?,?)', (999, 'legacy topic', 'legacy answer'))
        setup(self.s)
        setup(self.s)
        hits = recall(self.s, 'legacy')
        self.assertEqual(len(hits), 1)
        self.assertIsNone(hits[0]['captured_at_utc'])

    def test_recall_is_bounded_reference_not_sql(self):
        for i in range(9): self.add(i, 'orchard ' + 'x' * 4000)
        hits = recall(self.s, "orchard' OR 1=1 --", max_chars=1500)
        self.assertLessEqual(len(json.dumps(hits)), 1510)
        self.assertTrue(all(h['reference_only'] for h in hits))
        self.assertEqual(self.s.execute('SELECT COUNT(*) FROM conversation_archive').fetchone()[0], 9)

    def test_live_usage_and_access_inventory(self):
        self.s.reserve_call('test-model', 'test')
        data = supplied_context(self.s, 'what tools can you use?')
        self.assertEqual(data['usage_today']['calls'], 1)
        self.assertTrue(data['usage_today']['cost_estimate_incomplete'])
        self.assertIn('recall', data['callable_tools'])
        self.assertTrue(all(r['status'] in ('not_connected','reference_only','connected_via_workspace_git') for r in data['external_resources']))
        self.assertIn('unknown', report(self.s, 'usage'))

    def test_direct_read_routes_only_clear_requests(self):
        self.assertEqual(direct_read('How much have we used today? Give me uncertainty.'), ('usage',''))
        self.assertEqual(direct_read('Show me your status'), ('status',''))
        self.assertEqual(direct_read('Recall orchard'), ('recall','orchard'))
        self.assertIsNone(direct_read('For example: how much have we used today?'))
        self.assertIsNone(direct_read('"How much have we used today?"'))
        self.assertIsNone(direct_read('Maybe show me reminders later'))

    def test_direct_inspection_does_not_call_model(self):
        sent=[]
        async def generate(*a, **k): raise AssertionError('No model call expected')
        async def send(message,text): sent.append(text)
        async def reply(text): sent.append(text)
        update=NS(update_id=22,effective_message=NS(text='How much have we used today?',voice=None,reply_text=reply),effective_chat=NS(id=1))
        ctx=NS(bot_data={'store':self.s,'started':time.monotonic()})
        asyncio.run(handle_turn(update,ctx,owner=lambda *a:True,send_text=send,
            generate=generate,mirror=lambda s:True,speak=None,Turn=Turn))
        self.assertIn('Model calls:',sent[0])
        self.assertEqual(self.s.usage_summary()['calls'],0)

    def test_model_receives_current_context_and_historical_source(self):
        self.add(10, 'orchard decision')
        captured, sent = [], []
        async def generate(ctx, contents, **kwargs):
            captured.append(json.loads(contents))
            return NS(text=json.dumps(dict(reply='ok', explicit_rule_request=False,
                rule='', needs_clarification=False)))
        async def send(message, text): sent.append(text)
        async def reply(text): sent.append(text)
        message=NS(text='What was the orchard decision?',voice=None,reply_text=reply)
        update=NS(update_id=11,effective_message=message,effective_chat=NS(id=1))
        ctx=NS(bot_data={'store':self.s,'started':time.monotonic()})
        asyncio.run(handle_turn(update,ctx,owner=lambda *a:True,send_text=send,
            generate=generate,mirror=lambda s:True,speak=None,Turn=Turn))
        self.assertEqual(sent, ['ok'])
        data=captured[0]['application_context']
        self.assertEqual(data['model'], 'test-model')
        self.assertEqual(data['relevant_past_turns'][0]['update_id'],10)

    def test_inspection_commands_and_tool_require_evidence(self):
        async def run():
            output=[]
            async def send(message,text): output.append(text)
            ctx=NS(bot_data={'store':self.s,'started':time.monotonic()},args=[])
            update=NS(effective_message=NS(text='/usage'),effective_chat=NS(id=1))
            self.assertTrue(await extra_command(update,ctx,send))
            self.assertIn('Model calls:',output[0])
            bad=NS(tool='inspect',argument='usage',explicit=True,evidence='missing')
            self.assertEqual(await requested_tools([bad],'usage please',update,ctx),('',[]))
            good=NS(tool='inspect',argument='usage',explicit=True,evidence='usage')
            result,actions=await requested_tools([good],'usage please',update,ctx)
            self.assertIn('Model calls:',result)
            self.assertEqual(actions,['inspect'])
        asyncio.run(run())

    def test_zep_context_survives_tool_reasoning_and_reply_is_durably_delivered(self):
        captured, sent = [], []
        async def generate(ctx, contents, **kwargs):
            captured.append(json.loads(contents))
            tools = [dict(tool='calculate', argument='2+2', explicit=True,
                          evidence='calculate')] if len(captured) == 1 else []
            return NS(text=json.dumps(dict(reply='The answer is 4.', tool_requests=tools,
                explicit_rule_request=False, rule='', needs_clarification=False)))
        async def send(message, text): sent.append(text)
        async def reply(text): sent.append(text)
        update = NS(update_id=900, effective_chat=NS(id=1), effective_message=NS(
            text='Please calculate 2+2', voice=None, reply_text=reply))
        ctx = NS(bot_data={'store':self.s, 'started':time.monotonic()})
        with patch('j_runtime.retrieve_context_async', return_value='Synthetic historical reference'):
            asyncio.run(handle_turn(update,ctx,owner=lambda *a:True,send_text=send,
                generate=generate,mirror=lambda s:True,speak=None,Turn=Turn))
        self.assertEqual(len(captured), 2)
        self.assertTrue(all(c['zep_reference_context'] == 'Synthetic historical reference'
                            for c in captured))
        self.assertIn('4', captured[1]['tool_observations'][0]['result'])
        self.assertEqual(sent, ['The answer is 4.'])
        self.assertTrue(self.s.seen(900))
        self.assertEqual(self.s.execute('SELECT COUNT(*) FROM reply_outbox').fetchone()[0], 0)
        self.assertEqual(self.s.execute('SELECT COUNT(*) FROM zep_ingestion').fetchone()[0], 1)

    def test_forget_command_clears_archive_with_recent_history(self):
        from telegram_agent_bot import command
        self.add(1, 'orchard')
        sent=[]
        async def reply(text): sent.append(text)
        update=NS(effective_message=NS(text='/forget confirm',reply_text=reply),
                  effective_user=NS(id=1), effective_chat=NS(id=1,type='private'))
        ctx=NS(bot_data={'store':self.s,'owner_id':1},args=['confirm'])
        asyncio.run(command(update,ctx))
        self.assertEqual(self.s.execute('SELECT COUNT(*) FROM conversation_archive').fetchone()[0],0)
        self.assertEqual(self.s.execute('SELECT COUNT(*) FROM turns').fetchone()[0],0)
        self.assertTrue(sent)


if __name__ == '__main__': unittest.main()
