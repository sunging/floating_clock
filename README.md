# floating_clock

Windows 桌面**浮动时钟**：始终置顶、半透明、可调大小与透明度，默认**鼠标穿透**
（不影响下层窗口操作），并支持**闹钟**（到点播放提示音 + 时钟文字闪烁提醒）。

基于 **Python + [uv](https://docs.astral.sh/uv/) + PySide6/Qt**。

## 功能

- 无边框、置顶的浮动时钟，背景透明只显示时间文字。
- 字号、整体透明度、文字颜色可调；可选显示秒 / 日期。
- 默认鼠标穿透：点击会落到下层窗口，时钟不干扰操作。
- 系统托盘图标提供控制入口：设置、切换穿透/锁定移动、停止闹钟、退出。
- 闹钟：可添加多个（时间、名称、内容、重复周期），支持单次、每天、工作日或
  自定义星期重复；到点播放提示音并按自定义弹出样式提醒。
- 闹钟弹出样式：可调提醒文字颜色、背景颜色、背景透明度、闪烁、字号倍率和布局，
  并可在设置里预览。
- 提示音：可选无声、系统提示音（多种可选）或自定义 WAV 文件，设置里可「试听」。
- 关屏行为：可配置「屏幕关闭时是否仍响铃」，**默认关屏不响**（避免无人时空响、
  也不消耗单次闹钟）；基于监听 `WM_POWERBROADCAST` 的显示器电源状态。
- 开机自启动：在「设置」里勾选即可（写入当前用户注册表 Run 键，无需管理员权限）。
- 设置通过 `QSettings` 持久化为程序目录下 `config/config.ini`（INI 文本，便于查看/迁移；与工作目录无关，开机自启也读取同一份；已在 `.gitignore` 中忽略）。

## 运行

```powershell
# 安装依赖（首次）
uv sync

# 启动
uv run floating-clock
# 或
uv run python -m floating_clock
```

如果想直接从 Git 仓库安装为 uv tool，可以使用：

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
- **移动 / 调整位置**：在托盘菜单取消勾选「鼠标穿透」后，可直接用鼠标拖动时钟；
  调整完再勾选回穿透即可。位置会自动记忆。
- **调大小 / 透明度 / 颜色**：在「设置」对话框里调整，确认后立即生效。
- **设闹钟**：「设置」对话框 →「闹钟」区 →「新增」，填写时间、名称、内容和
  重复周期；列表前的复选框控制启用 / 停用。
- **调闹钟弹出样式**：「设置」对话框 →「闹钟弹出样式」区，调整颜色、背景、
  闪烁、字号倍率和布局后可点击「预览」查看效果。
- **开机自启动**：「设置」对话框勾选「开机自启动」。脚本运行时会以
  `pythonw.exe -m floating_clock` 注册，打包成 exe 后则注册该 exe 路径。

## 平台说明

程序面向 **Windows**：鼠标穿透（Win32 扩展窗口样式）与提示音（`winsound`）为
Windows 专有，已用 `sys.platform` 守卫。在其它平台可正常显示时钟窗口，但这两项功能
会自动跳过。

## 可选：打包为单文件 exe

```powershell
uv run --with pyinstaller pyinstaller --noconsole --onefile ^
  --name floating-clock src/floating_clock/__main__.py
```

生成的可执行文件位于 `dist/`。
