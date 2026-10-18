project('floating-clock', 'cpp',
  version: files('version.txt'),
  meson_version: '>=1.9.0',
  default_options: ['cpp_std=c++17', 'warning_level=3', 'werror=true', 'buildtype=debugoptimized'])

qt = import('qt6')
qt_modules = ['Core', 'Gui', 'Widgets', 'Network']
if host_machine.system() != 'windows'
  qt_modules += 'Multimedia'
endif
if get_option('tests')
  qt_modules += 'Test'
endif
if get_option('static_qt')
  if host_machine.system() != 'windows'
    error('The static SDK configuration currently targets Windows only')
  endif
  qt_base = dependency('qt6', version: '==6.12.0', method: 'qmake', static: true,
    modules: qt_modules)
  python = import('python').find_installation()
  static_args = run_command(python, files('scripts/static_qt_link.py'),
    qt_base.get_variable(configtool: 'QT_INSTALL_PREFIX'), qt_modules,
    check: true).stdout().strip().split('\n')
  qt_dep = declare_dependency(
    dependencies: qt_base.partial_dependency(compile_args: true, includes: true),
    link_args: static_args)
  add_project_arguments('-DFC_STATIC_QT', language: 'cpp')
  add_project_link_arguments('-static', '-Wl,--gc-sections', language: 'cpp')
else
  qt_dep = dependency('qt6', version: '>=6.12.0', modules: qt_modules,
    include_type: 'system')
endif
qt_runtime_path = ''
if host_machine.system() != 'windows'
  qt_runtime_path = qt_dep.get_variable(configtool: 'QT_INSTALL_LIBS', pkgconfig: 'libdir')
endif
cpp = meson.get_compiler('cpp')
if cpp.get_id() == 'msvc'
  add_project_arguments('/utf-8', language: 'cpp')
endif
conf = configuration_data()
conf.set_quoted('FC_VERSION', meson.project_version())
conf.set('FC_VERSION_TUPLE', ','.join(meson.project_version().split('.') + ['0']))
configure_file(output: 'version.h', configuration: conf)
inc = include_directories('src', '.')
subdir('src')
if get_option('tests')
  subdir('tests/cpp')
endif
