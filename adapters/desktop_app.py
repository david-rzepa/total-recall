"""Normal desktop applications use their installed launcher, never /proc argv replay."""
import configparser
import os
from pathlib import Path
import shlex
from urllib.parse import urlparse

ID = 'desktop-app'
PRIORITY = 0
TRANSPORT = 'desktop'
TERMINALS = {'foot', 'footclient', 'kitty', 'alacritty', 'ghostty', 'wezterm',
             'wezterm-gui', 'konsole', 'gnome-terminal', 'gnome-terminal-server',
             'xterm', 'uxterm', 'st', 'tilix', 'terminator', 'rio'}

def entries():
    roots = [Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))]
    roots += [Path(p) for p in os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':') if p]
    found = {}
    for root in roots:
        directory = root / 'applications'
        for path in sorted(directory.rglob('*.desktop')):
            desktop_id = str(path.relative_to(directory)).replace('/', '-')
            if desktop_id in found:
                continue
            # Hidden user entries also mask their system counterpart.
            found[desktop_id] = None
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path)
                e = parser['Desktop Entry']
                if e.get('Type') != 'Application' or e.getboolean('Hidden', False) or e.getboolean('Terminal', False):
                    continue
                argv = shlex.split(e.get('Exec', ''))
                exe = Path(argv[0]).name if argv else ''
                if exe in TERMINALS:
                    continue
                if not argv and not e.getboolean('DBusActivatable', False):
                    continue
                wmclass = e.get('StartupWMClass', '').lower()
                keys = {path.stem.lower(), wmclass}
                if exe and exe not in ('env', 'sh', 'bash', 'python', 'python3', 'launch'):
                    keys.add(exe.lower())
                # Omarchy web-app windows use Chromium's URL-derived app ID.
                if exe == 'omarchy-launch-webapp' and len(argv) > 1:
                    u = urlparse(argv[1])
                    keys.add('chrome-' + u.netloc.lower() + '_' + (u.path or '/').replace('/', '_') + '-default')
                keys.discard('')
                found[desktop_id] = dict(path=str(path), id=desktop_id, keys=keys,
                                        wmclass=wmclass, name=e.get('Name', path.stem))
            except (OSError, ValueError, KeyError, configparser.Error):
                continue
    return [e for e in found.values() if e]

def capture(ctx):
    c = ctx['client']
    classes = {c.get('class', '').lower(), c.get('initialClass', '').lower()}
    if ctx['executable'] in TERMINALS or classes.intersection(TERMINALS) or 'terminal' in {t.rstrip('*') for t in c.get('tags', [])}:
        return None
    candidates = []
    for e in entries():
        score = 2 if e['wmclass'] and e['wmclass'] in classes else 1 if e['keys'].intersection(classes) else 0
        if score:
            candidates.append((score, e))
    if not candidates:
        return None
    best_score = max(x[0] for x in candidates)
    best = [e for score, e in candidates if score == best_score]
    if len(best) != 1:
        return None
    e = best[0]
    return dict(identity='desktop:' + e['id'],
                state={'desktop_id': e['id'], 'cwd': str(Path.home()), 'window_class': c['class']},
                label=e['name'], coverage='limited',
                detail='Reopens the app; recovery of its contents depends on the app.')

def restore(state):
    e = next((e for e in entries() if e['id'] == state['desktop_id']), None)
    if not e:
        raise ValueError('Desktop application is no longer installed or its launcher is disabled')
    # GIO implements field-code expansion and launcher semantics. No shell parsing here.
    return ['gio', 'launch', e['path']]
