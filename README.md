# Floating Clock

基于 **C++17、Qt 6.12 Widgets、Meson + Ninja** 的桌面浮动时钟，支持 Windows、Linux 和 macOS。
应用运行不需要 Python；Python 3.12+ 仅用于 Meson 和构建、打包脚本。

## 功能

- 无边框、透明、置顶浮窗；托盘控制，托盘不可用时自动显示控制面板。
- 字号、文字颜色、透明度、秒和日期显示可调，支持背景自动取色和实时预览，取消设置会还原。
- 鼠标穿透、临时移动模式、多屏位置记忆，以及显示器唤醒、缩放或布局改变后的恢复。
- 多闹钟支持单次、每天、工作日、自定义星期；同时到点的闹钟合并展示。
- **提醒超时**全局默认 60 秒，可设为 1～3600 秒，每个闹钟可以覆盖。各条提醒独立到期，新提醒不会延长旧提醒。
- 提醒文字、背景、透明度、闪烁、字号倍率和布局可调；长内容可滚动，停止按钮保持可见。
- 无声、系统/内置提示音和自定义 WAV；声音不可用时仍显示提醒并提示原因。
- 一个倒计时、一个支持计次的秒表，可与时钟共用浮窗，切换显示不停止后台计时。
- 默认关屏不响，也不消耗单次闹钟；支持用户级自启动、按配置目录隔离的单实例控制。

## 安装与使用

从 [GitHub Releases](https://github.com/sunging/floating_clock/releases) 下载，使用同一版本的 `SHA256SUMS` 验证完整性。

| 平台 | 最低发行环境 | 文件 |
| --- | --- | --- |
| Windows x64 | Windows 10 1809 / Windows 11 | 单一 EXE |
| Linux x64 | Ubuntu 24.04+ 或兼容 glibc 2.39 的桌面环境 | AppImage、DEB |
| macOS Intel | macOS 14.4+ | x64 DMG |
| macOS Apple Silicon | macOS 14.4+ | arm64 DMG |

Windows 下载 EXE 后直接运行。
Qt、平台/样式插件、C++ 运行库、中文翻译、图标、提示音和许可文本均内嵌，无需安装或附带 DLL。
更新前退出应用并替换原位置的 EXE，配置继续保留；旧目录的配置可以从控制面板导入。
删除前可在设置中关闭自启动，退出后删除 EXE 即可，用户配置仍保留。
Linux AppImage 添加执行权限后运行，也可使用 `--appimage-extract-and-run` 在没有 FUSE 的环境运行。
DEB 使用 `sudo apt install ./floating-clock-*.deb` 安装。macOS 将 DMG 中的应用拖入「应用程序」。

首版默认 Windows 未签名，macOS 临时签名。macOS 如阻止首次打开，可在系统设置「隐私与安全性」对该应用选择「仍要打开」。
发行包的签名状态记录在 `build-info.json`。

- **控制面板**：托盘菜单「控制面板…」，或对可点击的浮窗右键；无托盘时关闭控制面板会退出应用。
- **移动**：托盘「移动时钟」或控制面板「移动浮窗」，拖动后恢复原穿透偏好。
- **自动取色**：在设置「外观」中勾选「自动适配背景色」，默认关闭。开启、预览或移动结束后立即更新，平时每 2 秒重新采样。
- **停止提醒**：点击提醒、停止按钮或托盘菜单；不操作也会在期限内停止声音、闪烁和弹窗。
- **计时**：控制面板分别提供倒计时和秒表页，顶部选择浮窗显示内容。
- **退出**：控制面板或托盘「退出」；存在托盘时关闭控制面板只会隐藏它。
- **关于与许可**：控制面板「关于与许可…」显示版本及许可说明；Windows 可离线查看、复制或导出完整许可文本。

## 计时规则

运行中的倒计时、秒表和提醒超时使用包含系统休眠时间的单调时钟，系统校时不会改变计时进度。
普通闹钟按本地时间工作，不补发错过的分钟，同一闹钟在同一分钟只触发一次。

- 倒计时和秒表支持暂停、继续、重置。退出前保存状态，运行中每 5 秒保存检查点。
- 重启后倒计时按保存的结束时间继续；已过期只显示完成、不补响。
- 秒表恢复累计时间和计次，保持暂停。异常终止可能丢失最后一个检查点之后的少量进度。
- 休眠期间完成的倒计时，或禁止关屏提醒时在关屏期间完成的倒计时，恢复后只显示完成。
- 提醒的超时和声音设置在每次触发时固定，合并后各自保留声音资格；休眠唤醒后清理已超时提醒。静音提醒同样自动结束。
- 预览和试听最多 3 秒，关闭设置时清理，不消耗真实闹钟。

## 配置与迁移

保留旧 QSettings INI 和闹钟 JSON，兼容稳定 ID、旧 `repeat_daily` 字段。
新增 `schema_version`、全局 `alarm_timeout_seconds` 和闹钟可选 `timeout_seconds`，缺失时使用默认值。
异常数值回退，重复 ID 修复，无效闹钟条目跳过并提示。

| 模式 | 默认配置位置 |
| --- | --- |
| 可执行文件旁有 `portable.flag` | 可执行文件目录的 `config/config.ini` |
| Windows 单文件版或普通构建 | `%APPDATA%\FloatingClock\config\config.ini` |
| Linux | `$XDG_CONFIG_HOME/floating_clock/config/config.ini`，默认 `~/.config/floating_clock/config/config.ini` |
| macOS | `~/Library/Application Support/FloatingClock/config/config.ini` |

`state.json` 位于 INI 旁，仅保存计时状态。相同配置目录共用实例和计时状态。
`--config <文件>` 显式指定配置，不依赖工作目录。
Windows 单文件版默认将配置保存在用户目录；仍兼容旧版 `portable.flag`，也可用 `--config` 指定随 EXE 保存的位置。

迁移前退出旧 Python 版，在控制面板选择「导入旧配置…」。同路径旧格式首次保存及导入覆盖前会生成 `.bak`，
备份失败取消写入；保存错误会显示在控制面板和托盘通知中。较新版本配置及计时状态不能被旧程序覆盖。
源码版原先位于项目 `config/` 的配置请手动导入。导入不覆盖计时进度，会将自启动设置应用到新可执行文件。

## 平台差异

Windows 使用 Win32 穿透、电源通知、WAV/系统声音和用户 Run 注册表项。音频直接调用系统接口，
发行包无需 Qt Multimedia 和 FFmpeg；保留内置提示音、自定义 WAV、循环播放与超时停止。
macOS 使用 AppKit 穿透与休眠通知、用户 LaunchAgent 自启动（下次登录生效）；自动取色需要屏幕录制权限。
Linux X11 使用桌面置顶/穿透、DPMS 和 logind；自启动写入用户 XDG autostart，AppImage 使用外层文件路径。

Wayland 的绝对定位、强制置顶、持续取色和关屏检测受桌面协议限制；设置中显示限制，拖动交给合成器。
核心计时、声音和提醒继续工作。关屏状态未知时按屏幕开启处理，不将未知误判成关屏。

## 构建与测试

使用 Python 3.12+、Qt **6.12.0**、Meson/Ninja 和 C++17 编译器。
Windows 为 MinGW-w64 15.1 UCRT，Linux 为 GCC 13，macOS 为 Apple Clang。
工具版本在 `scripts/requirements-build.txt`，部署工具及校验和在 `packaging/toolchain.json`。
下面的 Windows 示例将 MinGW-w64 工具链放在仓库的 `.tools/mingw64` 目录；使用其他位置时调整 PATH。

```powershell
python -m venv .tools/build-env
.\.tools\build-env\Scripts\Activate.ps1
python -m pip install -r scripts/requirements-build.txt
python scripts/install_qt.py install-qt windows desktop 6.12.0 win64_mingw --outputdir .tools/qt
$env:PATH = "$PWD\.tools\qt\6.12.0\mingw_64\bin;$PWD\.tools\mingw64\bin;" + $env:PATH
$env:CXX = "g++"
python scripts/build_static_qt.py --jobs 4
$env:PATH = "$PWD\.tools\qt-static\6.12.0\mingw_64\bin;" + $env:PATH
$env:CMAKE_PREFIX_PATH = "$PWD\.tools\qt-static\6.12.0\mingw_64"
meson setup build-static --buildtype=release -Dstatic_qt=true
meson compile -C build-static
python scripts/test.py build-static
.\build-static\src\floating-clock.exe --control
```

`scripts/install_qt.py` 兼容 Qt 6.12 的 Windows SDK 下载目录；`scripts/ci_environment.py` 可下载锁定的完整工具链。
Linux/macOS 将 Qt `bin` 加入 PATH 后使用 `meson setup build --buildtype=release -Dstatic_qt=false`，
再执行 `meson compile -C build` 与 `python scripts/test.py build`；Linux 系统依赖安装命令见 CI。
Qt 6.12 Linux SDK 的下载架构名为 `linux_gcc_64`，解压后的目录仍为 `gcc_64`，由 CI SDK 脚本统一处理。
静态 Qt SDK 首次需从锁定的 Qt Base 源码编译，后续直接复用 `.tools/qt-static`。
源码、配置参数和编译器版本记入 `static-qt-build.json`；SDK 校验失败会阻止复用。
保留 `-Dstatic_qt=false` 的动态 Qt 开发构建选项，Windows 正式发行要求静态构建。

```text
python scripts/check_format.py
python -m ruff check scripts tests/tooling
python -m unittest discover -s tests/tooling -v
python scripts/test.py build-static
python scripts/package.py windows --build build-static --qt .tools/qt-static/6.12.0/mingw_64
```

Windows 另有原生桌面测试，验证透明区域鼠标命中、拖动和黑白背景取色；不会移动真实鼠标或修改用户配置：

```powershell
$env:QT_QPA_PLATFORM = "windows"
.\build-static\tests\cpp\windows-ui-tests.exe
$env:QT_SCALE_FACTOR = "1.5"
.\build-static\tests\cpp\windows-ui-tests.exe
Remove-Item Env:QT_SCALE_FACTOR
Remove-Item Env:QT_QPA_PLATFORM
```

Windows 不生成安装程序；Meson 构建时自动嵌入翻译与许可文本，打包验证单文件独立运行。
Linux 打包用 `xvfb-run -a` 包裹命令；macOS 生成含 Qt 框架的应用和 DMG。
所有自动测试采用临时配置、可注入时间、声音和平台替身。`--smoke-test` 必须附带隔离的 `--config`，
不启用自启动、真实声音和可见浮窗。单实例测试需要环境允许本地命名管道。
验证记录和本地报告保存在已忽略的 `.cache/` 中；文档与代码使用可移植的路径示例，不记录开发机器的个人路径或环境信息。

## CI 与自动发行

`main` / `develop` 推送和 PR 执行四目标编译、Qt Test、格式检查、打包和产物启动检查。
Windows 缓存静态 SDK 及锁定的 Qt Base 源码，工具链或构建配置改变时重新编译；首次构建预留 120 分钟。
Windows 从只有一个 EXE 的中文含空格目录验证启动，不依赖 SDK 路径或外置资源；
Linux 在一次性 CI runner 中验证安装、升级、卸载保留配置，并运行 ASan/UBSan，
预编译 Qt 的全局分配不纳入泄漏检查。物理多屏、显示器关屏、真实音频和 macOS 权限需另做实机验收。

Release Please 根据英文 Conventional Commits 维护版本 PR，统一更新 `version.txt` 和变更记录。
人工合并版本 PR 后创建标签和草稿，以准确提交构建；四目标构建及 Linux ASan/UBSan 全部通过后，验证五个发行文件并上传源码、
Qt Base 对应源码、`build-info.json`、`SHA256SUMS` 并公开 Release。Windows 发行清单只接受单一 EXE；
静态 Qt 的源码不匹配、远端文件缺失或多出文件、SHA-256 不符时阻止发布。
失败保留草稿，可手动运行 Release workflow 填写原标签重试，已公开版本不覆盖。

使用默认 `GITHUB_TOKEN`；版本 PR 显式派发 CI，构建直接调用共享 workflow，不依赖机器人标签事件。
仓库需允许 Actions 创建 PR；发布需要 `contents: write`、`pull-requests: write`，派发检查需要 `actions: write`。
普通构建只读，签名凭据只用于 Release。

| 可选签名 | Secrets |
| --- | --- |
| Windows PFX | `WINDOWS_CERTIFICATE_BASE64`、`WINDOWS_CERTIFICATE_PASSWORD` |
| macOS Developer ID | `MACOS_CERTIFICATE_BASE64`、`MACOS_CERTIFICATE_PASSWORD`、`MACOS_SIGN_IDENTITY` |
| macOS 公证 API | `MACOS_NOTARY_KEY_BASE64`、`MACOS_NOTARY_KEY_ID`、`MACOS_NOTARY_ISSUER` |

未配置时生成首版无证书包。正式 macOS 签名启用后必须同时配置公证；签名或公证失败会阻止发布。
