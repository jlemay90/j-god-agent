"""Safe local demonstration CLI. NEVER invokes an AI or outside system."""
import argparse
import json
from . import Controller, CycleResult


def demo_worker(req):
    state = dict(req.state)
    state['observed_cycles'] = [*state.get('observed_cycles', []), req.cycle]
    return CycleResult(state, receipt=f'demo cycle {req.cycle}: deterministic local checkpoint')


def main():
    ap = argparse.ArgumentParser(description='J RUN v0.1: local checkpoint demonstration')
    ap.add_argument('--db', required=True, help='SQLite file; do not commit private state')
    subs = ap.add_subparsers(dest='command', required=True)
    d = subs.add_parser('demo', help='create and execute isolated deterministic cycles')
    d.add_argument('--cycles', type=int, default=5)
    d.add_argument('--seconds', type=float, default=3600)
    s = subs.add_parser('status', help='show local mission status')
    s.add_argument('id')
    args = ap.parse_args()
    controller = Controller(args.db)
    try:
        if args.command == 'demo':
            mid = controller.create('Local controller acceptance test', max_cycles=args.cycles, max_seconds=args.seconds)
            result = controller.run(mid, demo_worker)
        else:
            result = controller.status(args.id)
        print(json.dumps(result, indent=2, sort_keys=True))
    finally:
        controller.close()


if __name__ == '__main__':
    main()
