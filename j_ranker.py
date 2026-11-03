"""Run validated scoring in a bounded child, with a deterministic fallback."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from j_policy import validate

WORKER=r'''
import json,sys,resource
resource.setrlimit(resource.RLIMIT_CPU,(1,1))
resource.setrlimit(resource.RLIMIT_AS,(128*1024*1024,128*1024*1024))
resource.setrlimit(resource.RLIMIT_FSIZE,(1024*1024,1024*1024))
payload=json.load(sys.stdin)
import re,math
allowed={'re':re,'math':math}
def importer(name,*args,**kwargs):
    if name not in allowed: raise ImportError('not allowed')
    return allowed[name]
import builtins
safe={name:getattr(builtins,name) for name in ['str','int','float','bool','len','min','max','sum','sorted','set','list','dict','tuple','enumerate','range','abs','round','any','all','zip']}
safe['__import__']=importer
ns={'__builtins__':safe}
exec(compile(payload['source'],'retrieval-extension','exec'),ns)
scores=[ns['score'](m,payload['query']) for m in payload['records']]
assert all(isinstance(s,(int,float)) and not isinstance(s,bool) and math.isfinite(s) and abs(s)<=1000000 for s in scores)
print(json.dumps(scores))
'''


def scores(records,query,source=None):
    source=source if source is not None else Path(__file__).with_name('j_retrieval.py').read_text()
    validate(source)
    result=subprocess.run([sys.executable,'-I','-S','-c',WORKER],input=json.dumps({'source':source,'query':query,'records':records}),text=True,capture_output=True,timeout=3,env={'PATH':'/usr/bin:/bin'},cwd='/tmp',close_fds=True)
    if result.returncode:
        raise ValueError('Scoring worker failed')
    values=json.loads(result.stdout)
    if len(values)!=len(records): raise ValueError('Score count mismatch')
    return dict(zip((m['id'] for m in records),values))
