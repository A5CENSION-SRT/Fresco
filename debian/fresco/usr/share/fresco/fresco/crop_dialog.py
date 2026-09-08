# crop_dialog.py
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
"""A crop-preview dialog: defaults to the whole image (centered, no crop -
the right choice across monitors with different aspect ratios, since GNOME's
own "zoom" background mode already fills each one at render time), with an
optional free-form drag-to-draw crop for trimming composition."""

from gettext import gettext as _

import cairo
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, GdkPixbuf, Gtk


class CropDialog(Adw.Window):
    """Shows `image_path` with a crop rectangle defaulting to the full
    image. Drag anywhere on the image to draw a different rectangle.
    Reports the chosen crop box in the original image's pixel coordinates
    via `on_confirm(crop_box, skip_remaining)`."""

    def __init__(self, image_path, on_confirm, on_cancel=None, remaining_count=0):
        super().__init__(modal=True, default_width=760, default_height=560,
                          title=_('Crop Wallpaper'))
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel or (lambda: None)
        self._skip_remaining = False

        self.pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(image_path))
        self.img_w, self.img_h = self.pixbuf.get_width(), self.pixbuf.get_height()


        self.crop_offset_x = 0.0
        self.crop_offset_y = 0.0
        self.crop_w = float(self.img_w)
        self.crop_h = float(self.img_h)

        self._display = (0.0, 0.0, 1.0, 1.0, 1.0)
        self._drag_anchor = (0.0, 0.0)
        self._drag_start_widget = (0.0, 0.0)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)

        cancel_button = Gtk.Button(label=_('Cancel'))
        cancel_button.connect('clicked', self._on_cancel_clicked)
        header.pack_start(cancel_button)

        reset_button = Gtk.Button(label=_('Use Full Image'))
        reset_button.set_tooltip_text(
            _('Skip cropping and apply the whole image, centered'))
        reset_button.connect('clicked', self._on_reset_clicked)
        header.pack_start(reset_button)

        confirm_button = Gtk.Button(label=_('Apply'))
        confirm_button.add_css_class('suggested-action')
        confirm_button.connect('clicked', self._on_confirm_clicked)
        header.pack_end(confirm_button)
        toolbar_view.add_top_bar(header)

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_hexpand(True)
        self.drawing_area.set_vexpand(True)
        self.drawing_area.set_draw_func(self._on_draw)

        drag = Gtk.GestureDrag()
        drag.connect('drag-begin', self._on_drag_begin)
        drag.connect('drag-update', self._on_drag_update)
        self.drawing_area.add_controller(drag)

        if remaining_count > 0:
            bottom_bar = Gtk.CenterBox()
            bottom_bar.set_margin_top(8)
            bottom_bar.set_margin_bottom(8)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.set_halign(Gtk.Align.CENTER)
            switch = Gtk.Switch()
            switch.set_valign(Gtk.Align.CENTER)
            switch.connect('notify::active',
                            lambda s, p: setattr(self, '_skip_remaining', s.get_active()))
            label = Gtk.Label(label=_('Use the full image (no crop) for the other {}')
                               .format(remaining_count))
            row.append(switch)
            row.append(label)
            bottom_bar.set_center_widget(row)
            toolbar_view.add_bottom_bar(bottom_bar)

        toolbar_view.set_content(self.drawing_area)
        self.set_content(toolbar_view)


    def _on_draw(self, area, cr, width, height):
        scale = min(width / self.img_w, height / self.img_h)
        disp_w, disp_h = self.img_w * scale, self.img_h * scale
        off_x, off_y = (width - disp_w) / 2, (height - disp_h) / 2
        self._display = (off_x, off_y, disp_w, disp_h, scale)

        cr.save()
        cr.translate(off_x, off_y)
        cr.scale(scale, scale)
        Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
        cr.paint()
        cr.restore()

        crop_x = off_x + self.crop_offset_x * scale
        crop_y = off_y + self.crop_offset_y * scale
        crop_w = self.crop_w * scale
        crop_h = self.crop_h * scale

        cr.set_source_rgba(0, 0, 0, 0.6)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.rectangle(off_x, off_y, disp_w, disp_h)
        cr.rectangle(crop_x, crop_y, crop_w, crop_h)
        cr.fill()

        cr.set_source_rgb(1, 1, 1)
        cr.set_line_width(2)
        cr.rectangle(crop_x, crop_y, crop_w, crop_h)
        cr.stroke()


    def _widget_to_image(self, wx, wy):
        off_x, off_y, _disp_w, _disp_h, scale = self._display
        x = max(0.0, min((wx - off_x) / scale, self.img_w))
        y = max(0.0, min((wy - off_y) / scale, self.img_h))
        return x, y

    def _on_drag_begin(self, gesture, start_x, start_y):
        self._drag_start_widget = (start_x, start_y)
        self._drag_anchor = self._widget_to_image(start_x, start_y)

    def _on_drag_update(self, gesture, offset_x, offset_y):
        start_wx, start_wy = self._drag_start_widget
        cx, cy = self._widget_to_image(start_wx + offset_x, start_wy + offset_y)
        ax, ay = self._drag_anchor

        x0, x1 = sorted((ax, cx))
        y0, y1 = sorted((ay, cy))
        if x1 - x0 < 1 or y1 - y0 < 1:
            return
        self.crop_offset_x = x0
        self.crop_offset_y = y0
        self.crop_w = x1 - x0
        self.crop_h = y1 - y0
        self.drawing_area.queue_draw()

    def _on_reset_clicked(self, button):
        self.crop_offset_x = 0.0
        self.crop_offset_y = 0.0
        self.crop_w = float(self.img_w)
        self.crop_h = float(self.img_h)
        self.drawing_area.queue_draw()

    def _on_confirm_clicked(self, button):
        crop_box = (self.crop_offset_x, self.crop_offset_y, self.crop_w, self.crop_h)
        self.close()
        self._on_confirm(crop_box, self._skip_remaining)

    def _on_cancel_clicked(self, button):
        self.close()
        self._on_cancel()
