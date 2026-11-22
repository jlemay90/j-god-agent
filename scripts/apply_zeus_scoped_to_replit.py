"""Apply the scoped Zeus Telegram command to a different CLEAN bot checkout.

Designed for the currently verified Replit agent/intelligence-layer baseline.
No deployments, secrets, DB operations, or network are performed here.
This intentionally refuses unknown source shapes rather than guessing.
"""
from pathlib import Path
import subprocess
import sys

def main():
    if not Path(".git").is_dir():
        sys.exit("BLOCKED: no git checkout")
    current = subprocess.check_output(["git","status","--porcelain"],text=True)
    # The downloaded helper files are allowed untracked, but existing user edits are not.
    allowed = {"?? hub_link_probe.py", "?? hub_scoped_pulse.py",
               "?? tests/", "?? scripts/",
               "?? tests/test_hub_scoped_pulse.py", "?? scripts/apply_zeus_scoped_to_replit.py"}
    unknown = [x for x in current.splitlines() if x not in allowed]
    if unknown:
        sys.exit("BLOCKED: unexpected dirty worktree, no files modified")
    if subprocess.check_output(["git","branch","--show-current"],text=True).strip() != "agent/zeus-scoped-live-20261122":
        sys.exit("BLOCKED: not on isolated test branch")

    runtime = Path("j_runtime.py")
    bot = Path("telegram_agent_bot.py")
    if not runtime.is_file() or not bot.is_file():
        sys.exit("BLOCKED: bot source missing")
    old_runtime = runtime.read_text()
    old_bot = bot.read_text()
    anchor = "    if cmd == '/hubread':\n"
    if old_runtime.count(anchor) != 1 or "if cmd == '/hublink':" in old_runtime:
        sys.exit("BLOCKED: conflicting command router")
    add = """    if cmd == '/hublink':
        from hub_scoped_pulse import readiness, report as scoped_report
        import asyncio as _asyncio
        import json as _json
        if ctx.args == ['status']:
            response = _json.dumps(readiness(), sort_keys=True)
        elif ctx.args == ['verify-scoped']:
            response = await _asyncio.to_thread(scoped_report)
        else:
            response = 'Usage: /hublink status or /hublink verify-scoped'
        await send_text(message, response)
        return True
"""
    new_runtime = old_runtime.replace(anchor, add + anchor, 1)

    import re
    expression = re.compile(r"(app\.add_handler\(CommandHandler\(\[)([^\]]+)(\])", re.S)
    match = expression.search(old_bot)
    if not match or "'hubread'" not in match.group(2) or "'hublink'" in match.group(2):
        sys.exit("BLOCKED: unexpected Telegram command registration")
    changed_list = match.group(2).replace("'hubread'", "'hubread', 'hublink'", 1)
    new_bot = old_bot[:match.start(2)] + changed_list + old_bot[match.end(2):]
    if new_bot.count("'hublink'") != 1:
        sys.exit("BLOCKED: unexpected command count")
    for path, data in ((runtime,new_runtime),(bot,new_bot)):
        path.write_text(data)
    print("SCOPED_ZEUS_COMMAND_PATCH=STAGED")
    print("FILES_MODIFIED=j_runtime.py,telegram_agent_bot.py")
    print("RUNS_READ_ONLY_UNTIL_CONFIGURED=True")
    print("NO_DEPLOYMENT_OR_CREDENTIAL_OPERATION=True")

if __name__ == "__main__":
    main()
