# Total Recall

**Bring your Omarchy workspace back.**

Total Recall is a keyboard-driven Omarchy shell plugin that remembers which
windows you want to keep, captures their recoverable state as you work, and
reopens them after your next login.

Launch apps normally. Decide what to persist from one compact table. Supported
processes use recovery adapters; an unknown terminal command offers **Create
adapter** using your default OS agent.

## Features

- Automatic capture of persisted windows and adapter configuration every two seconds.
- Workspace placement, floating geometry, and dwindle tiling reconstruction.
- Hyprland groups: membership, tab order, and selected tab.
- Desktop application recognition through installed `.desktop` launchers.
- Session-aware recovery for Herdr, Codex, Hunk, and gh-dash in Foot.
- Default-shell recovery that follows changes to your account's login shell.
- User-owned adapters, with an agent-assisted draft and review flow.
- Keyboard navigation, application icons, and jump-to-window actions.

The bar icon is white when all windows are decided, yellow for new decisions,
and red for errors. The table shows **Persist / Workspace / Group / Application /
Window**. Group membership is displayed as `group:tab`, sorted in tab order.

## Install

Requires Omarchy with its Quickshell plugin system, Hyprland's Lua dispatcher
API, Python 3.11+, Foot, GIO, and a systemd user session. Development has been
tested on Hyprland 0.56.2. Older Hyprland dispatcher syntax is not supported.
Install any optional applications you want their adapters to recover separately.

Run these commands from your graphical session:

```sh
git clone https://github.com/david-rzepa/total-recall.git
cd total-recall
python3 install.py
```

The installer adds the widget to the right side of the bar, installs the CLI,
user service, and post-boot hook, and backs up your shell configuration. It
preserves existing adapter configuration. Ensure `~/.local/bin` is on `PATH`.
If the widget is cached after a plugin update, run `omarchy restart shell`.

To update, pull changes and rerun `python3 install.py`. **Editing an adapter does
not require reinstalling or restarting anything.**

For compatibility with early installations, the internal plugin ID remains
`dave.persist`, the service is `omarchy-persist.service`, and configuration/state
use the `omarchy-persist` directory name. The public CLI is `total-recall`.

## Use

Click the history icon to open Total Recall. Omarchy's positional panel shortcut
is **Super+Ctrl+1** when this widget is first in the right section.

| Key | Action |
| --- | --- |
| Up/Down, j/k, Tab/Shift+Tab | Select a window |
| Space or s | Persist, unpersist, or create a missing adapter |
| n | Skip this window and remove its registration |
| Enter | Jump to the selected live window |
| Home/End, PageUp/PageDown | Navigate the table |
| Esc or q | Close |

Click the persist marker to perform its action, right-click to skip, or
double-click a row to jump. Markers are **✓** persisted, **–** not persisted,
yellow **!** undecided, red **?** closed but persisted, and red **×** error.
For a closed entry, Enter/Space or clicking its marker restores it; Delete/n or
right-clicking the marker deletes its saved entry.

Closing a persisted window does not remove its startup registration. Unpersist
or skip it to stop restoring it. Newly opened windows require a new decision.
Only persisted group members return; existing live windows are never regrouped
by a recovery batch.

```sh
total-recall scan                       # capture now and print status
total-recall persist                    # act on the focused window
total-recall preview                    # inspect recovery plans
total-recall restore --id RECORD_ID     # restore one registration
total-recall forget --id RECORD_ID
```

For an optional focused-window shortcut, add this to your Hyprland bindings:

```lua
o.bind("SUPER + ALT + P", "Total Recall", "total-recall persist")
```

## Recovery support

| Application | What returns | Limits |
| --- | --- | --- |
| Desktop apps | Installed application launcher | App owns content recovery; one registration per app |
| Herdr | Named session, native panes and agents | Depends on Herdr's native recovery |
| Codex | Captured CLI conversation | Typed input and launch flags are not restored |
| Hunk | Live diff revisions and known PR context | Cursor, notes, selection, and Herdr bridge are not restored |
| gh-dash | Dashboard in the saved directory | Filters and selection reset |
| Idle Foot shell | Current account default shell and directory | Typed input is not restored |
| Unknown terminal command | Create adapter action | No automatic command replay |

Total Recall restores applications through adapters, not memory checkpoints.
It does not replay arbitrary jobs such as file copies. Existing matching
sessions are reused; conversations are not automatically forked. Group lock
state, exact desktop-app multi-window recovery, other tiling layouts, and full
monitor topology recovery are not implemented. Group reconstruction runs during
batch login recovery; restoring one registration does not restore its peers.
A full reboot and live-agent recovery have not yet been tested end to end.

## Adapter configuration

Edit `~/.config/omarchy-persist/config.toml`:

```toml
[adapters.hunk]
enabled = true

[agent]
command = ["omarchy", "agent", "prompt", "--inline"]
```

See [config.example.toml](config.example.toml) for all bundled adapters. Changes
are loaded every two seconds. Invalid configuration preserves the last snapshot
and surfaces a stale/error state.

**Create adapter** opens the OS default agent in the default terminal with a
process-context file and a draft request. Repeated requests focus the same draft
window. The prompt is submitted on startup; generation does not run in the
background merely because a process was discovered. The agent is instructed to
leave the original process alone, draft and test an adapter, and await review
before enabling it. A Herdr pane handoff is not yet implemented.

Drafts live under `~/.local/state/omarchy-persist/adapter-drafts/`. Enabled user
adapters live under `~/.config/omarchy-persist/adapters/`; a matching filename
overrides a bundled adapter. **Do not restart the service or shell UI to load an
adapter.** Verify detection with `total-recall scan`.

### Adapter contract

Adapters are trusted Python code executed in the user service.

- `ID`: stable adapter identifier.
- `PRIORITY`: recognition order, highest first.
- `capture(ctx)`: return `None`, or a JSON-serializable recipe containing
  `identity`, `state`, `label`, `coverage`, and `detail`. State includes `cwd`.
  Context supplies the client, process tree, recognized shell names, and a lazy
  Hunk session query. Set `needs_adapter` for unsupported process recovery.
- `restore(state)`: return an argv array, never a shell snippet. Foot is the
  terminal transport. `TRANSPORT = 'desktop'` launches the returned argv directly.

An identity names a resumable session, not merely an executable. Capture live
state where launch arguments can become stale. See [adapters/](adapters/) for
examples. Saved recipes include adapter fingerprints; changed recipes for live
persisted windows update automatically. Closed records with mismatched adapter
fingerprints require inspection before recovery.

Recovery state is stored under `~/.local/state/omarchy-persist/` with private
permissions and atomic writes. It may contain window titles, directories, session
identifiers, and process arguments in agent drafts. Do not commit these files.

## Development

```sh
python3 -m unittest discover -s tests -v
node tests/test_ui_model.cjs
```

Run a visual recovery test on an unused workspace:

```sh
python3 tests/preview_workspace.py --source 1 --target 8
```

This creates temporary windows and leaves them open for inspection. Live agents
and other potentially shared sessions use placeholders. It does not submit agent
input or fork conversations. Reports are written under the local state directory.
Close the test windows when finished.

Bug reports and pull requests are welcome. Include Omarchy/Hyprland versions,
steps to reproduce, and redacted diagnostics; avoid publishing session data.

## License

[MIT](LICENSE)
