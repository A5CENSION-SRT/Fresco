desktop_file = i18n.merge_file(
        input: 'com.fresco.v1.desktop.in',
      output: 'com.fresco.v1.desktop',
         type: 'desktop',
       po_dir: '../po',
      install: true,
  install_dir: get_option('datadir') / 'applications'
)

desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils, args: [desktop_file])
endif

appstream_file = i18n.merge_file(
        input: 'com.fresco.v1.metainfo.xml.in',
       output: 'com.fresco.v1.metainfo.xml',
       po_dir: '../po',
      install: true,
  install_dir: get_option('datadir') / 'metainfo'
)

appstreamcli = find_program('appstreamcli', required: false, disabler: true)
test('Validate appstream file', appstreamcli,
     args: ['validate', '--no-net', '--explain', appstream_file])

service_conf = configuration_data()
service_conf.set('bindir', get_option('prefix') / get_option('bindir'))
configure_file(
  input: 'com.fresco.v1.service.in',
  output: 'com.fresco.v1.service',
  configuration: service_conf,
  install_dir: get_option('datadir') / 'dbus-1' / 'services'
)

systemd_dep = dependency('systemd', required: false)
if systemd_dep.found()
  systemd_user_unit_dir = systemd_dep.get_variable(pkgconfig: 'systemduserunitdir')
else
  systemd_user_unit_dir = get_option('prefix') / get_option('datadir') / 'systemd' / 'user'
endif

rotate_service_conf = configuration_data()
rotate_service_conf.set('bindir', get_option('prefix') / get_option('bindir'))
configure_file(
  input: 'com.fresco.v1.rotate.service.in',
  output: 'com.fresco.v1.rotate.service',
  configuration: rotate_service_conf,
  install_dir: systemd_user_unit_dir,
)

install_data('com.fresco.v1.rotate.timer',
  install_dir: systemd_user_unit_dir,
)

subdir('icons')
