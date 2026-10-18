# C++ 迁移验证

本地验证环境：Windows x64、Qt 6.12.0、MinGW-w64 15.1.0 UCRT、Meson 1.9.1、Ninja 1.13.0。
验证日期：2026-10-18，版本 0.2.0。本地验证不能作为跨平台构建或已公开发行的证明。

## 自动验证

- Windows 静态 Qt Test：121 项通过，0 失败、0 跳过，包含 4 项原生 WAV 后端测试；另有独立的 Meson 启动烟雾测试。
- Windows 桌面集成测试：100% 和 150% 缩放下各 20 项通过，覆盖实际黑白背景取色、3 种字号、4 档透明度，以及关闭穿透和移动模式的系统鼠标命中、拖动。修复前这两种模式的透明边缘命中测试均失败。
- 构建与发布脚本：35 项通过。其中 21 项发布校验覆盖平台完整性、提交/版本及哈希、单文件分发、EXE/ZIP 一致、Qt 对应源码、草稿查找及重试、版本 PR 派发检查，以及远端上传状态、完整资产集合和 SHA-256；异常时保留草稿。
- 其余脚本测试包括 3 项静态链接、4 项内嵌资源、4 项下载及失败清理、3 项 SDK 架构选择和缓存复用；覆盖私有库、资源对象、许可与翻译、含空格路径及失效 SDK。实际 Meson 集成测试验证修改许可文件后会自动重新生成内嵌资源。
- C++ 格式检查、编译警告视为错误、构建脚本 Ruff、Actions actionlint 检查通过。
- 测试前后实际 `config/config.ini` 内容保持不变；声音、自启动和时间源使用替身。
- 已检查 100% 和 150% 缩放的设置、控制面板和长提醒内容布局。

| 行为 | 自动覆盖位置 |
| --- | --- |
| 旧 INI/JSON、重复规则、稳定 ID、损坏文件备份与保存失败 | `tests/cpp/tests.cpp` 的 config / alarm 测试 |
| 各条提醒独立到期、合并时的独立声音资格及触发快照、静音、音频失败 | independentReminderDeadlines / appNewAlarmDoesNotExtendOld / appMergedReminderSoundEligibility / appMergedReminderSoundSnapshot / silentAndFailedSoundStillExpire |
| Windows 系统声音、中文 WAV 路径、内置音回退、音频失败与超时停止 | nativeWaveSystemAndStop / nativeWaveCustomAndFallback / nativeWaveSilentAndUnavailableDevice / nativeWaveTimeoutCleanup |
| 单次闹钟在设置及嵌套编辑器打开期间被消耗 | settingsCommitDuringAlarm / nestedEditorPreservesConsumption |
| 设置取消、预览停止、穿透偏好还原 | settingsCancelRestoresAppearanceAndStopsPreview / appRingingTimeoutAndPreferences |
| 关屏抑制、未知电源状态、唤醒后清理 | appScreenOffAndWake / appCountdownDuringSleep |
| 校时、倒计时重启、秒表暂停恢复和计次 | countdownLifecycleAndClockChanges / countdownRestart / stopwatchRestartAndLaps |
| 较新版本的配置及计时状态禁止被旧版覆盖 | failedSaveAndFutureSchema / futureRuntimeIsPreserved |
| 负坐标、长内容、滚动条、无托盘退出、配置目录隔离 | geometry / popupBoundaries / popupKeepsScrollAtBottom / noTrayRetainsControlUntilQuit / singleInstanceIsolation |
| 自动取色即时预览、移动后刷新、采样失败保留颜色、交互透明度还原及拖动保存位置 | autoColorRefreshAndFailure / interactiveSurfaceRestoresTransparency / appDragPersistsPosition |
| Windows 原生透明区域鼠标命中及黑白背景捕获 | `tests/cpp/windows_ui.cpp`；使用独立测试窗口，不移动真实鼠标、不访问用户配置、声音或自启动 |
| 静态 Qt、Windows/离屏/样式插件、按钮图标和拖动光标资源 | qtLinkageAndStaticPlugins；发行包启动测试 |
| 内嵌中文翻译、完整许可文本及只读查看界面 | embeddedWindowsTranslationAndLicenses；发行包启动测试 |

Windows 单一 EXE 和 ZIP 已在本地生成，ZIP 中只有一个 `floating-clock.exe`，与单独发布的 EXE 字节一致。
打包过程校验 ZIP 完整性，解压到仅含 EXE 的中文含空格目录并重命名后启动，
清除 SDK 的 PATH 与 Qt 插件路径，以该空目录为工作目录，确认应用版本、Qt 版本、Windows 平台插件及内嵌资源可用。
启动完成后该目录仍只有 EXE，没有解压出的 DLL、翻译或许可文件。
所有烟雾启动都使用独立配置和静音服务，不安装应用、不改真实自启动。

## Windows 发行包体积优化

使用十进制 MB（1 MB = 1,000,000 字节）。初次优化移除 Qt Multimedia、FFmpeg 和多余部署依赖，
动态 Qt ZIP 从 33.07 MB 缩小到 15.77 MB。当前 Windows 正式包改为静态 Qt 单文件：

| 产物 | 动态 Qt 优化版 | 当前单文件版 |
| --- | --- | --- |
| 附带 DLL | 9 个 | **0 个** |
| 便携 ZIP | 15.77 MB | **8.61 MB** |
| 解压后文件总计 | 42.85 MB | **21.53 MB** |
| 运行所需文件 | EXE、DLL、翻译、许可目录等 | **一个 EXE** |

Windows WAV 改用 WinMM，移除 Qt Multimedia 和 FFmpeg 依赖，保留系统声音、自定义 WAV、内置音回退及循环停止。
打包时剥离应用符号，ZIP 使用最高 Deflate 压缩等级。

新包已从解压结果启动，检查中文翻译、Qt 版本、图标和声音资源；二进制导入表仅含 Windows 系统组件。
真实音频输出仍属于下面的实机验收范围；自动播放测试全部使用替身。

Windows 的 Qt Base、平台/样式插件和 MinGW 运行库静态链接，关闭未使用的 OpenGL、
Vulkan、SQL 等功能。Qt Base 源码及中文翻译均按锁定哈希验证，构建参数记录在 SDK 与包内的
`static-qt-build.json`；应用通过 Meson Qt 模块生成元对象和资源，并读取 SDK 的静态私有依赖清单。
中文翻译、应用和第三方许可文本以及构建记录也嵌入 EXE，控制面板支持离线查看、复制和导出许可。
翻译和许可输入由 Meson 依赖文件跟踪，源码统一使用 LF，避免 Windows 检出后改变锁定的翻译源码哈希。
Windows 安装脚本、安装测试和相应工具下载已移除，不生成安装程序；保留动态 Qt 作为开发构建选项。
Qt Base 的 51.22 MB 对应源码作为独立发行文件，不放入 EXE 或 ZIP；发布校验会核对其哈希。

## CI 与实机验收边界

四目标工作流、Linux ASan/UBSan、DEB 安装/升级/卸载保留配置检查，以及 Release 草稿到公开发行的校验已配置。
Windows CI 增加原生桌面测试及 150% 缩放测试，与离屏测试分别记录报告，避免只验证 Qt 事件处理而遗漏系统鼠标命中。
发布复用的构建工作流包含 ASan/UBSan，任一构建或检查失败均不会进入公开发布。
已核对 Qt 官方 6.12 SDK 元数据：Linux 下载架构为 `linux_gcc_64`，安装目录仍是 `gcc_64`；Wayland 客户端在基础 SDK 中。
Linux/macOS 构建及发行包、正式签名、公证、线上 Actions 和首发尚未在本地 Windows 环境实际执行。
这些结果须以推送后对应提交的 Actions 报告为准，不能由工作流语法检查代替。

实机仍需验证：物理关屏与休眠、实际扬声器播放、自定义 WAV 设备兼容性、不同 DPI 显示器热插拔与拖动、
Linux 各桌面托盘/Wayland 行为、macOS 屏幕录制权限允许与拒绝。DEB 安装生命周期仅在一次性 CI runner 执行。
