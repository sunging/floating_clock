sources = files(
  'core/model.cpp', 'core/config_store.cpp', 'core/time_source.cpp',
  'core/timers.cpp', 'core/single_instance.cpp', 'platform/services.cpp',
  'ui/clock_window.cpp', 'ui/dialogs.cpp', 'app.cpp',
)
headers = files('core/single_instance.h', 'platform/services.h',
                'ui/clock_window.h', 'ui/dialogs.h', 'app.h')
platform_deps = []
if host_machine.system() == 'windows'
  platform_deps += [cpp.find_library('user32'), cpp.find_library('winmm')]
  add_project_arguments('-D_WIN32_WINNT=0x0A00', '-DNOMINMAX', language: 'cpp')
elif host_machine.system() == 'darwin'
  add_languages('objcpp', required: true)
  add_project_arguments('-std=c++17', '-fobjc-arc', language: 'objcpp')
  sources += files('platform/macos.mm')
  platform_deps += dependency('appleframeworks', modules: ['AppKit', 'CoreGraphics'])
elif host_machine.system() == 'linux'
  platform_deps += [dependency('x11'), dependency('xext'),
    dependency('qt6', modules: ['DBus'], version: '>=6.12.0')]
endif
generated = qt.compile_moc(headers: headers, dependencies: [qt_dep] + platform_deps)
clock_lib = static_library('clock-core', sources, generated,
  include_directories: inc, dependencies: [qt_dep] + platform_deps)
clock_dep = declare_dependency(link_with: clock_lib, include_directories: inc,
  dependencies: [qt_dep] + platform_deps)
resources = qt.compile_resources(sources: '../resources/resources.qrc')
if host_machine.system() == 'windows'
  python = import('python').find_installation()
  windows_qt = get_option('static_qt') ? qt_base : qt_dep
  bundle_args = get_option('static_qt') ? ['--static'] : []
  windows_bundle = configure_file(output: 'windows-bundle.qrc',
    input: '../scripts/embed_windows_resources.py',
    command: [python, '@INPUT@', '--qt',
      windows_qt.get_variable(configtool: 'QT_INSTALL_PREFIX', pkgconfig: 'prefix'),
      '--output', '@OUTPUT@', '--depfile', '@DEPFILE@'] + bundle_args,
    depfile: 'windows-bundle.d')
  resources += qt.compile_resources(sources: windows_bundle)
endif
app_sources = files('main.cpp')
plugin_sources = []
if get_option('static_qt')
  plugin_sources = files('platform/static_plugins.cpp')
  app_sources += plugin_sources
endif
if host_machine.system() == 'windows'
  windows = import('windows')
  app_sources += windows.compile_resources('../resources/windows.rc',
    include_directories: [inc, include_directories('../resources')])
endif
clock_exe = executable('floating-clock', app_sources, resources,
  dependencies: clock_dep, build_rpath: qt_runtime_path,
  win_subsystem: 'windows', install: true)
