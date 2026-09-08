# config.py
#
# Copyright 2026 Snehal-Reddy
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Plain JSON persistence for Fresco's rotation state."""

import json
import os
import tempfile
from pathlib import Path

CONFIG_DIR = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'fresco'
CONFIG_FILE = CONFIG_DIR / 'config.json'
DEFAULT_WALLPAPERS_DIR = (
    Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share')))
    / 'fresco' / 'wallpapers'
)
DEFAULT_ROTATION_INTERVAL_HOURS = 24

DEFAULTS = {
    'wallpapers_dir': str(DEFAULT_WALLPAPERS_DIR),
    'order': [],
    'current_index': -1,
    'last_swap': None,
    'rotation_interval_hours': DEFAULT_ROTATION_INTERVAL_HOURS,
}


def load():
    """Load the config, merging in defaults for any missing keys."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding='utf-8') as f:
                data = json.load(f)
            merged = DEFAULTS.copy()
            merged.update(data)
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULTS.copy()


def save(data):
    """Atomically write the config back to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', dir=CONFIG_DIR,
            prefix='config.', suffix='.tmp', delete=False) as f:
        json.dump(data, f, indent=2)
        tmp_name = f.name
    os.replace(tmp_name, CONFIG_FILE)
