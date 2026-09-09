#!/usr/bin/env python3
"""Exercise saved recovery in a spare workspace without duplicating live sessions."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import persist

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', default='1')
parser.add_argument('--target', required=True)
args = parser.parse_args()
if args.source == args.target or any(c['workspace']['name'] == args.target for c in persist.hypr('clients')):
    raise SystemExit('Target workspace must be unused')
os.umask(0o077)
adapters = persist.load_adapters()
status = persist.snapshot(adapters)
windows = [w for w in status['windows'] if w['placement']['workspace'] == args.source]
if not windows:
    raise SystemExit('Source workspace has no windows')
original_clients = {c['address']: c for c in persist.hypr('clients') if c['workspace']['name'] == args.source}
records = persist.database()['records']
folder = persist.STATE / 'restore-tests' / time.strftime('%Y%m%d-%H%M%S')
folder.mkdir(parents=True)
helper = folder / 'placeholder.py'
helper.write_text('''import json,sys,textwrap,time
from pathlib import Path
item=json.loads(Path(sys.argv[1]).read_text())
print("\\033[2J\\033[H",end="")
print("TOTAL RECALL · RESTORE TEST\\n")
print(item['title'] + "\\n")
for line in item['lines']:
 print(textwrap.fill(line, width=65) + "\\n")
print("This placeholder does not run an agent or submit any input.")
try:
 while True: time.sleep(3600)
except KeyboardInterrupt: pass
''')
adapters['test-placeholder'] = types.SimpleNamespace(ID='test-placeholder', fingerprint='test', PRIORITY=-1000, capture=lambda ctx: None,
    restore=lambda state: ['python3', '-B', str(helper), state['message']])
report = {'source': args.source, 'target': args.target, 'directory': str(folder), 'windows': []}
test_records = {}
for w in windows:
    saved = next((r for r in records.values() if r['key'] == w['key']), None)
    record = copy.deepcopy(saved or w)
    rid = 'test-' + uuid.uuid4().hex[:12]
    record.update(id=rid, key='test:' + w['key'], address='')
    record['placement']['workspace'] = args.target
    recipe = record.get('recipe')
    kind = recipe['adapter'] if recipe else 'unsupported'
    # These adapters produce viewers or an empty shell; others may attach to a
    # running conversation, singleton app, or shared mutable session.
    real = bool(saved) and kind in ('gh-dash', 'terminal')
    detail = recipe['detail'] if recipe else 'No recovery adapter is available.'
    mode = 'reopened' if real else 'placeholder'
    if not real:
        message = folder / (rid + '.json')
        lines = [detail, 'Original workspace: ' + args.source,
                 'Recovery: ' + (recipe['label'] if recipe else 'unsupported'),
                 'On reboot this would resume the saved session.' if saved else 'This window has not been persisted.']
        if kind == 'herdr' and os.environ.get('HERDR_ENV') == '1':
            try:
                data = json.loads(persist.run(['herdr', 'workspace', 'list']))['result']['workspaces']
                lines += ['Herdr: ' + x['label'] + ' — ' + str(x['pane_count']) + ' panes, ' + str(x['tab_count']) + ' tabs' for x in data]
            except Exception as exc:
                lines.append('Herdr inspection unavailable: ' + str(exc))
        persist.write(message, {'title': 'LIVE SESSION PLACEHOLDER' if saved else 'NOT PERSISTED', 'lines': lines})
        record['recipe'] = dict(adapter='test-placeholder', fingerprint='test', identity='test:' + rid,
            state={'cwd': str(Path.home()), 'message': str(message)}, label='Test placeholder', detail=detail)
        record.pop('blocked', None)
    test_records[rid] = record
    report['windows'].append({'id': rid, 'original_address': w['address'], 'app': recipe['label'] if recipe else w['app'],
                              'mode': mode, 'detail': detail, 'expected': copy.deepcopy(w['placement'])})
persist.write(folder / 'source.json', status)
persist.STATE = folder
persist.write(folder / 'saved.json', {'schema': 1, 'records': test_records})
# Use the actual recovery engine. Layout errors are reported, not hidden by a
# separate floating-window reconstruction that would make the test misleading.
for item in report['windows']:
    try:
        item['result'] = persist.restore(adapters, item['id'])
    except Exception as exc:
        item['error'] = str(exc)
        persist.write(folder / 'report.json', report)
try:
    outcomes = [dict(id=item['id'], **item.get('result', {'error': item.get('error', 'Restore failed')}))
                for item in report['windows']]
    persist.arrange_restored(test_records, outcomes)
    for item, outcome in zip(report['windows'], outcomes):
        if outcome.get('layout_error'):
            item['layout_error'] = outcome['layout_error']
except Exception as exc:
    report['layout_error'] = str(exc)
time.sleep(.5)
clients = persist.hypr('clients')
for item in report['windows']:
    c = next((c for c in clients if c['class'] == 'omarchy-persist-' + item['id']), None)
    if c:
        item['address'] = c['address']
        item['actual'] = {k: c[k] for k in ('at', 'size', 'floating', 'fullscreen')}
        item['actual']['workspace'] = c['workspace']['name']
        item['layout_matches'] = all(item['actual'][k] == item['expected'][k] for k in ('at', 'size', 'floating', 'fullscreen')) and c['workspace']['name'] == args.target
report['source_unchanged'] = all(any(c['address'] == a and all(c[k] == old[k] for k in ('at', 'size', 'workspace', 'floating')) for c in clients) for a, old in original_clients.items())
persist.write(folder / 'report.json', report)
persist.dispatch('focus', {'workspace': args.target})
print(json.dumps(report, indent=2))
