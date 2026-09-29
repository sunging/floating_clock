# floating_clock

Windows 桌面**浮动时钟**：始终置顶、半透明、可调大小与透明度，默认**鼠标穿透**
（不影响下层窗口操作），并支持**闹钟**（到点播放提示音 + 弹出提醒）。

基于 **Python + [uv](https://docs.astral.sh/uv/) + PySide6/Qt**。

## 功能

- 无边框、置顶的浮动时钟，背景透明只显示时间文字；不占任务栏，由系统托盘图标控制。
- 字号、整体透明度、文字颜色可调；可选显示秒 / 日期。
- **自动适配背景色**：可按时钟背后屏幕的明暗自动切换深 / 浅文字颜色（两种颜色均可自定义）。
- 默认鼠标穿透：点击会落到下层窗口，时钟不干扰操作。
- **移动时钟**：托盘菜单「移动时钟」临时关闭穿透并显示虚线边框，拖到新位置松手后自动恢复。
  位置会自动记忆，并在显示器唤醒、分辨率变化、插拔屏幕后自动恢复到原位置。
- 闹钟：可添加多个（时间、名称、内容、重复周期），支持单次、每天、工作日或自定义星期重复；
  单次闹钟响过后自动停用。同一分钟到点的多个闹钟会**合并为一次提醒**，不会漏响。
- 闹钟弹出提醒：显示名称、内容和当前时间，内容过长时可滚动；点击时钟或弹窗里的
  「停止闹钟」按钮即可停止。可调提醒文字颜色、背景颜色、背景透明度、闪烁、字号倍率和布局，
  并可在设置里「预览」。
- 提示音：可选无声、系统提示音（多种可选）或自定义 WAV 文件，设置里可「试听」。
- 关屏行为：可配置「屏幕关闭时是否仍响铃」，**默认关屏不响**（避免无人时空响、
  也不消耗单次闹钟）；基于监听 `WM_POWERBROADCAST` 的显示器电源状态。
- 开机自启动：在「设置」里勾选即可（写入当前用户注册表 Run 键，无需管理员权限）。

## 运行

```powershell
# 安装依赖（首次）
uv sync

# 启动
uv run floating-clock
# 或
uv run python -m floating_clock
```

在 Windows 上启动后程序会**自动转入后台**运行（以 `pythonw.exe` 重新启动自身并脱离终端），
命令会立即返回，终端可以继续使用或直接关闭。需要在前台运行（例如调试、查看报错）时：

```powershell
$env:FLOATING_CLOCK_DETACHED = "1"; uv run floating-clock
```

退出程序：右键托盘图标 →「退出」。

### 作为 uv tool 安装

```powershell
uv tool install git+https://github.com/sunging/floating_clock.git
floating-clock
```

升级到仓库最新版本：

```powershell
uv tool upgrade floating-clock
```

卸载：

```powershell
uv tool uninstall floating-clock
```

## 使用说明

- **打开设置**：右键点击系统托盘里的时钟图标 →「设置…」（或双击托盘图标）。
  外观相关的修改会实时预览，点「取消」则还原。
- **移动位置**：托盘菜单 →「移动时钟」，按住时钟拖到目标位置，松手后自动恢复穿透。
  也可以在托盘菜单取消勾选「鼠标穿透」后直接拖动，调整完再勾选回来。
- **调大小 / 透明度 / 颜色**：在「设置」对话框的「外观」区调整。
- **设闹钟**：「设置」对话框 →「闹钟」区 →「新增」，填写时间、名称、内容和
  重复周期；双击列表行可编辑，行首复选框控制启用 / 停用。
- **调闹钟弹出样式**：「设置」对话框 →「闹钟弹出样式」区，调整后点击「预览」查看效果。
- **停止闹钟**：点击弹窗任意位置（开启鼠标穿透时也可以，响铃期间会临时关闭穿透）、
  弹窗里的「停止闹钟」按钮，或托盘菜单 →「停止闹钟」。
- **开机自启动**：「设置」对话框勾选「开机自启动」。脚本运行时会以
  `pythonw.exe -m floating_clock` 注册，打包成 exe 后则注册该 exe 路径。

## 配置文件

设置通过 `QSettings` 保存为 INI 文本文件 `config/config.ini`（便于查看 / 备份 / 迁移），
位置与工作目录无关，开机自启时也读取同一份：

| 运行方式 | 配置文件位置 |
| --- | --- |
| 从源码运行（`uv run`） | 项目根目录下 `config/config.ini`（已在 `.gitignore` 中忽略） |
| 打包的 exe | exe 所在目录下 `config/config.ini`（便携模式） |
| `uv tool install` / pip 安装 | `%APPDATA%\FloatingClock\config\config.ini`（非 Windows：`$XDG_CONFIG_HOME/floating_clock/config/`，默认 `~/.config/floating_clock/config/`） |

配置文件损坏或数值越界时会回退到默认值，不会导致程序无法启动。

## 平台说明

程序面向 **Windows**。以下功能为 Windows 专有，已用 `sys.platform` 守卫：

- 鼠标穿透（Win32 扩展窗口样式 `WS_EX_TRANSPARENT`）
- 提示音（`winsound`）
- 开机自启动（注册表 Run 键）
- 屏幕关闭检测（`WM_POWERBROADCAST`）
- 启动后自动转入后台

在其它平台可正常显示时钟窗口和闹钟弹窗，上述功能会自动跳过（屏幕视为始终开启）。

## 可选：打包为单文件 exe

```powershell
uv run --with pyinstaller pyinstaller --noconsole --onefile `
  --name floating-clock src/floating_clock/__main__.py
```

生成的可执行文件位于 `dist/`。

## 开发

```powershell
uv sync                                           # 安装依赖（含 pytest、ruff）
$env:QT_QPA_PLATFORM = "offscreen"; uv run pytest # 无窗口运行测试
uv run ruff check                                 # 代码检查
```

GitHub Actions 会在推送到 `main` / `develop` 以及每个 PR 时，于 Windows 上用
Python 3.9 和 3.12 运行 lint 与测试。架构说明与开发约定见 [AGENTS.md](AGENTS.md)。
