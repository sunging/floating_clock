test_moc = qt.compile_moc(sources: 'tests.cpp', dependencies: qt_dep,
  extra_args: host_machine.system() == 'windows' ? ['-DQ_OS_WIN'] : [])
test_exe = executable('clock-tests', 'tests.cpp', test_moc, resources, plugin_sources,
  dependencies: clock_dep)
test('clock', test_exe, env: ['QT_QPA_PLATFORM=offscreen'], timeout: 90,
  args: ['-o', 'native-tests.txt,txt', '-o', 'native-tests.xml,junitxml'],
  workdir: meson.current_build_dir())
test('smoke', clock_exe,
  args: ['--smoke-test', '--config', meson.current_build_dir() / 'smoke-config/config.ini'],
  env: ['QT_QPA_PLATFORM=offscreen'], timeout: 30)
