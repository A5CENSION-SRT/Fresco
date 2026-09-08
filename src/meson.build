pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'fresco'
gnome = import('gnome')

gnome.compile_resources('fresco',
  'fresco.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'fresco.in',
  output: 'fresco',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

fresco_sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'config.py',
  'wallpaper_manager.py',
  'crop_dialog.py',
]

install_data(fresco_sources, install_dir: moduledir)

install_subdir(
  meson.project_source_root() / 'shell-extension/fresco@snehal-reddy.github.io',
  install_dir: get_option('datadir') / 'gnome-shell/extensions'
)
