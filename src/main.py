# main.py
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

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gettext import gettext as _

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gio, GLib, Gtk

from .wallpaper_manager import WallpaperManager
from .window import FrescoWindow
from . import config

ROTATE_TIMER_UNIT = 'com.fresco.v1.rotate.timer'
MIN_ROTATION_INTERVAL_HOURS = 1
MAX_ROTATION_INTERVAL_HOURS = 168


class FrescoApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(application_id='com.fresco.v1',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/com/fresco/v1')
        self.manager = WallpaperManager()
        self._timer_enabled = False

        self.create_action('quit', lambda *_: self.quit(), ['<control>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('preferences', self.on_preferences_action)
        self.create_action('shortcuts', self.on_shortcuts_action)
        self.create_action('rotate-next', self.on_rotate_next_action)
        self.create_action('apply-wallpaper', self.on_apply_wallpaper_action,
                            param_type=GLib.VariantType.new('s'))

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        win = self.props.active_window
        if not win:
            win = FrescoWindow(manager=self.manager, application=self)
        win.present()
        self._ensure_rotation_timer_enabled()

    def on_about_action(self, *args):
        """Callback for the app.about action."""
        about = Adw.AboutDialog(application_name='Fresco',
                                application_icon='com.fresco.v1',
                                developer_name='Snehal-Reddy',
                                version='0.1.0',
                                # Translators: Replace "translator-credits" with your name/username, and optionally an email or URL.
                                translator_credits = _('translator-credits'),
                                developers=['Snehal-Reddy'],
                                copyright='© 2026 Snehal-Reddy')
        about.present(self.props.active_window)

    def on_preferences_action(self, widget, _param):
        """Callback for the app.preferences action.

        Automatic rotation is scheduled by the com.fresco.v1.rotate.timer
        systemd --user unit, enabled automatically on first launch; this
        just surfaces that state and lets it be toggled by hand.
        """
        win = self.props.active_window
        enabled = self._timer_active()
        interval = self._rotation_interval_hours()
        interval_label = Gtk.Label(label=self._format_interval(interval))
        interval_label.set_xalign(0)
        interval_label.add_css_class('dim-label')
        next_rotation_label = Gtk.Label(
            label=self._next_rotation_text(interval) if enabled else '')
        next_rotation_label.set_xalign(0)
        next_rotation_label.add_css_class('dim-label')
        next_rotation_label.set_visible(enabled)
        scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            MIN_ROTATION_INTERVAL_HOURS,
            MAX_ROTATION_INTERVAL_HOURS,
            1,
        )
        scale.set_value(interval)
        scale.set_digits(0)
        scale.set_hexpand(True)
        scale.set_draw_value(False)
        scale.set_tooltip_text(_('Rotation interval in hours'))
        scale.connect(
            'value-changed',
            lambda slider: (
                interval_label.set_text(
                    self._format_interval(int(slider.get_value()))),
                next_rotation_label.set_text(
                    self._next_rotation_text(int(slider.get_value()))),
            ),
        )
        interval_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        interval_box.append(Gtk.Label(label=_('Rotate every'), xalign=0))
        interval_box.append(scale)
        interval_box.append(interval_label)
        interval_box.append(next_rotation_label)
        dialog = Adw.AlertDialog(
            heading=_('Automatic Rotation'),
            body=_('Fresco uses a systemd --user timer, so it keeps working '
                   'when this window is closed.\n\nStatus: {}').format(
                       _('On') if enabled else _('Off')),
        )
        dialog.set_extra_child(interval_box)
        dialog.add_response('close', _('Close'))
        dialog.add_response('toggle', _('Turn Off') if enabled else _('Turn On'))
        if enabled:
            dialog.set_response_appearance('toggle', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect('response', self._on_preferences_response, scale)
        dialog.present(win)

    def _on_preferences_response(self, dialog, response, scale):
        interval = int(scale.get_value())
        if interval != self._rotation_interval_hours():
            self._set_rotation_interval(interval)
        if response == 'toggle':
            if self._timer_active():
                self._run_systemctl('disable', '--now')
            else:
                self._run_systemctl('enable', '--now')

    def _rotation_interval_hours(self):
        data = config.load()
        return max(
            MIN_ROTATION_INTERVAL_HOURS,
            min(MAX_ROTATION_INTERVAL_HOURS, int(data.get(
                'rotation_interval_hours', config.DEFAULT_ROTATION_INTERVAL_HOURS
            ))),
        )

    @staticmethod
    def _format_interval(hours):
        days, remaining_hours = divmod(hours, 24)
        if days and remaining_hours:
            return _('{} days, {} hours').format(days, remaining_hours)
        if days:
            return _('{} days').format(days)
        return _('{} hours').format(hours)

    def _next_rotation_text(self, hours):
        """Preview when the next rotation would land for a given interval.

        Based on the last swap time plus that interval, not the timer's
        own internal state, so the preview updates live as the slider
        moves before the interval is actually applied.
        """
        last_swap = self.manager.last_swap()
        if not last_swap:
            return _('Next rotation: not yet scheduled')
        try:
            last = datetime.fromisoformat(last_swap)
        except ValueError:
            return _('Next rotation: not yet scheduled')
        remaining = (last + timedelta(hours=hours)) - datetime.now(timezone.utc)
        total_minutes = int(remaining.total_seconds() // 60)
        if total_minutes <= 0:
            return _('Next rotation: due now')
        hours_left, minutes_left = divmod(total_minutes, 60)
        if hours_left and minutes_left:
            return _('Next rotation in {} h {} min').format(hours_left, minutes_left)
        if hours_left:
            return _('Next rotation in {} hours').format(hours_left)
        return _('Next rotation in {} minutes').format(minutes_left)

    def _set_rotation_interval(self, hours):
        data = config.load()
        data['rotation_interval_hours'] = hours
        config.save(data)
        timer_dropin = (
            Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
            / 'systemd' / 'user' / f'{ROTATE_TIMER_UNIT}.d' / 'interval.conf'
        )
        timer_dropin.parent.mkdir(parents=True, exist_ok=True)
        timer_dropin.write_text(
            # OnUnitActiveSec= is cumulative across the base unit and
            # drop-ins (systemd.timer(5)); an empty assignment first
            # clears the base unit's 24h default so only this interval
            # is active, instead of both firing.
            f'[Timer]\nOnUnitActiveSec=\nOnUnitActiveSec={hours}h\n', encoding='utf-8'
        )
        self._run_systemctl('daemon-reload')
        if self._timer_active():
            self._run_systemctl('restart')

    def on_shortcuts_action(self, *args):
        """Callback for the app.shortcuts action."""
        builder = Gtk.Builder.new_from_resource('/com/fresco/v1/shortcuts-dialog.ui')
        dialog = builder.get_object('shortcuts_dialog')
        dialog.present(self.props.active_window)

    def on_rotate_next_action(self, *args):
        """Callback for the app.rotate-next action.

        Exposed over D-Bus (GApplication actions) so the GNOME Shell
        extension can trigger a rotation without opening the app window.
        """
        name = self.manager.rotate_next()
        win = self.props.active_window
        if win:
            win.refresh()
            if name:
                win.toast_overlay.add_toast(Adw.Toast.new(_('Rotated to {}').format(name)))

    def on_apply_wallpaper_action(self, action, param):
        """Callback for the app.apply-wallpaper action.

        Takes the wallpaper's filename as its string parameter, so the
        GNOME Shell extension can apply a specific wallpaper (interactive
        selection) without opening the app window.
        """
        name = param.get_string()
        self.manager.apply(name)
        win = self.props.active_window
        if win:
            win.refresh()

    def _ensure_rotation_timer_enabled(self):
        if self._timer_enabled:
            return
        self._timer_enabled = True
        interval = self._rotation_interval_hours()
        self._set_rotation_interval(interval)
        self._run_systemctl('enable', '--now')

    def _timer_active(self):
        result = self._run_systemctl('is-active', check=False)
        return result is not None and result.returncode == 0

    def _run_systemctl(self, action, *extra_args, check=False):
        try:
            command = ['systemctl', '--user', action, *extra_args]
            if action != 'daemon-reload':
                command.append(ROTATE_TIMER_UNIT)
            return subprocess.run(
                command,
                check=check, capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None

    def create_action(self, name, callback, shortcuts=None, param_type=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
            param_type: an optional GLib.VariantType for the action's parameter
        """
        action = Gio.SimpleAction.new(name, param_type)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version):
    """The application's entry point."""
    if '--rotate' in sys.argv:
        WallpaperManager().rotate_next()
        return 0
    app = FrescoApplication()
    return app.run([a for a in sys.argv if a != '--rotate'])
