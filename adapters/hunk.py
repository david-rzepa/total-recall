"""Live revision capture. PR identity comes from the launcher's session metadata."""
import json
from pathlib import Path
import re

ID = 'hunk'
PRIORITY = 60

def capture(ctx):
    if ctx['executable'] != 'foot' or any(p['name'] == 'herdr' for p in ctx['processes']):
        return None
    pids = {p['pid'] for p in ctx['processes'] if p['name'] == 'hunk'}
    if not pids:
        return None
    for session in ctx['hunk_sessions']():
        if session.get('pid') not in pids:
            continue
        match = re.search(r' ([0-9a-f]{40}\.\.[0-9a-f]{40})$', session.get('title', ''))
        if not match:
            continue
        sid = session['sessionId']
        try:
            meta = json.loads((Path.home() / '.local/state/hunk-herdr' / (sid + '.json')).read_text())
        except (OSError, ValueError):
            meta = {}
        repo, pr = meta.get('repo'), meta.get('pr')
        identity = f'hunk:{repo.lower()}#{pr}' if repo and pr else 'hunk:' + sid
        return dict(identity=identity, state={'cwd': session['repoRoot'], 'target': match[1],
                                             'repo': repo, 'pr': pr},
                    label=f'Hunk · {repo}#{pr}' if repo and pr else 'Hunk · ' + match[1][:12],
                    coverage='limited', detail='Reopens the diff; cursor, notes and selection are not restored.')

def restore(state):
    if not re.fullmatch(r'[0-9a-f]{40}\.\.[0-9a-f]{40}', state['target']):
        raise ValueError('Invalid Hunk revision range')
    return ['hunk', 'diff', state['target'], '--sidebar', '--line-numbers']
