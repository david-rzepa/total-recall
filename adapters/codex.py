"""Discover the exact CLI session from its open transcript; ambiguity fails closed."""
import json
from pathlib import Path
import uuid

ID = 'codex'
PRIORITY = 50

def capture(ctx):
    if ctx['executable'] != 'foot' or any(p['name'] == 'herdr' for p in ctx['processes']):
        return None
    sessions = {}
    for p in ctx['processes']:
        if p['name'] != 'codex':
            continue
        try:
            fds = list(Path('/proc', str(p['pid']), 'fd').iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                path = fd.resolve()
                if not path.name.startswith('rollout-') or path.suffix != '.jsonl':
                    continue
                with path.open() as f:
                    event = json.loads(f.readline())
                meta = event.get('payload', {})
                if event.get('type') != 'session_meta' or meta.get('source') != 'cli':
                    continue
                sid = str(uuid.UUID(meta['id']))
                sessions[sid] = p['cwd']
            except (OSError, ValueError, KeyError):
                continue
    if len(sessions) != 1:
        return None
    sid, cwd = next(iter(sessions.items()))
    return dict(identity='codex:' + sid, state={'session': sid, 'cwd': cwd},
                label='Codex · ' + sid, coverage='limited',
                detail='Resumes the conversation; typed input and launch flags are not restored.')

def restore(state):
    return ['codex', 'resume', str(uuid.UUID(state['session']))]
