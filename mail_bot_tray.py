# -*- coding: utf-8 -*-
"""
邮件机器人 · 后台托盘版
运行后无黑窗口，右下角托盘（隐藏图标区）出现小图标：
  右键菜单 → 查看日志 / 退出
日志写入：机器人日志.txt
"""
import sys
import os

# pythonw 没有控制台，先把输出重定向到日志文件
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "机器人日志.txt")
try:
    _log = open(LOG_FILE, "a", encoding="utf-8")
    sys.stdout = _log
    sys.stderr = _log
except Exception:
    pass

import threading
import config
import mail_bot
import pystray
from PIL import Image, ImageDraw


def _run_bot():
    """后台运行机器人主循环。"""
    try:
        mail_bot.main()
    except Exception:
        import traceback
        traceback.print_exc()


def _on_open_log(icon, item):
    try:
        os.startfile(LOG_FILE)
    except Exception:
        pass


def _on_quit(icon, item):
    icon.stop()
    os._exit(0)


def _load_icon():
    """加载托盘图标：优先用 config.TRAY_ICON_PATH 指定的图片，否则生成默认信封图标。"""
    custom = getattr(config, "TRAY_ICON_PATH", "")
    if custom and os.path.isfile(custom):
        try:
            return Image.open(custom)
        except Exception:
            pass
    # 项目目录自带的图标文件（邮件机器人托盘图标.png），放一张即可自动使用
    bundled_icon = os.path.join(BASE_DIR, "邮件机器人托盘图标.png")
    if os.path.isfile(bundled_icon):
        try:
            return Image.open(bundled_icon)
        except Exception:
            pass
    try:
        img = Image.new("RGBA", (64, 64), (24, 120, 207, 255))
        d = ImageDraw.Draw(img)
        # 白色信封
        d.rectangle([6, 16, 58, 50], fill=(255, 255, 255, 255), outline=(16, 90, 160, 255), width=2)
        # 信封口折线
        d.line([6, 16, 32, 35, 58, 16], fill=(16, 90, 160, 255), width=2)
        return img
    except Exception:
        return Image.new("RGB", (64, 64), (16, 120, 200))


def main():
    threading.Thread(target=_run_bot, daemon=True).start()

    image = _load_icon()

    menu = pystray.Menu(
        pystray.MenuItem("查看日志", _on_open_log),
        pystray.MenuItem("退出", _on_quit),
    )
    icon = pystray.Icon("MailBot", image, "邮件取件机器人", menu)
    icon.run()


if __name__ == "__main__":
    main()
