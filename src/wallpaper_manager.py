# wallpaper_manager.py
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
"""Core wallpaper management: managed folder, rotation and cropping.

Every wallpaper kept here has already been cropped to the target display's
aspect ratio, so applying one (manual selection or a rotation tick) is just
pointing org.gnome.desktop.background at the file - no GTK/Gdk needed. That
is what lets the same manager run headlessly from a systemd --user timer.
"""

import fcntl
import random
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import gi

gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gio, GdkPixbuf

from . import config

IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.avif'}
ORIGINALS_DIRNAME = '.originals'
LOCK_FILENAME = '.rotate.lock'


class WallpaperManager:
    """Owns the managed wallpaper folder and the rotation/apply logic."""

    def __init__(self):
        self._data = config.load()
        self.wallpapers_dir = Path(self._data['wallpapers_dir'])
        self.wallpapers_dir.mkdir(parents=True, exist_ok=True)
        self.originals_dir = self.wallpapers_dir / ORIGINALS_DIRNAME
        self._sync_order()


    def _save(self):
        config.save(self._data)

    @contextmanager
    def _locked(self):
        """Serialize rotate/apply across processes.

        The manual "Rotate to Next Wallpaper" action and the systemd
        --user timer's own catch-up fire (e.g. right after waking from
        sleep) can both invoke `fresco --rotate` at nearly the same
        moment. Without a lock, two processes' picture-uri and
        picture-uri-dark writes can interleave, leaving the two keys
        pointing at different wallpapers - and since GNOME renders
        whichever key matches the active color scheme, the desktop can
        end up stuck showing a stale image even though config.json (and
        the extension's preview, which reads it) shows the rotation as
        having happened.
        """
        config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        lock_path = config.CONFIG_DIR / LOCK_FILENAME
        with open(lock_path, 'w', encoding='utf-8') as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                # Pick up whatever the last writer left, rather than
                # whatever this instance loaded at construction time.
                self._data = config.load()
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def _sync_order(self):
        """Reconcile the stored order with what is actually on disk."""
        on_disk = {
            p.name for p in self.wallpapers_dir.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
        }
        order = [name for name in self._data['order'] if name in on_disk]
        for name in sorted(on_disk - set(order)):
            order.append(name)
        self._data['order'] = order
        if self._data['current_index'] >= len(order):
            self._data['current_index'] = len(order) - 1
        self._save()


    def list_wallpapers(self):
        self._sync_order()
        return list(self._data['order'])

    def path_for(self, name):
        return self.wallpapers_dir / name

    def current_name(self):
        idx = self._data['current_index']
        order = self._data['order']
        if 0 <= idx < len(order):
            return order[idx]
        return None

    def last_swap(self):
        return self._data.get('last_swap')

    @staticmethod
    def full_crop_box(image_path):
        """The identity crop box: the whole image, uncropped.

        This is the sane default across a multi-monitor setup with mixed
        aspect ratios - GNOME's own "zoom" picture-options mode already
        scales and center-crops the wallpaper to fill each monitor at
        render time, so pre-cropping to any one monitor's aspect ratio
        here would only make it wrong for the others.
        """
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(image_path))
        return (0, 0, pixbuf.get_width(), pixbuf.get_height())


    def import_wallpaper(self, source_path):
        """Stash the original file and return (original_path, stem) so the
        caller can run the crop UI and then call finish_import()."""
        source_path = Path(source_path)
        stem = self._unique_stem(source_path.stem)
        self.originals_dir.mkdir(exist_ok=True)
        original_dest = self.originals_dir / f'{stem}{source_path.suffix.lower()}'
        shutil.copy2(source_path, original_dest)
        return original_dest, stem

    def finish_import(self, stem, original_path, crop_box):
        """Crop the stashed original and add it to the managed set."""
        dest = self.wallpapers_dir / f'{stem}.png'
        self._crop_to(original_path, crop_box, dest)
        self._data['order'].append(dest.name)
        self._save()
        return dest

    def recrop(self, name, crop_box):
        """Re-crop an already-managed wallpaper from its stashed original."""
        source = self._find_original(name) or self.path_for(name)
        dest = self.path_for(name)
        self._crop_to(source, crop_box, dest)
        self._save()
        return dest

    def _find_original(self, name):
        stem = Path(name).stem
        if self.originals_dir.exists():
            for p in self.originals_dir.iterdir():
                if p.stem == stem:
                    return p
        return None

    @staticmethod
    def _crop_to(source_path, crop_box, dest_path):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(source_path))
        x, y, w, h = crop_box
        x = max(0, min(int(x), pixbuf.get_width() - 1))
        y = max(0, min(int(y), pixbuf.get_height() - 1))
        w = max(1, min(int(w), pixbuf.get_width() - x))
        h = max(1, min(int(h), pixbuf.get_height() - y))
        cropped = pixbuf.new_subpixbuf(x, y, w, h)
        cropped.savev(str(dest_path), 'png', [], [])
        return dest_path

    def _unique_stem(self, stem):
        candidate = stem
        counter = 1
        while (self.wallpapers_dir / f'{candidate}.png').exists():
            candidate = f'{stem}-{counter}'
            counter += 1
        return candidate


    def remove_wallpaper(self, name):
        order = self._data['order']
        if name not in order:
            return
        idx = order.index(name)
        order.remove(name)
        path = self.path_for(name)
        if path.exists():
            path.unlink()
        original = self._find_original(name)
        if original and original.exists():
            original.unlink()
        if self._data['current_index'] > idx:
            self._data['current_index'] -= 1
        elif self._data['current_index'] >= len(order):
            self._data['current_index'] = len(order) - 1
        self._save()


    def apply(self, name):
        """Set an already-managed (already-cropped) wallpaper as current."""
        with self._locked():
            return self._apply_locked(name)

    def _apply_locked(self, name):
        """Do the actual apply work. Caller must already hold _locked()."""
        path = self.path_for(name)
        if not path.exists():
            return False
        uri = Gio.File.new_for_path(str(path)).get_uri()
        settings = Gio.Settings.new('org.gnome.desktop.background')
        settings.set_string('picture-uri', uri)
        settings.set_string('picture-uri-dark', uri)
        settings.set_string('picture-options', 'zoom')
        order = self._data['order']
        if name in order:
            self._data['current_index'] = order.index(name)
        self._data['last_swap'] = datetime.now(timezone.utc).isoformat()
        self._save()
        return True

    def rotate_next(self):
        """Apply a random wallpaper from the managed folder, avoiding an
        immediate repeat of the current one when there's a choice."""
        with self._locked():
            order = self.list_wallpapers()
            if not order:
                return None
            if len(order) == 1:
                name = order[0]
            else:
                current = self.current_name()
                name = random.choice([n for n in order if n != current] or order)
            self._apply_locked(name)
            return name
