# J autonomous retrieval improvements
Owner authorized code improvement on November 2, 2026.
Active scope: j_retrieval.py only. Model receives its source and a sanitized goal.
No access-control, credential, budget, deployment, or core-runtime file edits.
One automatic attempt per UTC day, up to two model calls within that attempt for a policy/syntax repair; shared Gemini usage ledger and existing request limits. Commissioning checks are recorded in the same usage ledger.
A five-minute worker checks for queued issues. It makes no model call when idle.

Before promotion: restricted AST policy, 16 frozen regression tests in a bubblewrap
sandbox, cleared environment and capabilities, private network/PID namespaces,
read-only /nix/store and staged source, no host home, secrets, live database or
host /proc mount. CPU/time/file-size limits apply; the scoring child also has a
128 MiB address-space bound. Tests and policy are not model-editable.
A frozen 12-case synthetic benchmark must strictly improve without losing any
previously passed case. A better benchmark score does not prove better results
for every real question. A source hash check stops promotion on concurrent edits.

Successful candidates receive a Git branch and commit, then fast-forward the
current branch and attempt GitHub sync. The tested source is checkpointed in the
canonical database. /autonomy displays the last result and Git commit.
Commands: /autonomy, /autonomy on, /autonomy off, /autonomy run goal.
The off command stops future builds. Prior commits remain available for rollback.
This scope is actual code generation/testing/promotion, not unrestricted self-editing.
Other code changes require extending the allowlist and its independent tests.

j_supervisor.py restarts a crashed bot with bounded backoff, stopping after six
failures in ten minutes. A host must keep that supervisor alive.
PostgreSQL advisory locking prevents duplicate owner instances in the same DB.
Before a production deployment, stop the workspace process: a distinct production
DB cannot share that advisory lock with development.

build_j.sh installs locked dependencies; start_j.sh runs the supervisor.
Deployment target required: an always-on background worker.
The current Replit Starter menu offers Autoscale/Static only. No hosting purchase
or publication was performed. Production builder operation also needs an isolated
runner provisioned on that host. It pauses when its sandbox is absent.

Records/history are preserved. No secrets are committed. Runtime markdown mirrors
and private backups are excluded from autonomous patch commits.
