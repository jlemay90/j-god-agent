"""Restart a single bot child with backoff; exit after repeated failures.

A host service must keep this supervisor alive. This is not 24/7 hosting itself.
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
child=None
stopping=False

def stop(signum,frame):
    global stopping
    stopping=True
    if child and child.poll() is None: child.terminate()


def main():
    global child
    signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
    failures=[]
    delay=2
    env=os.environ.copy(); env.pop('PYTHONPATH',None)
    while not stopping:
        started=time.monotonic()
        child=subprocess.Popen([sys.executable,str(ROOT/'telegram_agent_bot.py')],cwd=ROOT,env=env)
        code=child.wait()
        if stopping or code==0: break
        now=time.monotonic()
        failures=[t for t in failures if now-t<600]+[now]
        if len(failures)>=6:
            print('J supervisor stopped after six failed starts in ten minutes.',flush=True)
            return 1
        print('J child exited; restarting after bounded backoff.',flush=True)
        if now-started>300: delay=2
        for _ in range(delay):
            if stopping: return 0
            time.sleep(1)
        delay=min(delay*2,60)
    return 0

if __name__=='__main__': raise SystemExit(main())
