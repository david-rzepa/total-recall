"""Foot transport: never infer replay permission from an arbitrary child command."""
import shlex
import os
import pwd

ID = 'terminal'
PRIORITY = -100

def capture(ctx):
    if ctx['executable'] != 'foot':
        return None
    children = ctx['processes'][1:]
    cwd = children[0]['cwd'] if children else ctx['cwd']
    shells = ctx.get('shell_names', ('bash', 'zsh', 'fish', 'sh'))
    unsupported = [p for p in children if p['name'] not in shells]
    return dict(identity=None, state={'cwd': cwd, 'shell': 'default'},
                needs_adapter=bool(unsupported),
                label='Terminal', coverage='limited',
                detail=('No adapter · ' + shlex.join(unsupported[-1].get('argv') or [unsupported[-1]['name']]) if unsupported else
                        'Opens your default shell in ' + cwd + '.'))

def restore(state):
    # Query the account on every restore: inherited SHELL may be stale after chsh.
    shell = pwd.getpwuid(os.getuid()).pw_shell or '/bin/sh'
    if not os.path.isabs(shell) or not os.access(shell, os.X_OK):
        raise ValueError('The account default shell is not executable: ' + shell)
    return [shell]
