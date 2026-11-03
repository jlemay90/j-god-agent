"""One supervised ingestion worker shared by the Telegram and Hub transports."""
import logging
import time

from j_zep import process_pending, recover


def main():
    from telegram_agent_bot import Store
    for name in ('httpx', 'httpcore', 'zep_cloud'):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    store = Store()
    lock_file = None
    try:
        if store.pg:
            if not store.execute('SELECT pg_try_advisory_lock(?)', (847102039,)).fetchone()[0]:
                raise RuntimeError('Another memory ingestion worker is running')
        else:
            import fcntl
            from pathlib import Path
            db_path = store.execute('PRAGMA database_list').fetchone()[2]
            lock_file = open(Path(db_path).with_suffix('.zep.lock'), 'a')
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        recover(store)
        while True:
            count = process_pending(store)
            time.sleep(1 if count else 5)
    except Exception:
        # Let the service supervisor restart infrastructure failures. No raw error text.
        raise SystemExit('Memory ingestion worker unavailable; durable work remains queued.') from None
    finally:
        store.db.close()
        if lock_file:
            lock_file.close()


if __name__ == '__main__':
    main()
