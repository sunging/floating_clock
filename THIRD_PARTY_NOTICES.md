# Third-party components

Floating Clock is licensed under GNU AGPL-3.0; see `LICENSE`. The icon and built-in reminder sound
were created for this project.

Windows releases statically link Qt 6.12.0 Core, Gui, Widgets, Network, platform/style plugins and
the MinGW runtime. The static Qt Base build uses its GPL-3.0 licensing option. The application
remains AGPL-3.0, with build scripts and corresponding application source supplied with releases.
Releases also include the complete, hash-verified corresponding Qt Base source.

`static-qt-build.json` records the source, configuration and compiler version. It is embedded in
the Windows EXE together with license texts and third-party notices. Use About and licenses in
the control panel to read, copy or export them offline. `scripts/build_static_qt.py` documents the
build needed to recompile, modify and relink the static SDK.

Linux/macOS dynamically link Qt and also use Qt Multimedia. Compatible Qt shared libraries can
be substituted. Windows WAV playback uses WinMM and does not require Qt Multimedia or FFmpeg.

- Qt uses LGPL-3.0, GPL-3.0 and other terms depending on the component. The supplied Qt licenses and attribution files identify the applicable terms. See [Qt licensing](https://doc.qt.io/qt-6/licensing.html) and the [Qt 6.12.0 source archives](https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/).
- Qt Multimedia deployment may include FFmpeg. See the configuration, licenses and attribution notices in [Qt Multimedia third-party components](https://doc.qt.io/qt-6/qtmultimedia-index.html#licenses-and-attributions).
- Windows statically links the MinGW-w64/GCC 15.1 runtime. GCC libraries use the GPL with the GCC Runtime Library Exception; MinGW-w64 files have their own terms. See the [GCC Runtime Library Exception](https://www.gnu.org/licenses/gcc-exception-3.1.html) and [MinGW-w64 source](https://www.mingw-w64.org/downloads/).

The Windows EXE embeds application and Qt attribution notices plus the original MinGW-w64, GCC
and winpthreads runtime license texts. Linux/macOS packaging copies licenses, attribution notices
and binary SPDX JSON inventories from the SDK into the package's `licenses` directory, excluding
duplicate inventory formats and complete SDK source-file inventories.

Build, test and signing tools are used only during development and distribution. They are not
Python runtime dependencies of the application. Translation catalog text is user-interface data;
the unmodified Qt Chinese catalog retains its original copyright and license terms.
