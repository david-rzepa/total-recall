import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import persist

class RecoveryTests(unittest.TestCase):
    def test_shell_restore_follows_account_changes_not_environment(self):
        adapter = self.adapters['terminal']
        state = {'cwd': '/tmp', 'shell': 'default'}
        with patch.dict(os.environ, {'SHELL': '/old/shell'}), patch.object(adapter.os, 'access', return_value=True):
            for path in ['/bin/bash', '/bin/fish']:
                with patch.object(adapter.pwd, 'getpwuid', return_value=type('Account', (), {'pw_shell': path})()):
                    self.assertEqual(adapter.restore(state), [path])
                    self.assertEqual(adapter.restore({'cwd': '/tmp'}), [path])
        self.assertEqual(state['shell'], 'default')

    def test_group_restore_never_moves_reused_windows(self):
        records = {'a': {'placement': {'group': {'id': 'g', 'index': 0}}},
                   'b': {'placement': {'group': {'id': 'g', 'index': 1}}}}
        outcomes = [{'id': 'a', 'result': 'restored', 'address': '0x1'},
                    {'id': 'b', 'result': 'reuse', 'address': '0x2'}]
        with patch.object(persist, 'dispatch') as dispatch:
            persist.restore_groups(records, outcomes)
            dispatch.assert_not_called()

    def test_group_layout_uses_one_rectangle(self):
        records = {str(i): {'placement': {'workspace':'8', 'floating':False,
                   'group':{'id':'g', 'index':i, 'active':i==1}}} for i in range(2)}
        outcomes = [{'id':str(i), 'result':'restored', 'address':str(i)} for i in range(2)]
        with patch.object(persist, 'restore_groups'), patch.object(persist, 'arrange_tiled') as arrange, patch.object(persist, 'dispatch') as dispatch:
            persist.arrange_restored(records, outcomes)
            self.assertEqual(len(arrange.call_args.args[0]), 1)
            dispatch.assert_called_with('focus', {'window':'address:1'})

    def test_unknown_process_requires_adapter_but_idle_shell_does_not(self):
        ctx = dict(executable='foot', cwd='/tmp', processes=[{'name':'foot', 'cwd':'/tmp'}, {'name':'bash', 'cwd':'/tmp'}])
        self.assertFalse(self.adapters['terminal'].capture(ctx)['needs_adapter'])
        ctx['processes'].append({'name':'python', 'cwd':'/tmp'})
        self.assertTrue(self.adapters['terminal'].capture(ctx)['needs_adapter'])

    def test_create_adapter_rejects_changed_window(self):
        with patch.object(persist, 'discover', return_value=[]), patch.object(persist, 'dispatch') as dispatch:
            with self.assertRaises(ValueError):
                persist.create_adapter(self.adapters, '0x1', 'stale')
            dispatch.assert_not_called()

    def test_create_adapter_drafts_without_enrollment_or_process_replay(self):
        window = copy.deepcopy(self.window)
        window['recipe']['needs_adapter'] = True
        with tempfile.TemporaryDirectory() as directory, patch.object(persist, 'STATE', Path(directory)), patch.object(persist, 'CONFIG', Path(directory)/'config'), patch.object(persist, 'discover', return_value=[window]), patch.object(persist, 'hypr', return_value=[{'address':'0x1', 'pid':42}]), patch.object(persist, 'processes', return_value=[{'argv':['cp','a','b']}]), patch.object(persist, 'dispatch') as dispatch:
            result = persist.create_adapter(self.adapters, '0x1', 'window:1')
            self.assertTrue((Path(result['draft'])/'context.json').exists())
            self.assertFalse((Path(directory)/'saved.json').exists())
            args = __import__('shlex').split(dispatch.call_args.args[1])
            self.assertEqual(args[:3], ['omarchy', 'launch', 'tui'])
            self.assertEqual(args[6:10], ['omarchy', 'agent', 'prompt', '--inline'])
            self.assertIn('wait for the user to approve', args[-1])
            self.assertIn('hot-reload automatically every two seconds', args[-1])
            self.assertIn('Do not restart or stop omarchy-persist.service', args[-1])
            self.assertIn('total-recall scan', args[-1])

    def test_place_explicitly_sets_float_state(self):
        for floating, action in [(True, 'on'), (False, 'off')]:
            with patch.object(persist, 'dispatch') as dispatch:
                persist.place('0x1', dict(workspace='8', floating=floating, at=[2, 28], size=[956, 523]))
                self.assertIn(unittest.mock.call('window.float', {'window': 'address:0x1', 'action': action}), dispatch.call_args_list)

    def test_three_window_layout_tree(self):
        def item(address, at, size):
            return dict(address=address, placement=dict(at=at, size=size))
        tree = persist.layout_tree([item('bottom', [2,555], [956,523]), item('right', [962,28], [956,1050]), item('top', [2,28], [956,523])])
        self.assertEqual(tree['axis'], 0)
        self.assertAlmostEqual(tree['ratio'], 1)
        self.assertEqual(tree['second']['address'], 'right')
        self.assertEqual(tree['first']['axis'], 1)
        self.assertEqual(tree['first']['first']['address'], 'top')
        self.assertEqual(tree['first']['second']['address'], 'bottom')

    def test_layout_preserves_unrelated_destination_windows(self):
        clients = [dict(address=a, workspace={'name': '8'}, floating=False) for a in ('0x1', '0x2')]
        with patch.object(persist, 'hypr', return_value=clients), patch.object(persist, 'dispatch') as dispatch:
            with self.assertRaises(ValueError):
                persist.arrange_tiled([dict(address='0x1', placement={'workspace':'8'})])
            dispatch.assert_not_called()

    def test_restore_layout_excludes_live_reused_sessions(self):
        outcomes = [dict(id='one', result='reuse', address='0x1')]
        with patch.object(persist, 'arrange_tiled') as arrange:
            persist.arrange_restored({'one': self.window}, outcomes)
            arrange.assert_not_called()

    def setUp(self):
        self.adapters = persist.load_adapters()
        self.window = dict(key='window:1', address='0x1', title='review', error=None,
                           placement={'workspace': '1'}, recipe=dict(adapter='herdr', identity='herdr:default',
                           fingerprint=self.adapters['herdr'].fingerprint, label='Herdr', detail='native', state={'cwd': '/tmp', 'session': 'default'}))
        self.db = {'schema': 1, 'records': {'one': copy.deepcopy(self.window)}}

    def test_copy_never_becomes_replay_command(self):
        ctx = dict(executable='foot', cwd='/tmp', processes=[{'name': 'foot', 'cwd': '/tmp'},
                   {'name': 'cp', 'argv': ['cp', 'a', 'b'], 'cwd': '/tmp'}])
        recipe = self.adapters['terminal'].capture(ctx)
        self.assertEqual(self.adapters['terminal'].restore(recipe['state']), [persist.pwd.getpwuid(os.getuid()).pw_shell or '/bin/sh'])
        self.assertEqual(recipe['coverage'], 'limited')

    def test_changed_conversation_updates_automatically(self):
        current = copy.deepcopy(self.window)
        current['recipe']['identity'] = 'herdr:other'
        persist.reconcile(self.db, [current])
        self.assertEqual(current['status'], 'saved')
        self.assertEqual(self.db['records']['one']['recipe']['identity'], 'herdr:other')
        self.assertEqual(persist.plan(self.db, [current], self.adapters)[0]['action'], 'reuse')
        self.assertEqual(persist.plan(self.db, [], self.adapters)[0]['action'], 'restore')

    def test_layout_autosaves_for_same_identity(self):
        current = copy.deepcopy(self.window)
        current['placement']['workspace'] = '9'
        persist.reconcile(self.db, [current])
        self.assertEqual(self.db['records']['one']['placement']['workspace'], '9')
        self.assertEqual(current['status'], 'saved')

    def test_live_identity_prevents_duplicate_after_pid_changes(self):
        current = copy.deepcopy(self.window)
        current.update(key='new-boot:new-pid', address='0x2')
        self.assertEqual(persist.plan(self.db, [current], self.adapters)[0]['action'], 'reuse')

    def test_jump_uses_current_workspace_and_exact_window(self):
        client = {'address': '0x123', 'pid': 42, 'workspace': {'name': '6'}}
        with patch.dict(os.environ, {'HYPRLAND_INSTANCE_SIGNATURE': 'boot'}), patch.object(persist, 'hypr', return_value=[client]), patch.object(persist, 'process', return_value={'start': '77'}), patch.object(persist, 'dispatch') as dispatch:
            persist.focus_window('0x123', 'boot:0x123:42:77')
            self.assertEqual(dispatch.call_args_list[0].args, ('focus', {'workspace': '6'}))
            self.assertEqual(dispatch.call_args_list[1].args, ('focus', {'window': 'address:0x123'}))

    def test_jump_rejects_reused_window_address(self):
        client = {'address': '0x123', 'pid': 42, 'workspace': {'name': '6'}}
        with patch.dict(os.environ, {'HYPRLAND_INSTANCE_SIGNATURE': 'boot'}), patch.object(persist, 'hypr', return_value=[client]), patch.object(persist, 'process', return_value={'start': '88'}), patch.object(persist, 'dispatch') as dispatch:
            with self.assertRaises(ValueError):
                persist.focus_window('0x123', 'boot:0x123:42:77')
            dispatch.assert_not_called()

    def test_adapter_change_blocks_old_registration(self):
        self.db['records']['one']['recipe']['fingerprint'] = 'old'
        self.assertEqual(persist.plan(self.db, [], self.adapters)[0]['action'], 'blocked')

    def test_missing_adapter_does_not_execute_stored_arguments(self):
        self.assertEqual(persist.plan(self.db, [], {})[0]['action'], 'blocked')

    def test_hunk_uses_live_revision_not_launch_argument(self):
        target = 'a' * 40 + '..' + 'b' * 40
        ctx = dict(executable='foot', processes=[{'name': 'hunk', 'pid': 1}],
                   hunk_sessions=lambda: [{'pid': 1, 'sessionId': 'test', 'repoRoot': '/tmp', 'title': 'diff ' + target}])
        recipe = self.adapters['hunk'].capture(ctx)
        self.assertEqual(recipe['state']['target'], target)

    def test_private_atomic_storage_and_corruption_not_silenced(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'saved.json'
            persist.write(path, self.db)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(persist.read(path, {}), self.db)
            path.write_text('{broken')
            with self.assertRaises(json.JSONDecodeError):
                persist.read(path, {})

    def test_adapter_config_can_disable_and_reenable(self):
        with tempfile.TemporaryDirectory() as d, patch.object(persist, 'CONFIG', Path(d)):
            config = Path(d) / 'config.toml'
            config.write_text('[adapters.codex]\nenabled = false\n')
            self.assertNotIn('codex', persist.load_adapters())
            self.assertIn('herdr', persist.load_adapters())
            config.write_text('[adapters.codex]\nenabled = true\n')
            self.assertIn('codex', persist.load_adapters())

    def test_skip_is_durable_and_persist_clears_it(self):
        with tempfile.TemporaryDirectory() as d, patch.object(persist, 'STATE', Path(d)), patch.object(persist, 'discover', return_value=[self.window]):
            persist.skip_window(self.adapters, '0x1', 'window:1')
            self.assertTrue(persist.database()['skipped']['window:1'])
            persist.enroll(self.adapters, '0x1')
            self.assertNotIn('window:1', persist.database()['skipped'])

class DesktopAppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.apps = self.root / 'applications'
        self.apps.mkdir()
        self.env = patch.dict(os.environ, {'XDG_DATA_HOME': str(self.root), 'XDG_DATA_DIRS': ''})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.adapters = persist.load_adapters()
        self.adapter = self.adapters['desktop-app']
        self.ctx = dict(executable='slack', client={'class': 'Slack', 'initialClass': 'Slack', 'tags': []})

    def entry(self, name='slack.desktop', extra=''):
        p = self.apps / name
        p.write_text('[Desktop Entry]\nType=Application\nName=Slack\nExec=/usr/bin/slack %U\nStartupWMClass=Slack\n' + extra)
        return p

    def test_desktop_launcher_instead_of_process_arguments(self):
        p = self.entry()
        self.ctx['argv'] = ['slack', '--arbitrary-old-argument']
        r = self.adapter.capture(self.ctx)
        self.assertEqual(r['identity'], 'desktop:slack.desktop')
        self.assertEqual(self.adapter.restore(r['state']), ['gio', 'launch', str(p)])

    def test_terminal_never_uses_desktop_app_fallback(self):
        self.entry()
        self.ctx['executable'] = 'kitty'
        self.assertIsNone(self.adapter.capture(self.ctx))
        self.ctx['executable'] = 'something-custom'
        self.ctx['client']['tags'] = ['terminal*']
        self.assertIsNone(self.adapter.capture(self.ctx))

    def test_terminal_and_hidden_launchers_excluded(self):
        self.entry(extra='Terminal=true\n')
        self.assertIsNone(self.adapter.capture(self.ctx))
        self.entry(extra='Hidden=true\n')
        self.assertIsNone(self.adapter.capture(self.ctx))

    def test_ambiguous_app_id_is_not_guessed(self):
        self.entry()
        self.entry('second.desktop')
        self.assertIsNone(self.adapter.capture(self.ctx))

    def test_uninstalled_application_cannot_be_replayed(self):
        p = self.entry()
        recipe = self.adapter.capture(self.ctx)
        p.unlink()
        with self.assertRaises(ValueError):
            self.adapter.restore(recipe['state'])

    def test_gui_restore_does_not_open_terminal(self):
        p = self.entry()
        recipe = self.adapter.capture(self.ctx)
        recipe.update(adapter=self.adapter.ID, fingerprint=self.adapter.fingerprint)
        record = dict(key='old', recipe=recipe, placement={'workspace': '8'}, title='Slack', address='old')
        live = dict(record, key='new', address='0x2')
        with patch.object(persist, 'STATE', self.root / 'state'), patch.object(persist, 'discover', side_effect=[[], [], [live], [live]]), patch.object(persist, 'dispatch') as dispatch, patch.object(persist, 'place'):
            persist.write(persist.STATE / 'saved.json', {'schema': 1, 'records': {'slack': record}})
            result = persist.restore(self.adapters, 'slack')
            self.assertEqual(result['result'], 'restored')
            command = dispatch.call_args.args[1]
            self.assertTrue(command.startswith('gio launch '), command)
            self.assertNotIn('foot', command)
            saved = persist.database()['records']['slack']
            self.assertNotIn('launch_pending', saved)

if __name__ == '__main__':
    unittest.main()
