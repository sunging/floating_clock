test_moc = qt.compile_moc(sources: 'tests.cpp', dependencies: qt_dep,
  extra_args: host_machine.system() == 'windows' ? ['-DQ_OS_WIN'] : [])
test_exe = executable('clock-tests', 'tests.cpp', test_moc, resources, plugin_sources,
  dependencies: clock_dep, build_rpath: qt_runtime_path)
test('clock', test_exe, env: ['QT_QPA_PLATFORM=offscreen'], timeout: 90,
  args: ['-o', 'native-tests.txt,txt', '-o', 'native-tests.xml,junitxml'],
  workdir: meson.current_build_dir())
test('smoke', clock_exe,
  args: ['--smoke-test', '--config', meson.current_build_dir() / 'smoke-config/config.ini'],
  env: ['QT_QPA_PLATFORM=offscreen'], timeout: 30)
if host_machine.system() == 'windows'
  native_ui_moc = qt.compile_moc(sources: 'windows_ui.cpp', dependencies: qt_dep)
  native_ui_exe = executable('windows-ui-tests', 'windows_ui.cpp', native_ui_moc,
    resources, plugin_sources, dependencies: clock_dep)
endif
