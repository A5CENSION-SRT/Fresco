application_id = 'com.fresco.v1'
icon_name = application_id

scalable_dir = 'hicolor' / '512x512' / 'apps'
install_data(
  scalable_dir / ('@0@.png').format(icon_name),
  install_dir: get_option('datadir') / 'icons' / scalable_dir
)

symbolic_dir = 'hicolor' / 'symbolic' / 'apps'
install_data(
  symbolic_dir / ('@0@-symbolic.svg').format(icon_name),
  install_dir: get_option('datadir') / 'icons' / symbolic_dir
)
