import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import GObject from 'gi://GObject';

import {Extension, gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const APP_ID = 'com.fresco.v1';
const APP_OBJECT_PATH = '/com/fresco/v1';

function readConfig() {
    try {
        const path = GLib.build_filenamev(
            [GLib.get_user_config_dir(), 'fresco', 'config.json']);
        const [ok, contents] = GLib.file_get_contents(path);
        if (!ok)
            return null;
        return JSON.parse(new TextDecoder().decode(contents));
    } catch (e) {
        return null;
    }
}

const FrescoIndicator = GObject.registerClass(
class FrescoIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'Fresco');

        this.add_child(new St.Icon({
            icon_name: 'com.fresco.v1-symbolic',
            style_class: 'system-status-icon',
        }));

        this._actionGroup = Gio.DBusActionGroup.get(
            Gio.DBus.session, APP_ID, APP_OBJECT_PATH);

        this._previewBin = new St.Bin({
            style_class: 'fresco-preview',
            style: 'width: 220px; height: 130px; border-radius: 8px; '
                + 'background-size: cover; background-position: center;',
        });
        const previewItem = new PopupMenu.PopupBaseMenuItem({
            reactive: false,
            can_focus: false,
        });
        previewItem.add_child(this._previewBin);
        this.menu.addMenuItem(previewItem);

        const rotateItem = new PopupMenu.PopupMenuItem(_('Rotate to Next Wallpaper'));
        rotateItem.connect('activate', () => {
            this._activate('rotate-next');
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 300, () => {
                this._updatePreview();
                return GLib.SOURCE_REMOVE;
            });
        });
        this.menu.addMenuItem(rotateItem);

        this.menu.connect('open-state-changed', (menu, isOpen) => {
            if (isOpen)
                this._updatePreview();
        });
    }

    _activate(actionName, parameter = null) {
        try {
            this._actionGroup.activate_action(actionName, parameter);
        } catch (e) {
            logError(e, `Fresco: failed to activate ${actionName}`);
        }
    }

    _updatePreview() {
        const config = readConfig();
        const order = config?.order ?? [];
        const current = order[config?.current_index] ?? null;

        if (!current || !config?.wallpapers_dir) {
            this._previewBin.set_style(
                'width: 220px; height: 130px; border-radius: 8px;');
            return;
        }

        const path = GLib.build_filenamev([config.wallpapers_dir, current]);
        const uri = Gio.File.new_for_path(path).get_uri();
        this._previewBin.set_style(
            'width: 220px; height: 130px; border-radius: 8px; '
            + 'background-size: cover; background-position: center; '
            + `background-image: url("${uri}");`);
    }
});

export default class FrescoExtension extends Extension {
    enable() {
        this._indicator = new FrescoIndicator();
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
