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

import subprocess
import sys

from gettext import gettext as _

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gio, GLib, Gtk

from .wallpaper_manager import WallpaperManager
from .window import FrescoWindow

ROTATE_TIMER_UNIT = 'com.Fresco.v1.rotate.timer'


class FrescoApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(application_id='com.Fresco.v1',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/com/Fresco/v1')
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
                                application_icon='com.Fresco.v1',
                                developer_name='Snehal-Reddy',
                                version='0.1.0',
                                # Translators: Replace "translator-credits" with your name/username, and optionally an email or URL.
                                translator_credits = _('translator-credits'),
                                developers=['Snehal-Reddy'],
                                copyright='© 2026 Snehal-Reddy')
        about.present(self.props.active_window)

    def on_preferences_action(self, widget, _param):
        """Callback for the app.preferences action.

        Automatic rotation is scheduled by the com.Fresco.v1.rotate.timer
        systemd --user unit, enabled automatically on first launch; this
        just surfaces that state and lets it be toggled by hand.
        """
        win = self.props.active_window
        enabled = self._timer_active()
        dialog = Adw.AlertDialog(
            heading=_('Automatic Rotation'),
            body=_('Fresco rotates to the next wallpaper every 24 hours '
                   'using a systemd --user timer, so it keeps working even '
                   'when this window is closed.\n\nStatus: {}').format(
                       _('On') if enabled else _('Off')),
        )
        dialog.add_response('close', _('Close'))
        dialog.add_response('toggle', _('Turn Off') if enabled else _('Turn On'))
        if enabled:
            dialog.set_response_appearance('toggle', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect('response', self._on_preferences_response)
        dialog.present(win)

    def _on_preferences_response(self, dialog, response):
        if response == 'toggle':
            if self._timer_active():
                self._run_systemctl('disable', '--now')
            else:
                self._run_systemctl('enable', '--now')

    def on_shortcuts_action(self, *args):
        """Callback for the app.shortcuts action."""
        builder = Gtk.Builder.new_from_resource('/com/Fresco/v1/shortcuts-dialog.ui')
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
        self._run_systemctl('enable', '--now')

    def _timer_active(self):
        result = self._run_systemctl('is-active', check=False)
        return result is not None and result.returncode == 0

    def _run_systemctl(self, action, *extra_args, check=False):
        try:
            return subprocess.run(
                ['systemctl', '--user', action, *extra_args, ROTATE_TIMER_UNIT],
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
