import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from j_tools import calculate,ToolError,public_target,add_reminder,setup,reminder_tick
import test_j_core as core_tests

class ToolUnitTests(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(calculate('(40+10)*1.1'),'55.00000000000001')
        self.assertEqual(calculate('2**3+5'),'13')
    def test_arbitrary_code_rejected(self):
        for text in ['__import__("os").system("x")','10**100000','[1]*99999','(1).__class__','True+1']:
            with self.assertRaises((ToolError,SyntaxError)):calculate(text)
    def test_private_targets_blocked(self):
        for url in ['http://example.com','https://localhost','https://user:pass@example.com','https://example.com:444']:
            with self.assertRaises(ToolError):public_target(url)
        with patch('j_tools.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ToolError):public_target('https://public-looking.example')

class ReminderTests(unittest.TestCase):
    setUp=core_tests.CoreTests.setUp
    tearDown=core_tests.CoreTests.tearDown
    def test_reminder_dedup_and_delivery(self):
        setup(self.store)
        add_reminder(self.store,'source',777,'1m','synthetic reminder')
        add_reminder(self.store,'source',777,'1m','synthetic reminder')
        self.assertEqual(self.store.execute('SELECT COUNT(*) FROM reminders').fetchone()[0],1)
        self.store.execute('UPDATE reminders SET next_try=0,due_at=0')
        delivered=[]
        async def send_message(**args):delivered.append(args)
        app=SimpleNamespace(bot_data={'store':self.store,'owner_id':777},bot=SimpleNamespace(send_message=send_message))
        asyncio.run(reminder_tick(app));asyncio.run(reminder_tick(app))
        self.assertEqual(len(delivered),1)
        self.assertEqual(self.store.execute('SELECT status FROM reminders').fetchone()[0],'sent')
    def test_other_recipient_blocked(self):
        setup(self.store)
        add_reminder(self.store,'source',888,'1m','synthetic reminder')
        self.store.execute('UPDATE reminders SET next_try=0,due_at=0')
        async def send_message(**args):raise AssertionError('Unauthorized destination')
        app=SimpleNamespace(bot_data={'store':self.store,'owner_id':777},bot=SimpleNamespace(send_message=send_message))
        asyncio.run(reminder_tick(app))
        self.assertEqual(self.store.execute('SELECT status FROM reminders').fetchone()[0],'blocked')
