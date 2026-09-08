# window.py
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
from gettext import gettext as _

from gi.repository import Adw, GdkPixbuf, Gio, GLib, Gtk

from .crop_dialog import CropDialog

THUMB_HEIGHT = 500
THUMB_BOX_WIDTH = 340
THUMB_BOX_HEIGHT = 210


@Gtk.Template(resource_path='/com/Fresco/v1/window.ui')
class FrescoWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'FrescoWindow'

    toast_overlay = Gtk.Template.Child()
    main_stack = Gtk.Template.Child()
    flow_box = Gtk.Template.Child()
    scrolled_window = Gtk.Template.Child()

    def __init__(self, manager, **kwargs):
        super().__init__(**kwargs)
        self.manager = manager
        self._thumb_cache = {}

        add_action = Gio.SimpleAction.new('add-wallpaper', None)
        add_action.connect('activate', lambda a, p: self.on_add_wallpaper())
        self.add_action(add_action)

        rotate_action = Gio.SimpleAction.new('rotate-next', None)
        rotate_action.connect('activate', lambda a, p: self.on_rotate_next())
        self.add_action(rotate_action)

        self.refresh()


    def on_add_wallpaper(self):
        dialog = Gtk.FileDialog(title=_('Select Wallpaper Images'))
        image_filter = Gtk.FileFilter()
        image_filter.set_name(_('Images'))
        image_filter.add_pixbuf_formats()
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(image_filter)
        dialog.set_filters(filters)
        dialog.set_default_filter(image_filter)
        dialog.open_multiple(self, None, self._on_files_chosen)

    def _on_files_chosen(self, dialog, result):
        try:
            files = dialog.open_multiple_finish(result)
        except GLib.Error:
            return
        paths = [f.get_path() for f in files if f.get_path()]
        self._import_next(paths)

    def _import_next(self, paths):
        if not paths:
            self.refresh()
            return
        path = paths.pop(0)
        original, stem = self.manager.import_wallpaper(path)

        def on_confirm(crop_box, skip_remaining):
            dest = self.manager.finish_import(stem, original, crop_box)
            if not self.manager.current_name():
                self.manager.apply(dest.name)
            if skip_remaining and paths:
                self._import_remaining_uncropped(paths)
            else:
                self._import_next(paths)

        def on_cancel():
            self._import_next(paths)

        dialog = CropDialog(original, on_confirm, on_cancel, remaining_count=len(paths))
        dialog.set_transient_for(self)
        dialog.present()

    def _import_remaining_uncropped(self, paths):
        """Import the rest of a bulk-add batch with no crop dialog at all -
        each one gets applied as its own full image, centered."""
        count = len(paths)
        for path in paths:
            original, stem = self.manager.import_wallpaper(path)
            crop_box = self.manager.full_crop_box(original)
            self.manager.finish_import(stem, original, crop_box)
        self.refresh()
        self.toast_overlay.add_toast(
            Adw.Toast.new(_('Imported {} more wallpapers').format(count)))

    def on_recrop(self, name):
        original = self.manager._find_original(name) or self.manager.path_for(name)

        def on_confirm(crop_box, skip_remaining):
            self.manager.recrop(name, crop_box)
            if name == self.manager.current_name():
                self.manager.apply(name)
            self.refresh()

        dialog = CropDialog(original, on_confirm, lambda: None)
        dialog.set_transient_for(self)
        dialog.present()


    def on_rotate_next(self):
        name = self.manager.rotate_next()
        self.refresh()
        if name:
            self.toast_overlay.add_toast(Adw.Toast.new(_('Rotated to {}').format(name)))
        else:
            self.toast_overlay.add_toast(Adw.Toast.new(_('No wallpapers to rotate to')))

    def on_wallpaper_clicked(self, button, name):
        self.manager.apply(name)
        self.refresh()
        self.toast_overlay.add_toast(Adw.Toast.new(_('Applied {}').format(name)))

    def on_remove(self, name):
        self.manager.remove_wallpaper(name)
        self.refresh()
        self.toast_overlay.add_toast(Adw.Toast.new(_('Removed {}').format(name)))


    def refresh(self):
        vadjustment = self.scrolled_window.get_vadjustment()
        scroll_position = vadjustment.get_value()

        child = self.flow_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.flow_box.remove(child)
            child = next_child

        names = self.manager.list_wallpapers()
        self.main_stack.set_visible_child_name('grid' if names else 'empty')
        self._thumb_cache = {k: v for k, v in self._thumb_cache.items() if k in names}
        current = self.manager.current_name()
        for name in names:
            self.flow_box.append(self._build_item(name, name == current))


        GLib.idle_add(self._restore_scroll_position, vadjustment, scroll_position)

    def _restore_scroll_position(self, vadjustment, scroll_position):
        upper = max(0.0, vadjustment.get_upper() - vadjustment.get_page_size())
        vadjustment.set_value(min(scroll_position, upper))
        return GLib.SOURCE_REMOVE

    def _thumbnail_pixbuf(self, name):
        """A small, pre-scaled pixbuf for the grid, cached by (name, mtime)
        so switching/rotating doesn't re-decode full-resolution wallpapers
        on every refresh."""
        path = self.manager.path_for(name)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None
        cached = self._thumb_cache.get(name)
        if cached and cached[0] == mtime:
            return cached[1]
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(path), -1, THUMB_HEIGHT, True)
        except GLib.Error:
            return None
        self._thumb_cache[name] = (mtime, pixbuf)
        return pixbuf

    def _build_item(self, name, is_current):
        pixbuf = self._thumbnail_pixbuf(name)
        picture = Gtk.Picture.new_for_pixbuf(pixbuf) if pixbuf else Gtk.Picture()

        picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        picture.set_size_request(THUMB_BOX_WIDTH, THUMB_BOX_HEIGHT)
        picture.set_hexpand(False)
        picture.set_vexpand(False)

        overlay = Gtk.Overlay()

        overlay.set_size_request(THUMB_BOX_WIDTH, THUMB_BOX_HEIGHT)
        overlay.set_halign(Gtk.Align.CENTER)
        overlay.set_valign(Gtk.Align.CENTER)
        overlay.set_child(picture)
        if is_current:
            check = Gtk.Image.new_from_icon_name('object-select-symbolic')
            check.set_halign(Gtk.Align.END)
            check.set_valign(Gtk.Align.START)
            check.set_margin_top(6)
            check.set_margin_end(6)
            check.add_css_class('accent')
            check.add_css_class('osd')
            overlay.add_overlay(check)

        button = Gtk.Button()
        button.set_child(overlay)
        button.set_halign(Gtk.Align.CENTER)
        button.set_valign(Gtk.Align.CENTER)
        button.add_css_class('flat')
        button.set_tooltip_text(name)
        button.connect('clicked', self.on_wallpaper_clicked, name)

        click = Gtk.GestureClick.new()
        click.set_button(3)
        click.connect('pressed', self._on_secondary_click, name, button)
        button.add_controller(click)

        return button

    def _on_secondary_click(self, gesture, n_press, x, y, name, widget):
        popover = Gtk.Popover()
        popover.set_parent(widget)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        recrop_btn = Gtk.Button(label=_('Recrop…'))
        recrop_btn.add_css_class('flat')
        recrop_btn.connect('clicked', lambda b: (popover.popdown(), self.on_recrop(name)))
        remove_btn = Gtk.Button(label=_('Remove'))
        remove_btn.add_css_class('flat')
        remove_btn.add_css_class('destructive-action')
        remove_btn.connect('clicked', lambda b: (popover.popdown(), self.on_remove(name)))
        box.append(recrop_btn)
        box.append(remove_btn)
        popover.set_child(box)
        popover.popup()
