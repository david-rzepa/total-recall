ID = 'gh-dash'
PRIORITY = 10

def capture(ctx):
    if ctx['executable'] != 'foot':
        return None
    for p in ctx['processes']:
        if (p['name'] == 'gh' and p['argv'][1:2] == ['dash']) or p['name'] == 'gh-dash':
            return dict(identity=None, state={'cwd': p['cwd']}, label='GitHub dashboard',
                        coverage='limited', detail='Reopens gh dash; selection and filters reset.')

def restore(state):
    return ['gh', 'dash']
