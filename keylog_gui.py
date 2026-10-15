# -*- coding: utf-8 -*-
"""
=====================================================================
【免责声明】
本程序是一个信息安全教学演示程序（Demo），仅用于展示键盘监听
类程序的基本工作原理，帮助学习者理解此类威胁并提升防护意识。

使用限制（务必阅读并遵守）：
1. 仅限在本人拥有所有权、或已获得设备所有者明确授权的设备上
   运行与学习；
2. 严禁用于监控他人、窃取他人账号密码等任何违法违规用途，
   由此产生的一切法律责任由使用者自行承担；
3. 可见性保证（本程序的诚实性边界，不可移除）：
   - 程序启动先显示免责声明，点击同意后才进入主界面；
   - 主窗口始终可见，绝不启动即隐藏；
   - 最小化到托盘后，托盘图标常驻显示、颜色标明记录状态，
     点击即可恢复主窗口，右键菜单可随时退出；
4. 不开机自启、不向任何远程地址传输数据、不做任何免杀处理。

图标素材：assets/keyboard-white.png 及 app.ico 基于 Tabler Icons 的
keyboard 图标重着色合成（https://github.com/tabler/tabler-icons ，MIT License）。
=====================================================================
"""

import os
import queue
import sys
from datetime import datetime

import tkinter as tk
from tkinter import messagebox

from pynput import keyboard
from PIL import Image, ImageDraw
import pystray

# ------------------------- 基本配置 -------------------------

APP_NAME = "键盘监听教学 Demo"          # 产品名
APP_VERSION = "1.2"

LOG_FILE_NAME = "keylog.txt"           # 日志文件（写在 exe / 脚本所在目录）

ICON_ASSET = os.path.join("assets", "keyboard-white.png")   # 键盘字形（Tabler，MIT）

STAMP_FMT = "%H:%M:%S"                 # 日志内时间戳格式
IDLE_STAMP_SEC = 30                    # 打字停顿超过该秒数时补一个时间锚点

# 界面配色（深色工具风）
C_BG = "#1c1c22"                       # 窗口背景
C_CARD = "#26262e"                     # 卡片背景
C_BORDER = "#34343e"                   # 卡片描边
C_TEXT = "#e8e8ec"                     # 主文字
C_DIM = "#8a8a94"                      # 次要文字
C_BTN = "#3a3a46"                      # 普通按钮
C_BTN_HI = "#4a4a58"                   # 按钮悬停/按下
C_ACCENT = "#3f6ea5"                   # 主行动按钮（同意/开始）

COLOR_RECORDING = "#e5484d"            # 记录中：红
COLOR_RECORDING_HI = "#ff7b81"         # 记录中呼吸灯亮色
COLOR_STOPPED = "#8a8a94"              # 已停止：灰

# 字体（Windows 优先；缺失时 tkinter 自动回退默认字体）
F_UI = "Microsoft YaHei UI"
F_MONO = "Consolas"

# 常见特殊按键 -> 日志标记文本（与命令行版 keylog_demo.py 保持一致）
SPECIAL_KEYS = {
    "space":        "[SPACE]",
    "enter":        "[ENTER]",
    "esc":          "[ESC]",
    "tab":          "[TAB]",
    "backspace":    "[BACKSPACE]",
    "delete":       "[DELETE]",
    "insert":       "[INSERT]",
    "shift":        "[SHIFT]",
    "shift_l":      "[SHIFT]",
    "shift_r":      "[SHIFT]",
    "ctrl":         "[CTRL]",
    "ctrl_l":       "[CTRL]",
    "ctrl_r":       "[CTRL]",
    "alt":          "[ALT]",
    "alt_l":        "[ALT]",
    "alt_r":        "[ALT]",
    "alt_gr":       "[ALTGR]",
    "caps_lock":    "[CAPSLOCK]",
    "cmd":          "[WIN]",
    "cmd_l":        "[WIN]",
    "cmd_r":        "[WIN]",
    "print_screen": "[PRTSC]",
    "num_lock":     "[NUMLOCK]",
    "up":           "[UP]",
    "down":         "[DOWN]",
    "left":         "[LEFT]",
    "right":        "[RIGHT]",
    "home":         "[HOME]",
    "end":          "[END]",
    "page_up":      "[PAGEUP]",
    "page_down":    "[PAGEDOWN]",
}


def get_log_path():
    """日志文件完整路径：exe 取 exe 所在目录，脚本取脚本所在目录。"""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, LOG_FILE_NAME)


def format_key(key):
    """把一次按键格式化为文本：普通字符原样，特殊按键加 [标记]。"""
    ch = getattr(key, "char", None)
    if ch:
        if ch.isprintable():
            return ch
        if 1 <= ord(ch) <= 26:                            # Ctrl+字母
            return "[CTRL+%s]" % chr(ord(ch) + 64)
        return "[CTRL+?]"
    name = getattr(key, "name", None) or "UNKNOWN"
    return SPECIAL_KEYS.get(name, "[%s]" % name.upper())


def make_icon(color):
    """兜底图标（assets 字形缺失时使用）：彩色圆底 + 白色 K 字。"""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=color)
    d.text((24, 16), "K", fill="white")
    return img


def resource_path(rel):
    """资源路径：兼容开发目录与 PyInstaller 打包（--add-data）环境。"""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)


def load_keyboard_glyph():
    """加载 assets 里的白色键盘字形；失败返回 None（由兜底图标顶上）。"""
    try:
        return Image.open(resource_path(ICON_ASSET)).convert("RGBA")
    except Exception:
        return None


def compose_status_icon(glyph, badge_color, size=64):
    """深色圆角瓷砖 + 键盘字形 + 状态角标，作为托盘/窗口图标。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, size - 2, size - 2), radius=size // 5,
                        fill=(58, 58, 70, 255))
    g = glyph.resize((int(size * 0.70), int(size * 0.70)), Image.LANCZOS)
    off = (size - g.width) // 2
    img.alpha_composite(g, (off, off))
    r = size // 7
    cx = cy = size - 2 - r - size // 40
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=badge_color,
              outline=(255, 255, 255, 255), width=max(1, size // 110))
    return img


def enable_high_dpi():
    """Windows 高分屏下让界面清晰（其他平台自动跳过）。"""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def fmt_secs(sec):
    """秒数格式化为 HH:MM:SS。"""
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return "%02d:%02d:%02d" % (h, m, s)


def shorten_path(path, limit=52):
    """长路径截断显示：保留开头与文件名。"""
    if len(path) <= limit:
        return path
    return path[:24] + "…" + path[-(limit - 25):]


class KeyLogGui:
    """带 GUI 的键盘监听演示：启动需先同意免责声明，主界面只显示
    状态与统计，按键内容仅写入日志；停止/退出通过按钮或托盘菜单
    （ESC 等按键照常记录，不承担停止功能）。

    线程模型：tkinter 主循环在主线程；pynput 监听在独立线程，只往
    队列里塞事件；pystray 托盘在独立线程，动作同样只往队列里塞。
    所有 UI / 文件操作统一由主线程的 _poll_queue 处理。
    """

    def __init__(self):
        self.log_path = get_log_path()
        self.recording = False
        self.listener = None
        self.file = None
        self.count = 0                                  # 当前会话按键数
        self.count_total = 0                            # 程序运行以来累计按键数
        self.count_special = 0                          # 当前会话特殊按键数
        self.need_stamp = True                          # 下一个写入的按键前需要补时间戳
        self.last_stamp = datetime.now()                # 上次写时间锚点的时刻
        self.q = queue.Queue()                          # 跨线程事件队列
        self._tray_ready = False                        # 是否已通过免责声明进入主界面
        self._start_time = None                         # 本段记录开始时刻（计时用）
        self._blink_job = None                          # 呼吸灯动画任务 id
        self._timer_job = None                          # 会话时长走表任务 id
        self._blink_on = True

        # 图标：优先用 assets 的 Tabler 键盘字形合成，缺失时回退自绘 K 圆标
        glyph = load_keyboard_glyph()
        if glyph is not None:
            self.icon_rec_img = compose_status_icon(glyph, COLOR_RECORDING)
            self.icon_stop_img = compose_status_icon(glyph, COLOR_STOPPED)
        else:
            self.icon_rec_img = make_icon(COLOR_RECORDING)
            self.icon_stop_img = make_icon(COLOR_STOPPED)

        self._build_window()

    # ------------------- 窗口与页面 -------------------

    def _build_window(self):
        self.root = tk.Tk()
        self.root.title("%s v%s（仅限本人授权设备使用）" % (APP_NAME, APP_VERSION))
        self.root.configure(bg=C_BG)
        self.root.resizable(False, False)

        # 窗口居中显示
        w, h = 680, 380
        self.root.update_idletasks()
        sx = max((self.root.winfo_screenwidth() - w) // 2, 0)
        sy = max((self.root.winfo_screenheight() - h) // 2, 0)
        self.root.geometry("%dx%d+%d+%d" % (w, h, sx, sy))

        # 窗口/任务栏图标（失败不影响运行）；两套状态图随记录状态切换
        try:
            from PIL import ImageTk
            self._photo_rec = ImageTk.PhotoImage(self.icon_rec_img)
            self._photo_stop = ImageTk.PhotoImage(self.icon_stop_img)
            self.root.iconphoto(True, self._photo_stop)
        except Exception:
            pass

        # 点窗口"X"：已进入主界面则收进托盘，还在声明页则直接退出
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        self.root.after(50, self._poll_queue)            # 启动主线程事件泵
        self._show_disclaimer()                          # 先显示免责声明，同意后进主界面

    def _show_disclaimer(self):
        """启动免责声明页：同意后进入主界面，不同意（或关窗）直接退出。"""
        self._disclaimer = tk.Frame(self.root, bg=C_BG)
        self._disclaimer.pack(fill="both", expand=True, padx=28, pady=24)

        head = tk.Frame(self._disclaimer, bg=C_BG)
        head.pack(fill="x")
        tk.Label(head, text=APP_NAME, font=(F_UI, 17, "bold"),
                 fg=C_TEXT, bg=C_BG).pack(side="left")
        tk.Label(head, text="v%s" % APP_VERSION, font=(F_MONO, 11),
                 fg=C_DIM, bg=C_BG).pack(side="left", padx=8, pady=(8, 0))

        card = tk.Frame(self._disclaimer, bg=C_CARD,
                        highlightbackground=C_BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, pady=(14, 4))
        text = ("【免责声明】\n\n"
                "1. 本软件仅用于信息安全教学演示，仅限在本人拥有所有权\n"
                "   或已获得明确授权的设备上运行学习；\n"
                "2. 严禁用于监控他人、窃取账号密码等任何违法违规用途，\n"
                "   由此产生的一切法律责任由使用者自行承担；\n"
                "3. 本软件为前台可见程序：不隐藏窗口、不开机自启、不联\n"
                "   网外传数据，可随时通过按钮或托盘菜单停止并退出。\n\n"
                "点击「我已阅读并同意」即表示你已理解并承诺遵守以上条款。")
        tk.Label(card, text=text, font=(F_UI, 11), fg=C_TEXT, bg=C_CARD,
                 justify="left", anchor="w", padx=18, pady=14
                 ).pack(fill="both", expand=True)

        row = tk.Frame(self._disclaimer, bg=C_BG)
        row.pack(pady=12)
        tk.Button(row, text="  我已阅读并同意，继续使用  ", font=(F_UI, 11, "bold"),
                  fg="#ffffff", bg=C_ACCENT, activebackground=C_BTN_HI,
                  activeforeground="#ffffff", relief="flat", bd=0,
                  padx=10, pady=7, cursor="hand2",
                  command=self._on_agree).pack(side="left", padx=6)
        tk.Button(row, text="不同意，退出", font=(F_UI, 11),
                  fg=C_DIM, bg=C_CARD, activebackground=C_BTN_HI,
                  activeforeground=C_TEXT, relief="flat", bd=0,
                  padx=10, pady=7, cursor="hand2",
                  command=self.root.destroy).pack(side="left", padx=6)

    def _on_agree(self):
        """同意免责声明：进入主界面并启动托盘图标。"""
        self._disclaimer.destroy()
        self._build_main_ui()
        self._build_tray()

    def _build_main_ui(self):
        """主界面：状态行 + 统计卡片 + 操作按钮 + 底部信息。"""
        # 顶部状态行：左侧大号状态（记录中时红点呼吸闪烁），右侧会话时长
        hero = tk.Frame(self.root, bg=C_BG)
        hero.pack(fill="x", padx=22, pady=(20, 8))
        self.status_label = tk.Label(hero, text="○ 已停止",
                                     font=(F_UI, 20, "bold"),
                                     fg=COLOR_STOPPED, bg=C_BG)
        self.status_label.pack(side="left")
        self.time_label = tk.Label(hero, text="00:00:00",
                                   font=(F_MONO, 15), fg=C_DIM, bg=C_BG)
        self.time_label.pack(side="right", pady=(6, 0))

        # 统计卡片行：本次按键 / 累计按键 / 特殊按键
        cards = tk.Frame(self.root, bg=C_BG)
        cards.pack(fill="x", padx=22, pady=8)
        cards.columnconfigure((0, 1, 2), weight=1, uniform="tile")
        self.count_label = self._stat_tile(cards, "本次按键", 0)
        self.total_label = self._stat_tile(cards, "累计按键", 1)
        self.sp_keys_label = self._stat_tile(cards, "特殊按键", 2)

        # 操作按钮行
        btns = tk.Frame(self.root, bg=C_BG)
        btns.pack(fill="x", padx=22, pady=(6, 2))
        self.btn_start = self._btn(btns, "● 开始记录", self._start)
        self.btn_stop = self._btn(btns, "■ 停止记录", self._stop)
        self.btn_stop.configure(state="disabled")
        self._btn(btns, "打开日志", self._open_log)
        self._btn(btns, "收进托盘", self._hide_to_tray)
        tk.Button(btns, text="退出", font=(F_UI, 10), fg=C_DIM, bg=C_CARD,
                  activebackground=C_BTN_HI, activeforeground=C_TEXT,
                  relief="flat", bd=0, padx=12, pady=7, cursor="hand2",
                  command=lambda: self.q.put(("exit", None))
                  ).pack(side="right", padx=4)

        # 底部：日志路径 + 使用范围提醒
        foot = tk.Frame(self.root, bg=C_BG)
        foot.pack(fill="x", padx=22, pady=(8, 14))
        tk.Label(foot, text="日志 " + shorten_path(self.log_path),
                 font=(F_MONO, 9), fg=C_DIM, bg=C_BG).pack(side="left")
        tk.Label(foot, text="仅限本人授权设备学习使用",
                 font=(F_UI, 9), fg="#5c5c66", bg=C_BG).pack(side="right")

    def _stat_tile(self, parent, title, col):
        """一张统计卡片，返回其中数值 Label（便于后续更新）。"""
        card = tk.Frame(parent, bg=C_CARD,
                        highlightbackground=C_BORDER, highlightthickness=1)
        card.grid(row=0, column=col, sticky="nsew", padx=6, pady=6)
        tk.Label(card, text=title, font=(F_UI, 10), fg=C_DIM, bg=C_CARD
                 ).pack(pady=(12, 2))
        value = tk.Label(card, text="0", font=(F_MONO, 21, "bold"),
                         fg=C_TEXT, bg=C_CARD)
        value.pack(pady=(0, 12))
        return value

    def _btn(self, parent, text, command):
        """统一样式的操作按钮，返回按钮对象便于更新可用状态。"""
        btn = tk.Button(parent, text=text, font=(F_UI, 10, "bold"),
                        fg=C_TEXT, bg=C_BTN, activebackground=C_BTN_HI,
                        activeforeground=C_TEXT, relief="flat", bd=0,
                        padx=12, pady=7, cursor="hand2", command=command)
        btn.pack(side="left", padx=4)
        return btn

    def _build_tray(self):
        """托盘图标：常驻可见，左键点击=显示窗口，右键菜单=显示/退出。"""
        self.tray = pystray.Icon(
            "keylog_demo",
            icon=self.icon_stop_img,
            title="%s - 已停止（点击图标显示窗口）" % APP_NAME,
            menu=pystray.Menu(
                pystray.MenuItem("显示主窗口", self._tray_show, default=True),
                pystray.MenuItem("退出程序", self._tray_exit),
            ),
        )
        self.tray.run_detached()                         # 在独立线程运行
        self._tray_ready = True                          # 已进入主界面，此后关窗=收进托盘

    # ------------------- 记录控制 -------------------

    def _start(self):
        if self.recording:
            return
        self.file = open(self.log_path, "a", encoding="utf-8")
        now = datetime.now()
        self.file.write("==== 会话开始 %s ====\n"
                        % now.strftime("%Y-%m-%d %H:%M:%S"))
        self.file.write("[%s] " % now.strftime(STAMP_FMT))    # 行首时间戳
        self.count = 0
        self.count_special = 0
        self.need_stamp = False
        self.last_stamp = now
        self.count_label.configure(text="0")
        self.sp_keys_label.configure(text="0")
        self.time_label.configure(text="00:00:00")
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.start()
        self.recording = True
        self._set_status(True)

    def _stop(self):
        if not self.recording:
            return
        if self.listener:
            self.listener.stop()
            self.listener = None
        self.file.write("\n")                                 # 结束当前未换行的行
        self.file.write("==== 会话结束 %s（本次 %d 个按键）====\n"
                        % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                           self.count))
        self.file.close()
        self.file = None
        self.recording = False
        self._set_status(False)

    def _on_press(self, key):
        """pynput 回调（监听线程）：只往队列塞事件，不做任何 UI/文件操作。"""
        self.q.put(("key", format_key(key)))

    # ------------------- 主线程事件泵 -------------------

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "key" and self.recording:
                    self._record_one(payload)
                elif kind == "show":
                    self.root.deiconify()
                elif kind == "exit":
                    self._shutdown()
                    return
        except queue.Empty:
            pass
        self.root.after(50, self._poll_queue)

    def _record_one(self, text):
        """主线程：写入一个按键并维护行首时间戳与统计卡片。"""
        self.count += 1
        self.count_total += 1
        now = datetime.now()
        # 新起一行，或停顿超过 IDLE_STAMP_SEC 秒时，先补一个时间锚点
        if self.need_stamp or (now - self.last_stamp).total_seconds() >= IDLE_STAMP_SEC:
            if not self.need_stamp:
                self.file.write("\n")                     # 停顿锚点：先结束旧行
            self.file.write("[%s] " % now.strftime(STAMP_FMT))
            self.need_stamp = False
        self.last_stamp = now
        self.file.write(text)
        if text == "[ENTER]":                             # 回车换行，下一行重新打时间戳
            self.file.write("\n")
            self.need_stamp = True
        self.file.flush()                                 # 逐键落盘，异常退出不丢
        self.count_label.configure(text=str(self.count))
        self.total_label.configure(text=str(self.count_total))
        if text.startswith("["):                          # 特殊按键统计
            self.count_special += 1
            self.sp_keys_label.configure(text=str(self.count_special))

    # ------------------- 动画与状态 -------------------

    def _blink_tick(self):
        """记录中红点呼吸灯。"""
        if not self.recording:
            return
        self._blink_on = not self._blink_on
        self.status_label.configure(
            fg=COLOR_RECORDING if self._blink_on else COLOR_RECORDING_HI)
        self._blink_job = self.root.after(600, self._blink_tick)

    def _timer_tick(self):
        """会话时长走表。"""
        if not self.recording or self._start_time is None:
            return
        self.time_label.configure(
            text=fmt_secs((datetime.now() - self._start_time).total_seconds()))
        self._timer_job = self.root.after(1000, self._timer_tick)

    def _set_status(self, recording):
        """同步状态行、窗口/托盘图标、按钮可用性、计时。"""
        # 窗口图标同步切换为红/灰角标版
        if getattr(self, "_photo_rec", None) and hasattr(self.root, "iconphoto"):
            try:
                self.root.iconphoto(
                    True, self._photo_rec if recording else self._photo_stop)
            except Exception:
                pass
        if recording:
            self.status_label.configure(text="● 记录中", fg=COLOR_RECORDING)
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.tray.icon = self.icon_rec_img
            self.tray.title = "%s - 正在记录（点击图标显示窗口）" % APP_NAME
            self._start_time = datetime.now()
            self._blink_on = True
            self._blink_job = self.root.after(600, self._blink_tick)
            self._timer_job = self.root.after(1000, self._timer_tick)
        else:
            self.status_label.configure(text="○ 已停止", fg=COLOR_STOPPED)
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.tray.icon = self.icon_stop_img
            self.tray.title = "%s - 已停止（点击图标显示窗口）" % APP_NAME
            for attr in ("_blink_job", "_timer_job"):
                job = getattr(self, attr, None)
                if job is not None:
                    try:
                        self.root.after_cancel(job)
                    except Exception:
                        pass
                    setattr(self, attr, None)

    # ------------------- 辅助 -------------------

    def _open_log(self):
        """打开日志文件；尚未生成时给出提示。"""
        if not os.path.exists(self.log_path):
            messagebox.showinfo(APP_NAME, "日志文件尚未生成，请先开始记录。")
            return
        if hasattr(os, "startfile"):                      # 仅 Windows 存在此方法
            try:
                os.startfile(self.log_path)
            except Exception as e:
                messagebox.showerror(APP_NAME, "打开日志失败：%s" % e)
        else:
            messagebox.showinfo(APP_NAME, "日志路径：%s" % self.log_path)

    def _hide_to_tray(self):
        if self._tray_ready:
            self.root.withdraw()                         # 窗口收进托盘，图标保持可见
        else:
            self.root.destroy()                          # 免责声明阶段关窗 = 直接退出

    def _tray_show(self, icon=None, item=None):
        self.q.put(("show", None))                       # 托盘线程 -> 队列 -> 主线程

    def _tray_exit(self, icon=None, item=None):
        self.q.put(("exit", None))

    def _shutdown(self):
        self._stop()
        try:
            self.tray.stop()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    enable_high_dpi()                    # 必须在创建任何窗口之前调用才生效
    KeyLogGui().run()
