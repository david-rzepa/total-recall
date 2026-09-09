ID = 'herdr'
PRIORITY = 100

def capture(ctx):
    if ctx['executable'] != 'foot':
        return None
    for p in ctx['processes']:
        if p['name'] != 'herdr':
            continue
        argv = p['argv']
        name = 'default'
        if '--session' in argv:
            i = argv.index('--session')
            if i + 1 >= len(argv):
                return None
            name = argv[i + 1]
        elif any(a.startswith('--session=') for a in argv):
            name = next(a.split('=', 1)[1] for a in argv if a.startswith('--session='))
        return dict(identity='herdr:' + name, state={'session': name, 'cwd': p['cwd']},
                    label='Herdr · ' + name, coverage='limited',
                    detail='Restores Herdr panes and agents.')

def restore(state):
    return ['herdr'] if state['session'] == 'default' else ['herdr', '--session', state['session']]
