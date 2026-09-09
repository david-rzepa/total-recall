#!/usr/bin/env python3
"""Install user-owned plugin files and service; preserve existing shell configuration."""
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import time

root = Path(__file__).resolve().parent
home = Path.home()
plugin = home / '.config/omarchy/plugins/dave.persist'
stamp = time.strftime('%Y%m%d-%H%M%S')
backup = home / '.local/state/omarchy-persist/backups' / stamp
backup.mkdir(parents=True, exist_ok=True, mode=0o700)
def preserve(path):
    if path.exists():
        shutil.copy2(path, backup / path.name)

plugin.mkdir(parents=True, exist_ok=True)
adapter_config = home / '.config/omarchy-persist/config.toml'
adapter_config.parent.mkdir(parents=True, exist_ok=True)
if not adapter_config.exists():
    shutil.copy2(root / 'config.example.toml', adapter_config)
for filename in ('manifest.json', 'BarWidget.qml', 'RecoveryModel.js', 'persist.py', 'README.md'):
    shutil.copy2(root / filename, plugin / filename)
# Distinct component URL avoids stale Qt component caches during local updates.
qml_name = 'PersistenceWidgetV' + hashlib.sha256((root / 'BarWidget.qml').read_bytes()).hexdigest()[:12].upper() + '.qml'
shutil.copy2(root / 'BarWidget.qml', plugin / qml_name)
manifest = json.loads((root / 'manifest.json').read_text())
manifest['entryPoints']['barWidget'] = qml_name
(plugin / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
shutil.copytree(root / 'adapters', plugin / 'adapters', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
bindir = home / '.local/bin'
bindir.mkdir(parents=True, exist_ok=True)
launcher = bindir / 'total-recall'
launcher.write_text('#!/bin/sh\nexec python3 -B "$HOME/.config/omarchy/plugins/dave.persist/persist.py" "$@"\n')
launcher.chmod(0o755)
# Compatibility for existing scripts and running adapter conversations.
legacy = bindir / 'omarchy-persist'
legacy.write_text('#!/bin/sh\nexec "$HOME/.local/bin/total-recall" "$@"\n')
legacy.chmod(0o755)
unit = home / '.config/systemd/user/omarchy-persist.service'
unit.parent.mkdir(parents=True, exist_ok=True)
unit.write_text('''[Unit]
Description=Adapter-based Omarchy workspace persistence
PartOf=graphical-session.target
After=graphical-session.target
[Service]
Type=simple
ExecStart=%h/.local/bin/total-recall watch
Restart=on-failure
RestartSec=5
UMask=0077
''')
config = home / '.config/omarchy/shell.json'
preserve(config)
data = json.loads(config.read_text())
layout = data.setdefault('bar', {}).setdefault('layout', {})
if not any(item.get('id') == 'dave.persist' for section in layout.values() for item in section if isinstance(item, dict)):
    layout.setdefault('right', []).insert(0, {'id': 'dave.persist'})
config.write_text(json.dumps(data, indent=2) + '\n')
subprocess.run(['omarchy', 'plugin', 'validate', str(plugin)], check=True)
subprocess.run(['omarchy', 'hook', 'install', 'post-boot', str(root / 'post-boot.hook')], check=True)
subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
subprocess.run(['systemctl', '--user', 'import-environment', 'HYPRLAND_INSTANCE_SIGNATURE', 'WAYLAND_DISPLAY', 'DISPLAY', 'XDG_RUNTIME_DIR', 'PATH'], check=True)
subprocess.run(['systemctl', '--user', 'restart', 'omarchy-persist.service'], check=True)
print('Installed dave.persist. Configuration backup:', backup)
