# 第三方组件

Floating Clock 本身采用仓库 `LICENSE` 中的 GNU AGPL-3.0 许可证。图标和内置提示音为本项目制作。

Windows 发行包静态链接 Qt 6.12.0 的 Core、Gui、Widgets、Network、平台/样式插件及 MinGW 运行库。
静态 Qt Base 采用其 GPL-3.0 许可选项；应用继续采用 AGPL-3.0，构建脚本与对应应用源码随 Release 提供。
Release 另外提供经过哈希验证的 Qt Base 完整源码。`static-qt-build.json` 记录来源、配置和编译器版本，
与完整许可文本一同嵌入 Windows EXE，可在控制面板「关于与许可…」中查看、复制或导出；
可使用仓库中的 `scripts/build_static_qt.py` 重新编译、修改和重新链接。

Linux/macOS 使用动态 Qt，另外使用 Multimedia；Qt 动态库可由兼容版本替换。
Windows WAV 播放使用系统 WinMM，无需 Qt Multimedia 或 FFmpeg。

- Qt：LGPL-3.0 / GPL-3.0 等，具体文件以 Qt 自带许可证和第三方归属说明为准。
  [Qt 许可说明](https://doc.qt.io/qt-6/licensing.html)、[Qt 6.12.0 对应源码](https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/)。
- Qt Multimedia 部署工具可能附带 FFmpeg 库；对应配置、许可证与归属说明见
  [Qt Multimedia 的第三方组件](https://doc.qt.io/qt-6/qtmultimedia-index.html#licenses-and-attributions)。
- Windows 程序静态链接 MinGW-w64 / GCC 15.1 运行库。GCC 库采用 GPL 及 GCC Runtime Library Exception；
  MinGW-w64 的文件另有各自许可证。[GCC 运行库例外](https://www.gnu.org/licenses/gcc-exception-3.1.html)、
  [MinGW-w64 源码](https://www.mingw-w64.org/downloads/)。

Windows EXE 内嵌应用、Qt 第三方归属说明与 MinGW-w64、GCC、winpthreads 运行库的许可证原文。
Linux/macOS 打包脚本将许可证、归属说明与 SDK 提供的二进制 SPDX JSON 清单复制到发行包的 `licenses` 目录；
不附带同一清单的重复格式及完整 SDK 源文件清单。
构建、测试、签名工具仅用于构建，不是应用的 Python 运行依赖。
