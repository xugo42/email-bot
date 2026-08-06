# -*- coding: utf-8 -*-
"""
邮箱配置测试工具
先改好 config.py 里的邮箱信息，再运行本脚本，确认账号/授权码/服务器都填对了。
"""
import sys
import smtplib
from imapclient import IMAPClient
import config

# 让输出用 UTF-8，避免在 Windows 控制台下因 GBK 编码崩溃
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("=" * 50)
print("开始测试邮箱配置……")
print(f"邮箱地址：{config.EMAIL_ADDR}")
print(f"IMAP 服务器：{config.IMAP_SERVER}:{config.IMAP_PORT}")
print(f"SMTP 服务器：{config.SMTP_SERVER}:{config.SMTP_PORT}")
print("=" * 50)

print("\n[1/2] 测试 IMAP 收信连接……")
try:
    server = IMAPClient(config.IMAP_SERVER, port=config.IMAP_PORT, ssl=True, timeout=30)
    server.login(config.EMAIL_ADDR, config.EMAIL_AUTH_CODE)
    # 网易邮箱(163/126)要求发送 ID 命令声明客户端身份，否则报 Unsafe Login
    server.id_({"name": "MailBot", "version": "1.0"})
    server.select_folder("INBOX")
    count = len(server.search(["ALL"]))
    print(f"  [OK] IMAP 收信正常（收件箱 {count} 封邮件）")
    server.logout()
except Exception as e:
    print(f"  [FAIL] IMAP 连接失败：{e}")
    print("  请检查：")
    print("    1. EMAIL_ADDR 是否填对（含 @ 后缀）")
    print("    2. EMAIL_AUTH_CODE 是否填了『授权码』而不是登录密码")
    print("    3. IMAP_SERVER / IMAP_PORT 是否与你的邮箱对应")

print("\n[2/2] 测试 SMTP 发信连接……")
try:
    server = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT, timeout=30)
    server.login(config.EMAIL_ADDR, config.EMAIL_AUTH_CODE)
    print("  [OK] SMTP 发信正常")
    server.quit()
except Exception as e:
    print(f"  [FAIL] SMTP 连接失败：{e}")
    print("  请检查 SMTP_SERVER / SMTP_PORT 是否正确。")

print("\n" + "=" * 50)
print("测试完成。两项都 ✅ 即可正常使用。")
print("=" * 50)
input("按回车键退出……")
