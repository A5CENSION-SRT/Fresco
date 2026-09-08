# WallPana

A native GNOME wallpaper engine. WallPana keeps a managed folder of
wallpapers and rotates your desktop background every 24 hours, with
manual controls and a crop preview before anything is applied.

## Features

- **Managed wallpaper folder** — add images via a file picker (they're
  copied into `~/.local/share/wallpana/wallpapers/`), remove them, and
  browse them as a thumbnail grid.
- **Automatic 24h rotation** — a `systemd --user` timer
  (`com.WallPana.v1.rotate.timer`) runs `wallpana --rotate` once a day.
  It's enabled automatically the first time you launch the app, and it
  keeps working whether or not the app window is open, and survives
  sleep/suspend (`Persistent=true`, so a missed tick fires on resume).
- **Manual controls** — a header-bar button to rotate to the next
  wallpaper immediately, and click-to-apply on any thumbnail for
  interactive selection.
- **Crop preview** — every import goes through a crop dialog. The crop
  region matches your primary display's aspect ratio; drag it to choose
  what's kept. Right-click a thumbnail to re-crop it later from its
  original.
- **GNOME Shell top-bar widget** — a separate GJS extension
  (`shell-extension/`) that can rotate or apply a specific wallpaper
  from the top bar without opening the app, by calling the app's D-Bus
  action group.

## Architecture decisions made

- **Scheduling**: `systemd --user` timer + `wallpana --rotate`, not an
  in-app timer, so rotation keeps happening when the app isn't running.
  The same `WallpaperManager` class backs both the CLI rotate path and
  the GUI.
- **Persistence**: plain JSON at `~/.config/wallpana/config.json`
  (wallpapers dir, rotation order, current index, last-swap timestamp).
- **Smooth transition**: not implemented — wallpapers are applied as an
  instant swap via `org.gnome.desktop.background`. GNOME doesn't expose
  a crossfade for this key; a custom compositor-level fade was out of
  scope for a first pass.
- **Multi-monitor**: not handled — the crop target and the applied
  wallpaper both use the primary monitor's geometry. All monitors get
  the same picture.
- **Cropping**: originals are stashed in
  `~/.local/share/wallpana/wallpapers/.originals/`, and the managed
  folder holds only the already-cropped PNGs that get applied directly
  (this is what lets `--rotate` run headlessly, with no Gdk/display
  dependency).

## Building

```sh
meson setup _build --prefix="$HOME/.local"
ninja -C _build install
wallpana
```

## GNOME Shell extension

The extension lives in `shell-extension/wallpana@snehal-reddy.github.io/`
and is not installed by the Meson build. To try it:

```sh
cp -r shell-extension/wallpana@snehal-reddy.github.io \
  ~/.local/share/gnome-shell/extensions/
```

Then log out and back in (Wayland needs a shell restart to notice a new
extension directory), and enable it with:

```sh
gnome-extensions enable wallpana@snehal-reddy.github.io
```

It only lists wallpapers/rotates once the main WallPana app has been
launched at least once (it reads `~/.config/wallpana/config.json` and
talks to `com.WallPana.v1` over D-Bus, which is D-Bus-activatable so it
doesn't need to already be running).

## Known gaps / next steps

- No crossfade transition on wallpaper swap.
- No per-monitor cropping for multi-monitor setups.
- The Shell extension's "Select Wallpaper" submenu reads the config file
  directly rather than through a dedicated D-Bus query interface —
  fine for a single-user desktop app, but worth revisiting if the
  config format changes.
- No Preferences UI beyond an automatic-rotation on/off toggle.
