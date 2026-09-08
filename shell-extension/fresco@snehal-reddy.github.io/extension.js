/* extension.js
 *
 * Fresco Shell integration: a top-bar indicator that can rotate to the
 * next wallpaper or apply a specific one, by talking to the main Fresco
 * app over its D-Bus GApplication action group (com.Fresco.v1, D-Bus
 * activatable, see data/com.Fresco.v1.service.in). No GTK/Python code
 * runs in-process here - this is a separate GJS technology stack.
 */

import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import GObject from 'gi://GObject';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const APP_ID = 'com.Fresco.v1';
const APP_OBJECT_PATH = '/com/Fresco/v1';

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

const WallpanaIndicator = GObject.registerClass(
class WallpanaIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'Fresco');

        this.add_child(new St.Icon({
            icon_name: 'preferences-desktop-wallpaper-symbolic',
            style_class: 'system-status-icon',
        }));

        this._actionGroup = Gio.DBusActionGroup.get(
            Gio.DBus.session, APP_ID, APP_OBJECT_PATH);

        const rotateItem = new PopupMenu.PopupMenuItem(_('Rotate to Next Wallpaper'));
        rotateItem.connect('activate', () => this._activate('rotate-next'));
        this.menu.addMenuItem(rotateItem);

        this._selectSubMenu = new PopupMenu.PopupSubMenuMenuItem(_('Select Wallpaper'));
        this.menu.addMenuItem(this._selectSubMenu);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        const openItem = new PopupMenu.PopupMenuItem(_('Open Fresco…'));
        openItem.connect('activate', () => this._launchApp());
        this.menu.addMenuItem(openItem);

        this.menu.connect('open-state-changed', (menu, isOpen) => {
            if (isOpen)
                this._rebuildWallpaperList();
        });
    }

    _activate(actionName, parameter = null) {
        try {
            this._actionGroup.activate_action(actionName, parameter);
        } catch (e) {
            logError(e, `Fresco: failed to activate ${actionName}`);
        }
    }

    _launchApp() {
        const appInfo = Gio.DesktopAppInfo.new(`${APP_ID}.desktop`);
        if (appInfo)
            appInfo.launch([], global.create_app_launch_context(0, -1));
    }

    _rebuildWallpaperList() {
        this._selectSubMenu.menu.removeAll();

        const config = readConfig();
        const order = config?.order ?? [];
        const current = order[config?.current_index] ?? null;

        if (order.length === 0) {
            const item = new PopupMenu.PopupMenuItem(_('No wallpapers added yet'));
            item.setSensitive(false);
            this._selectSubMenu.menu.addMenuItem(item);
            return;
        }

        for (const name of order) {
            const item = new PopupMenu.PopupMenuItem(name);
            if (name === current)
                item.setOrnament(PopupMenu.Ornament.CHECK);
            item.connect('activate', () =>
                this._activate('apply-wallpaper', GLib.Variant.new_string(name)));
            this._selectSubMenu.menu.addMenuItem(item);
        }
    }
});

export default class WallpanaExtension extends Extension {
    enable() {
        this._indicator = new WallpanaIndicator();
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
