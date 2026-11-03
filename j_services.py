"""Run the Telegram supervisor and authenticated web transport together."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent

def main():
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.setdefault('J_ENV', 'production')
    env.setdefault('J_DAILY_TOKEN_LIMIT', '2000000')
    env.setdefault('ZEUS_BRIDGE_BIND', '0.0.0.0')
    env.setdefault('ZEUS_BRIDGE_PORT', env.get('PORT', '3000'))
    if not env.get('DATABASE_URL') or len(env.get('ZEUS_BRIDGE_SECRET', '')) < 32:
        raise SystemExit('Database and bridge signing secret must be configured.')
    # Provision additive tables once before the three services connect concurrently.
    try:
        from telegram_agent_bot import Store
        store = Store()
        store.db.close()
    except Exception:
        raise SystemExit('State storage initialization failed; no services were started.') from None
    children = []
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
        for child in children:
            if child.poll() is None:
                child.terminate()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for script in ('j_supervisor.py', 'j_web_bridge.py', 'j_zep_worker.py'):
            children.append(subprocess.Popen([sys.executable, str(ROOT / script)], cwd=ROOT, env=env))
        while not stopping:
            if any(child.poll() is not None for child in children):
                return 1
            time.sleep(0.5)
        return 0
    finally:
        stop(None, None)
        for child in children:
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()

if __name__ == '__main__':
    raise SystemExit(main())
