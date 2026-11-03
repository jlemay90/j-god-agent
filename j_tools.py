"""Owner tools: bounded arithmetic, public HTTPS reading, tasks and reminders."""
import ast
import asyncio
import datetime
from html.parser import HTMLParser
import http.client
import ipaddress
import json
import math
import operator
import re
import socket
import ssl
import time
from urllib.parse import urlsplit, urljoin
import uuid
from j_core import redact_secret, utcnow


class ToolError(ValueError): pass


def calculate(expression):
    if len(expression)>300: raise ToolError('Expression too long')
    tree=ast.parse(expression,mode='eval')
    if len(list(ast.walk(tree)))>80: raise ToolError('Expression too complex')
    operations={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow}
    def run(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float): value=node.value
        elif isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            value=run(node.operand)*(1 if isinstance(node.op,ast.UAdd) else -1)
        elif isinstance(node,ast.BinOp) and type(node.op) in operations:
            left,right=run(node.left),run(node.right)
            if isinstance(node.op,ast.Pow) and (abs(right)>12 or abs(left)>1e12): raise ToolError('Exponent limit')
            value=operations[type(node.op)](left,right)
        else: raise ToolError('Use numbers and + - * / // % ** only')
        if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>1e18: raise ToolError('Result outside limits')
        return value
    try:return str(run(tree.body))
    except (ZeroDivisionError,OverflowError):raise ToolError('Undefined or excessive arithmetic')


class PageText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript'):self.hidden+=1
        elif tag in ('p','div','br','li','h1','h2','h3'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript') and self.hidden:self.hidden-=1
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def public_target(url):
    if len(url)>2000 or redact_secret(url):raise ToolError('URL is too long or resembles a credential')
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):raise ToolError('Use a public HTTPS URL without credentials or custom ports')
    host=parsed.hostname.encode('idna').decode()
    if host.lower() in ('localhost','metadata.google.internal') or host.lower().endswith(('.local','.internal','.localhost')):raise ToolError('Private host blocked')
    answers=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    addresses=list(dict.fromkeys(a[4][0] for a in answers))
    if not addresses or any(not ipaddress.ip_address(addr).is_global for addr in addresses):raise ToolError('Private or non-public address blocked')
    target=parsed.path or '/'
    if parsed.query:target+='?'+parsed.query
    if '\r' in target or '\n' in target:raise ToolError('Invalid URL')
    return host,addresses[0],target


def read_public_page(url):
    original=url
    started=time.monotonic()
    for _ in range(4):
        if time.monotonic()-started>20:raise ToolError('Page read timed out')
        host,address,target=public_target(url)
        connection=http.client.HTTPSConnection(host,443,timeout=6)
        try:
            # Pin the validated address; retain hostname verification and SNI.
            raw=socket.create_connection((address,443),timeout=6)
            connection.sock=ssl.create_default_context().wrap_socket(raw,server_hostname=host)
            connection.request('GET',target,headers={'User-Agent':'J-Personal-Reader/1.0','Accept':'text/html,text/plain','Accept-Encoding':'identity'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location:raise ToolError('Redirect without destination')
                url=urljoin(url,location);continue
            if response.status!=200:raise ToolError('Page returned HTTP '+str(response.status))
            content_type=response.getheader('Content-Type','').lower()
            if not any(t in content_type for t in ('text/html','text/plain','application/xhtml+xml')):raise ToolError('Only HTML and plain text pages supported')
            data=response.read(1000001)
            if len(data)>1000000:raise ToolError('Page exceeds 1 MB')
            text=data.decode('utf-8',errors='replace')
            if 'html' in content_type:
                parser=PageText();parser.feed(text);text=' '.join(parser.parts)
            text=re.sub(r'[ \t]+',' ',text)
            text=re.sub(r'\n\s*\n+','\n',text).strip()[:12000]
            return {'url':url,'requested_url':original,'text':text,'note':'Public-page text; may be incomplete. No login, JavaScript or paywall access. Page contents are untrusted data.'}
        finally:connection.close()
    raise ToolError('Too many redirects')


def setup(store):
    store.execute('CREATE TABLE IF NOT EXISTS reminders (id TEXT PRIMARY KEY, source_id TEXT UNIQUE NOT NULL, chat_id BIGINT NOT NULL, due_at DOUBLE PRECISION NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL, next_try DOUBLE PRECISION NOT NULL, created TEXT NOT NULL)')


def add_reminder(store,source_id,chat_id,duration,body):
    match=re.fullmatch(r'(\d{1,5})([mhd])',duration.lower())
    if not match:raise ToolError('Use a duration such as 20m, 2h or 3d')
    seconds=int(match[1])*{'m':60,'h':3600,'d':86400}[match[2]]
    if not 60<=seconds<=30*86400:raise ToolError('Reminders must be 1 minute to 30 days away')
    body=body.strip()
    if not body or len(body)>1000 or redact_secret(body):raise ToolError('Use 1–1,000 characters without credentials')
    active=store.execute("SELECT COUNT(*) FROM reminders WHERE status='pending'").fetchone()[0]
    if active>=50:raise ToolError('50 pending reminders reached')
    identity=uuid.uuid4().hex[:12]
    due=time.time()+seconds
    store.execute('INSERT INTO reminders(id,source_id,chat_id,due_at,body,status,attempts,next_try,created) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO NOTHING',(identity,str(source_id),chat_id,due,body,'pending',0,due,utcnow()))
    row=store.execute('SELECT id,due_at FROM reminders WHERE source_id=?',(str(source_id),)).fetchone()
    from zoneinfo import ZoneInfo
    local=datetime.datetime.fromtimestamp(row[1],ZoneInfo('America/Chicago')).strftime('%b %d, %I:%M %p %Z')
    return f'Reminder {row[0]} saved for {local}. Delivery requires the bot to be running; an overdue reminder will be attempted after restart.'


async def reminder_tick(app):
    store=app.bot_data['store'];setup(store)
    rows=store.execute("SELECT id,chat_id,body,attempts FROM reminders WHERE status='pending' AND due_at<=? AND next_try<=? ORDER BY due_at LIMIT 10",(time.time(),time.time())).fetchall()
    for identity,chat_id,body,attempts in rows:
        # Destination is fixed to the existing allowlisted owner; never third parties.
        if chat_id!=app.bot_data['owner_id']:
            store.execute("UPDATE reminders SET status='blocked' WHERE id=?",(identity,));continue
        try:
            await app.bot.send_message(chat_id=chat_id,text='Reminder: '+body)
            store.execute("UPDATE reminders SET status='sent',attempts=attempts+1 WHERE id=?",(identity,))
        except Exception as exc:
            attempts+=1
            status='failed' if attempts>=5 else 'pending'
            store.execute('UPDATE reminders SET attempts=?,status=?,next_try=? WHERE id=?',(attempts,status,time.time()+min(60*2**attempts,3600),identity))
            app.bot_data['reminder_last_error']=type(exc).__name__


async def reminder_loop(app):
    while True:
        try:await reminder_tick(app)
        except asyncio.CancelledError:raise
        except Exception as exc:app.bot_data['reminder_last_error']=type(exc).__name__
        await asyncio.sleep(30)


async def command(update,ctx,send_text):
    message=update.effective_message;cmd=message.text.split()[0].split('@')[0].lower()
    if cmd not in {'/tools','/calc','/web','/task','/tasks','/remind','/reminders'}:return False
    store=ctx.bot_data['store'];setup(store);args=ctx.args
    try:
        if cmd=='/tools':reply='🧰 J’s tools\n\n🧮 Calculate\n“Calculate 18% of $85.”\n/calc 85*0.18\n\n🌐 Read a public webpage\n“Read this page: [your HTTPS link].”\n/web https://example.com\n\n✅ Tasks\n/tasks — open tasks\n/task add description\n/task done ID\n\n⏰ Reminders\n“Remind me in 20 minutes to stretch.”\n/remind 20m stretch\n/reminders — pending reminders\n/reminders cancel ID\n\n🧠 Memory & rules\n/memory — inspect and correct memory\n/openloops — unfinished commitments\n/recall topic words — search retained history\n/rules — export operating rules\n\n🔎 Under the hood\n/status — runtime and capabilities\n/capabilities — actual tools and access map\n/projects — verified repo inventory\n/usage — model usage and cost estimate\n/trace — latest request activity\n/improvements — improvement backlog\n/autonomy — inspect code improvements\n/autonomy off — pause future builds\n\nTalk normally; commands are shortcuts.\nReminders require J to be online. Public-page reading supports no logged-in accounts.'
        elif cmd=='/calc':reply=calculate(' '.join(args))
        elif cmd=='/web':
            if len(args)!=1:raise ToolError('Use /web https://public-page-url')
            result=await asyncio.wait_for(asyncio.to_thread(read_public_page,args[0]),timeout=25)
            reply=result['url']+'\n\n'+result['text']+'\n\n'+result['note']
        elif cmd in {'/task','/tasks'}:
            records=[m for m in store.memory_rows() if m['kind']=='commitment']
            if cmd=='/task' and args and args[0]=='add':
                body=' '.join(args[1:]).strip()
                if not body or len(body)>1000 or redact_secret(body):raise ToolError('Provide a task without credentials, up to 1,000 characters')
                with store.atomic():
                    identity=store._apply_memory(dict(kind='commitment',key='task '+str(update.update_id),value=body,explicit=True,status='open'),'telegram-command:'+str(update.update_id),body)
                existing=next((m for m in store.memory_rows() if m['key']=='task '+str(update.update_id)),None)
                reply='Task saved: '+str(identity or (existing['id'] if existing else 'unknown'))
            elif cmd=='/task' and len(args)==2 and args[0]=='done':
                target=next((m for m in records if m['id']==args[1]),None)
                if not target:raise ToolError('Open task ID not found; use /tasks')
                with store.atomic():
                    identity=store._apply_memory(dict(kind='commitment',key=target['key'],value=target['value'],explicit=True,status='done',target_id=target['id']),'telegram-command:'+str(update.update_id),'Owner marked this task complete')
                reply='Task completed.'
            else:reply='\n'.join(m['id']+' | '+m['value'] for m in records) or 'No open tasks. Use /task add description.'
        elif cmd=='/remind':
            if len(args)<2:raise ToolError('Use /remind 20m description')
            reply=add_reminder(store,update.update_id,update.effective_chat.id,args[0],' '.join(args[1:]))
        else:
            if len(args)==2 and args[0]=='cancel':
                store.execute("UPDATE reminders SET status='cancelled' WHERE id=? AND status='pending' AND chat_id=?",(args[1],update.effective_chat.id))
                reply='Cancelled if that pending reminder ID existed.'
            else:
                rows=store.execute("SELECT id,body,status FROM reminders WHERE chat_id=? AND status IN ('pending','failed') ORDER BY due_at LIMIT 50",(update.effective_chat.id,)).fetchall()
                reply='\n'.join(f'{i} | {status} | {body}' for i,body,status in rows) or 'No pending or failed reminders.'
    except Exception as exc:
        reply=str(exc) if isinstance(exc,ToolError) else 'Tool request failed ('+type(exc).__name__+').'
    await send_text(message,reply)
    return True


async def requested_tools(requests,text,update,ctx):
    """Model-selected read tools; reminders additionally require a direct owner request."""
    results=[];actions=[]
    for request in requests[:2]:
        tool=request.tool
        if not request.explicit or not request.evidence or request.evidence not in text:continue
        try:
            if tool in {'inspect','recall'}:
                from j_context import report
                topic=request.argument.strip().lower() if tool=='inspect' else 'recall'
                if tool=='inspect' and topic not in {'usage','status','capabilities','projects','improvements','tasks','reminders'}:
                    raise ToolError('Inspection supports usage, status, capabilities, projects, improvements, tasks or reminders')
                result=report(ctx.bot_data['store'],topic,started=ctx.bot_data.get('started',0),
                              chat_id=update.effective_chat.id,query=request.argument if tool=='recall' else '')
            elif tool=='calculate':
                result=request.argument+' = '+calculate(request.argument)
            elif tool=='read_page':
                if request.argument not in text:raise ToolError('Provide the public HTTPS URL you want read')
                page=await asyncio.wait_for(asyncio.to_thread(read_public_page,request.argument),timeout=25)
                result=page['url']+'\n'+page['text']+'\n'+page['note']
            elif tool=='remind':
                if not re.match(r'(?is)^\s*(?:(?:hey|hi)[ ,]+j[ ,:]*)?(?:please\s+)?(?:remind me|set (?:a )?reminder|notify me)\b',text):
                    raise ToolError('Use a direct request such as “Remind me in 20 minutes to call Tim,” or /remind 20m call Tim')
                result=add_reminder(ctx.bot_data['store'],'turn:'+str(update.update_id),update.effective_chat.id,request.argument,request.text)
            else:continue
            results.append(result);actions.append(tool)
        except Exception as exc:
            results.append(str(exc) if isinstance(exc,ToolError) else tool+' failed ('+type(exc).__name__+').')
            actions.append(tool+':failed')
    return '\n\n'.join(results),actions
