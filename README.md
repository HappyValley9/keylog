# 键盘监听教学 Demo（pynput + PyInstaller / Wine 交叉打包）

> ⚠️ **免责声明**：本项目仅用于信息安全教学演示，**只允许在本人拥有所有权或已获得明确授权的设备上运行学习**。严禁用于监控他人、窃取账号密码等任何违法违规用途。程序不含任何木马特性：不隐藏窗口、不后台静默运行、不开机自启、不联网传输数据，按 ESC 即可停止退出。

## 文件清单

| 文件 | 说明 |
| --- | --- |
| `keylog_demo.py` | 命令行版：监听键盘，控制台实时打印 + 写入本地 `keylog.txt` |
| `keylog_gui.py` | GUI 托盘版：窗口实时显示 + 写日志，可最小化到托盘（图标常驻可见） |
| `requirements.txt` | 打包时需要安装到 Wine 内 Windows Python 的依赖 |
| `build.sh` | 一键打包脚本（`./build.sh` 打命令行版；`./build.sh keylog_gui` 打 GUI 版） |
| `assets/` | 图标素材：`app.ico`（exe 图标，多尺寸）、`keyboard-white.png`（运行时合成托盘/窗口图标）、`keyboard.svg` / `tabler-keyboard.png`（原始素材）。键盘图标来自 [Tabler Icons](https://github.com/tabler/tabler-icons)（MIT License，经官方 npm 包 `@tabler/icons-png` 获取），深色瓷砖与状态角标为本项目用 Pillow 合成 |
| `README.md` | 本文档 |

## 程序行为（Windows 10 端运行说明）

1. 双击 `keylog_demo.exe`（或在 cmd 中运行），**弹出可见的控制台窗口**，无需管理员权限。
2. 启动后先显示免责声明，**输入 `yes` 确认同意后才开始运行**；输入其他内容或直接关窗即退出，不记录任何内容。
3. 正常敲键盘：控制台实时逐键回显，同时写入 exe 同目录下的 `keylog.txt`（UTF-8 编码，记事本可直接打开）。
4. 特殊按键以 `[方括号大写]` 标记：`[SPACE]` `[ENTER]` `[TAB]` `[BACKSPACE]` `[SHIFT]` `[CTRL]` `[ALT]` `[CAPSLOCK]` `[WIN]` 方向键等；回车会在日志中换行，每行行首带 `[HH:MM:SS]` 时间戳（停顿超过 30 秒会另起新行打新时间戳）。
5. 按 **Ctrl+C** 或直接关闭窗口停止并退出；**ESC 不再是停止键**，会被正常记录为 `[ESC]`。日志每次写入即 flush，异常退出也不丢数据。

日志示例：

```
==== 会话开始 2026-10-13 17:30:01 ====
hello world[ENTER]
my[TAB]pass[SHIFT]!123[ENTER]
[BACKSPACE][BACKSPACE]3[ENTER]
==== 会话结束 2026-10-13 17:31:00（共 42 个按键）====
```

## 打包完整流程（Ubuntu → Windows exe）

原理：PyInstaller 本身不支持跨平台打包，因此在 Ubuntu 上用 **Wine 运行 Windows 版 Python**，再在 Wine 里运行 Windows 版 PyInstaller，产出原生 Windows exe。

### 0. 安装依赖（Ubuntu 侧，需要 sudo）

```bash
sudo apt-get update
sudo apt-get install -y wine64        # 只需 64 位 wine，无需 i386 多架构
```

### 1. 初始化独立 Wine 前缀

```bash
export WINEPREFIX="$HOME/.wine-pybuild"
export WINEARCH="win64"
export WINEDLLOVERRIDES="mscoree,mshtml="   # 禁止 wine-mono/gecko 弹窗
[ -d "$WINEPREFIX" ] || wineboot -u
```

### 2. 下载并静默安装 Windows Python 3.11.9（64 位）

```bash
curl -fL -o python-3.11.9-amd64.exe \
    https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
wine python-3.11.9-amd64.exe /quiet InstallAllUsers=1 \
    TargetDir=C:/Python311 PrependPath=1 Include_test=0
```

> 3.11.9 是 3.11 系列最后一个提供官方 Windows 安装器的版本。

### 3. 在 Wine 内安装 Python 依赖

```bash
wine C:/Python311/python.exe -m pip install --upgrade pip setuptools wheel
wine C:/Python311/python.exe -m pip install pynput==1.7.7 pyinstaller==6.10.0
```

### 4. 打包命令

```bash
wine C:/Python311/python.exe -m PyInstaller \
    --onefile --console --clean --noconfirm \
    --name keylog_demo keylog_demo.py
```

参数说明：`--onefile` 打成单个独立 exe（约 10 MB）；`--console` **保留控制台窗口**（前台可见程序的硬性要求，绝不使用 `--noconsole`/`--windowed`）；`--clean` 清理上次缓存；`--noconfirm` 覆盖旧产物。

产物：`dist/keylog_demo.exe`，拷贝到 Windows 10 即可独立运行（目标机无需安装 Python）。

### 一键执行

以上全部步骤等价于在项目目录执行：

```bash
chmod +x build.sh
./build.sh
```

## 打包注意事项

1. **架构必须全程一致**：64 位 Ubuntu + 64 位 Wine + 64 位 Windows Python，产出的 exe 只能运行在 x64 的 Windows 上（Win10 绝大多数都是 x64）。若需 32 位 exe，Ubuntu 侧要额外启用 i386 多架构并安装 32 位依赖，复杂度翻倍，一般没必要。
2. **Wine 前缀独立、弹窗禁用**：脚本使用 `WINEPREFIX=$HOME/.wine-pybuild` 独立前缀；`WINEDLLOVERRIDES="mscoree,mshtml="` 避免 wineboot 时弹出 .NET/HTML 组件安装框。
3. **无显示器环境**：纯命令行的 Ubuntu 上 `wineboot` 会打印一些显示相关的警告，一般可忽略；若卡住，可 `sudo apt install xvfb` 后用 `xvfb-run ./build.sh`。
4. **首次运行较慢**：初始化 Wine 前缀 + 静默装 Python + pip 下载，总计约几分钟。
5. **pip 慢**：可加 `-i https://pypi.tuna.tsinghua.edu.cn/simple` 镜像。
6. **Wine 内无法真实验证键盘钩子**：打包产物建议拷到真机 Windows 10 做最终功能验证，Wine 里只负责"产出 exe"这一步。
7. **项目路径不能含中文**：Wine 的 `BeginUpdateResourceW`（exe 图标嵌入）对非 ASCII 路径会报伪错误 `winerror 0`。本项目目录名含中文（"键盘记录"），因此 `build.sh` 会先把源码拷到纯 ASCII 的 `/tmp/kl_exe_build` 打包，再把 exe 拷回 `dist/`——这是脚本内置行为，无需手动处理；若手工执行打包命令，请在 ASCII 路径下进行。
8. **杀毒软件会处理 dist 目录**：在 Linux 上没有影响，但 exe 一旦进入 Windows（U 盘、网络传输、压缩包）就可能被杀软静态扫描删除，属预期现象，见下节。

## GUI 托盘版（keylog_gui.py）

`keylog_demo.py` 的图形界面版本，记录逻辑、日志格式与命令行版完全一致，界面行为如下：

1. 双击运行后**先弹出免责声明页**：点「我已阅读并同意，继续使用」进入主界面；点「不同意，退出」或直接关窗即退出，不记录任何内容。
2. 主界面（深色卡片式）：顶部大号状态（● 红色=记录中，带呼吸灯闪烁 / ○ 灰色=已停止）与会话时长走表，中部三张统计卡片（本次按键 / 累计按键 / 特殊按键，**不显示按键内容**），底部"开始记录 / 停止记录 / 打开日志 / 收进托盘 / 退出"按钮——按钮可用性随记录状态自动启停；已适配 Windows 高分屏，窗口启动居中，含程序图标。
3. **最小化到托盘**：点"最小化到托盘"或窗口"X"，窗口收进右下角托盘，**托盘图标常驻显示**——红色 = 正在记录，灰色 = 已停止；左键点击图标恢复主窗口，右键菜单可"显示主窗口 / 退出程序"。
4. **停止/退出不设热键**：ESC 等按键照常记录为 `[ESC]`，停止用「停止记录」按钮，退出用「退出」按钮或托盘菜单；关闭窗口只是收进托盘（托盘右键可退出）。
4. 打包命令（GUI 程序无控制台窗口，可见性由主窗口 + 托盘图标保证）：

```bash
./build.sh keylog_gui
# 等价于：
wine C:/Python311/python.exe -m PyInstaller \
    --onefile --noconsole --clean --noconfirm \
    --hidden-import pystray._win32 --name keylog_gui keylog_gui.py
```

> `--noconsole` 在 GUI 版中是正常选择（GUI 程序本就不该带黑色控制台）；程序的"可见性承诺"由**启动免责声明页、可见主窗口、常驻托盘图标**共同承担——**请勿移除这三条设计**，去掉任何一条它就变成了另一种性质的东西。

## ⚠️ 风险提示（重要，请务必阅读）

- **Windows Defender 及其他杀毒软件会把该 exe 识别为风险程序并拦截/隔离**。原因有二：其一是行为特征（程序注册全局键盘钩子属于典型的键盘记录行为）；其二是 PyInstaller 打包的未签名程序本身特征高危。典型报法：`Trojan:Win32/...`、`HackTool:Win32/...`、`Behavior:Win32/Keylogging` 之类。
- 这是**教学演示的预期现象，不代表程序真的有恶意行为**，但也正说明了此类威胁的真实性。处理方式（仅限本人测试机）：Windows 安全中心 → 病毒和威胁防护 → 管理设置 → 排除项 → 添加该 exe 所在文件夹；**演示完成后请立即删除排除项**。
- 首次运行可能还有 SmartScreen"未知发布者"提示：点"更多信息"→"仍要运行"（程序无数字签名所致）。
- **请勿将该 exe 分发给他人**——无签名 + 键盘钩子行为，必然被拦截，且脱离"本人授权设备学习"的场景即属违规使用。
- 日志文件 `keylog.txt` 含敏感输入内容，学习结束后请自行删除。

## 防御视角的学习延伸

这个 Demo 同时演示了为什么终端防护要关注：全局键盘钩子的注册行为（EDR/Defender 行为检测的立足点）、未签名 PyInstaller 程序的高风险特征、以及"最小权限 + 不运行来路不明的 exe"这条最朴素也最有效的防线。
