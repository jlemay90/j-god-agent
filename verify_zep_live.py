"""Opt-in Cloud API probe. Uses new synthetic users only; never polls Telegram.

Leaves disposable remote test users in place: no deletion API is called.
Output contains checks and timings, never credentials or retrieved text.
"""
import argparse
import json
import os
import tempfile
import time
import uuid
from unittest.mock import patch


def run():
    from telegram_agent_bot import Store
    import j_zep
    result = {'kind': 'LIVE_ZEP_API_ONLY', 'sdk': '4.1.0', 'api': 'v4',
              'checks': {}, 'latency_ms': {}, 'gemini_calls': 0,
              'hosting_cost_tested': False, 'deleted_records': 0}
    marker = 'synthetic-' + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix='zep-live-isolated-') as folder:
        with patch.dict(os.environ, {'DATABASE_URL': '', 'J_ENV': 'test', 'J_DATA_DIR': folder}):
            store = Store()
            try:
                store.finalize(1, 'For this synthetic verification only, the orchard label is ' +
                               marker + '.', 'Synthetic receipt.', [], '', {},
                               conversation_key='disposable-telegram')
                started = time.monotonic()
                j_zep.process_pending(store)
                result['latency_ms']['ingestion'] = round((time.monotonic()-started)*1000)
                completed = j_zep.status(store).get('completed', 0) == 1
                result['checks']['authenticated_ingestion'] = completed
                if not completed:
                    result['error_code'] = store.setting('zep_last_error')
                    return result
                result['disposable_user_uuid'] = store.setting('zep_user_uuid')
                # Separate conversation and transport, same persisted owner.
                with store.atomic():
                    store.queue_zep_turn('hub', 'disposable-hub', 'synthetic-hub',
                                         'What is the synthetic orchard label?',
                                         'Synthetic verification request.')
                j_zep.process_pending(store)
                store.db.close()
                store = Store()
                result['checks']['restart_identity'] = (
                    store.setting('zep_user_uuid') == result['disposable_user_uuid'])
                context = ''
                started = time.monotonic()
                for _ in range(12):
                    context = j_zep.retrieve_context(store, 'What is the synthetic orchard label?')
                    if marker in context:
                        break
                    time.sleep(5)
                result['latency_ms']['recall_wait'] = round((time.monotonic()-started)*1000)
                result['checks']['new_conversation_cross_channel_api_recall'] = marker in context
                corrected = 'replacement-' + uuid.uuid4().hex[:12]
                store.finalize(
                    2, 'Correction for the synthetic orchard label: it is now ' + corrected +
                    '. The former label ' + marker + ' is obsolete and must not be used.',
                    'Synthetic correction receipt.', [], '', {},
                    conversation_key='disposable-correction')
                j_zep.process_pending(store)
                before = j_zep.status(store)
                j_zep.process_pending(store)
                result['checks']['completed_queue_not_replayed'] = before == j_zep.status(store)
                for _ in range(12):
                    context = j_zep.retrieve_context(store, 'What is the current synthetic orchard label?')
                    if corrected in context and marker not in context:
                        break
                    time.sleep(5)
                result['checks']['live_correction_freshness'] = (
                    corrected in context and marker not in context)
                # A second disposable local store must provision a separate Cloud user.
                with tempfile.TemporaryDirectory(prefix='zep-live-second-') as second_folder:
                    with patch.dict(os.environ, {'J_DATA_DIR': second_folder}):
                        other = Store()
                        try:
                            other.finalize(1, 'This isolated synthetic user prefers teal notebooks.',
                                           'Synthetic receipt.', [], '', {})
                            j_zep.process_pending(other)
                            result['checks']['distinct_user_identity'] = (
                                other.setting('zep_user_uuid') not in
                                (None, result['disposable_user_uuid']))
                            separate = j_zep.retrieve_context(other, 'What is the orchard label?')
                            result['checks']['cross_user_fact_not_returned'] = (
                                marker not in separate and corrected not in separate)
                            result['second_disposable_user_uuid'] = other.setting('zep_user_uuid')
                        finally:
                            other.db.close()
                result['queue'] = j_zep.status(store)
                result['last_error'] = store.setting('zep_last_error')
                result['notes'] = ['No Telegram/Hub UI delivery or Gemini generation tested.',
                                   'Disposable synthetic remote user retained; no real user queried.']
            finally:
                store.db.close()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', required=True,
                        help='Create a disposable synthetic Zep user using the configured key.')
    parser.parse_args()
    try:
        report = run()
        print(json.dumps(report, indent=2))
        if not report['checks'] or not all(report['checks'].values()):
            raise SystemExit(2)
    except Exception as exc:
        print(json.dumps({'kind': 'LIVE_ZEP_API_ONLY', 'error_class': type(exc).__name__}))
        raise SystemExit(1)
