#!/usr/bin/env bash
# =====================================================================
# 一键脚本：在 Ubuntu 上通过 Wine 交叉打包 Windows 版 keylog_demo.exe
#
# 用法：  ./build.sh              打包命令行版（keylog_demo）
#         ./build.sh keylog_gui   打包 GUI 托盘版（keylog_gui）
# 前提：  当前用户具备 sudo 权限（仅用于安装 wine64，可提前手动安装）
# 产物：  dist/<程序名>.exe
# =====================================================================
set -euo pipefail

# -------- 可按需调整的参数 --------
APP_NAME="${1:-keylog_demo}"                # keylog_demo 或 keylog_gui
PY_VER="3.11.9"                            # 3.11 系列最后一个提供 Windows 安装器的版本
PY_DIR="C:/Python311"                      # Wine 内 Windows Python 的安装目录
STAGE="/tmp/kl_exe_build"                  # 纯 ASCII 临时打包目录（第 6 步在此打包再拷回）
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine-pybuild}"   # 独立 wine 前缀，不污染默认前缀
export WINEARCH="win64"                    # 全程 64 位：64 位 wine + 64 位 Python
export WINEDLLOVERRIDES="mscoree,mshtml="  # 禁止 wine-mono / gecko 弹出安装提示
export WINEDEBUG="-all"                    # 关闭 wine 调试日志输出
# ----------------------------------

cd "$(dirname "$0")"                       # 切到本脚本所在目录（即项目目录）

echo "==> [1/6] 安装宿主机依赖（需要 sudo）"
if ! command -v wine >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y wine64
fi

echo "==> [2/6] 初始化 Wine 前缀：$WINEPREFIX"
[ -d "$WINEPREFIX" ] || wineboot -u

echo "==> [3/6] 下载并静默安装 Windows Python $PY_VER 到 Wine 中"
CACHE_DIR="$HOME/.pybuild-cache"
INSTALLER="$CACHE_DIR/python-$PY_VER-amd64.exe"
mkdir -p "$CACHE_DIR"
if [ ! -f "$INSTALLER" ]; then
    curl -fL --progress-bar -o "$INSTALLER" \
        "https://www.python.org/ftp/python/$PY_VER/python-$PY_VER-amd64.exe"
fi
if [ ! -f "$WINEPREFIX/drive_c/Python311/python.exe" ]; then
    # /quiet 静默安装；InstallAllUsers=1 装到 C:\Python311；PrependPath=1 加入 PATH
    wine "$INSTALLER" /quiet InstallAllUsers=1 TargetDir="$PY_DIR" PrependPath=1 Include_test=0
fi

echo "==> [4/6] 验证 Wine 内 Python"
wine "$PY_DIR/python.exe" -V

echo "==> [5/6] 安装 Python 依赖（pynput + pyinstaller）"
wine "$PY_DIR/python.exe" -m pip install --upgrade pip setuptools wheel
wine "$PY_DIR/python.exe" -m pip install -r requirements.txt
# 网络较慢时可改用国内镜像，把上一行替换为：
#   wine "$PY_DIR/python.exe" -m pip install -r requirements.txt \
#       -i https://pypi.tuna.tsinghua.edu.cn/simple

echo "==> [6/6] PyInstaller 打包（前台程序：命令行版带控制台，GUI 版带窗口+托盘图标）"
# 注意：项目路径含中文（"键盘记录"），Wine 的 BeginUpdateResourceW（exe 图标嵌入）
# 对非 ASCII 路径会报伪错误（winerror 0），因此统一拷到纯 ASCII 的 /tmp 目录打包，
# 完成后再把 exe 拷回项目的 dist/ 目录
rm -rf "$STAGE"
mkdir -p "$STAGE" dist
cp "$APP_NAME.py" "$STAGE/"
ICON_ARGS=""
if [ -f assets/app.ico ]; then
    cp -r assets "$STAGE/"
    ICON_ARGS="--icon assets/app.ico"
fi
if [ "$APP_NAME" = "keylog_gui" ]; then
    # GUI 版：无控制台窗口，可见性由主窗口 + 常驻托盘图标保证；
    # pystray 的 Windows 后端是动态导入，需显式声明给 PyInstaller；
    # --add-data 携带 assets（运行时合成托盘/窗口状态图标；分隔符用 Windows 的 ";"）
    ( cd "$STAGE" && wine "$PY_DIR/python.exe" -m PyInstaller \
        --onefile --noconsole --clean --noconfirm $ICON_ARGS \
        --add-data "assets;assets" \
        --hidden-import pystray._win32 --name "$APP_NAME" "$APP_NAME.py" )
else
    # 命令行版：--console 保留控制台窗口
    ( cd "$STAGE" && wine "$PY_DIR/python.exe" -m PyInstaller \
        --onefile --console --clean --noconfirm $ICON_ARGS \
        --name "$APP_NAME" "$APP_NAME.py" )
fi
cp "$STAGE/dist/${APP_NAME}.exe" dist/

echo ""
echo "打包完成：$(pwd)/dist/${APP_NAME}.exe"
echo "请复制到 Windows 10 测试机运行（会触发杀毒软件告警，处理方式见 README.md）。"
