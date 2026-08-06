# -*- coding: utf-8 -*-
"""
邮件自动取件机器人（方案 C）
启动后常驻监听邮箱，收到你的指令邮件后自动在电脑上找文件并发回给你。

指令格式（写在新邮件里，标题或正文均可）：
  找 <文件名关键词>        例：找 A05 论文
  列 <文件夹路径>          例：列 C:/Users/<你的用户名>/Desktop
  帮助                     例：帮助

运行环境：Windows + Python 3
"""
from imapclient import IMAPClient
import smtplib
import email
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr
import os
import time
import re
import requests

import sys
import config
import search_files

# 让日志输出用 UTF-8，避免在 Windows 控制台下因 GBK 编码崩溃
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------- 日志 ----------------
def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


# ---------------- 邮件解析 ----------------
def decode_str(s):
    """解码邮件头（标题/发件人）中的乱码。"""
    if not s:
        return ""
    parts = decode_header(s)
    out = []
    for text, charset in parts:
        if isinstance(text, bytes):
            charset = charset or "utf-8"
            try:
                out.append(text.decode(charset))
            except Exception:
                out.append(text.decode("utf-8", "ignore"))
        else:
            out.append(text)
    return "".join(out)


def extract_addr(frm):
    """从「名字 <邮箱>」格式里提取纯邮箱地址。"""
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", frm)
    return m.group(0) if m else frm


def get_body(msg):
    """提取邮件正文纯文本。"""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, "ignore")
                except Exception:
                    continue
        return ""
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, "ignore")
        except Exception:
            return ""


def parse_command(subject, body):
    """从标题+正文解析指令。返回 (cmd, arg)，cmd ∈ {find, download, ask, list, help}。"""
    text = subject.strip() + " " + body.strip()
    first_line = text.splitlines()[0][:500] if text else ""
    first_line = re.sub(r"\s+", " ", first_line)
    m = re.search(r"(?:找|搜索|search)\s*[:：]?\s*(.+)", first_line)
    if m:
        return "find", m.group(1).strip()
    m = re.search(r"(?:发|下载|要|send)\s*[:：]?\s*(.+)", first_line)
    if m:
        return "download", m.group(1).strip()
    m = re.search(r"(?:问|请问|ai)\s*[:：]?\s*(.+)", first_line)
    if m:
        return "ask", m.group(1).strip()
    m = re.search(r"(?:列|目录|ls)\s*[:：]?\s*(.+)", first_line)
    if m:
        return "list", m.group(1).strip()
    if "帮助" in first_line or "help" in first_line.lower():
        return "help", ""
    return None, None


# ---------------- 回复 ----------------
def build_help_text():
    return (
        "【邮件取件机器人 使用说明】\n\n"
        "1. 找文件：写「找 关键词」\n"
        "   例：找 论文\n"
        "2. 找最新：写「找 扩展名」\n"
        "   例：找 docx\n"
        "3. 取文件：先收到清单，再写「发 序号」\n"
        "   例：发 1  或  发 1,3\n"
        "4. 问 AI：写「问 问题」\n"
        "   例：问 帮我改一下这段话\n"
        "5. 列目录：写「列 路径」\n"
        "   例：列 C:/Users/<你的用户名>/Desktop\n"
        "6. 帮助：写「帮助」\n\n"
        "注意：请新写邮件，不要在旧邮件上点「回复」。"
    )


def send_reply(to_addr, subject, text, attachments=None):
    """发送回复邮件，可带附件。"""
    msg = MIMEMultipart()
    msg["From"] = formataddr(("文件取件机器人", config.EMAIL_ADDR))
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain", "utf-8"))

    for path in (attachments or []):
        try:
            fname = os.path.basename(path)
            with open(path, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="octet-stream")
            part.add_header("Content-Disposition", "attachment",
                            filename=("utf-8", "", fname))
            msg.attach(part)
        except Exception as e:
            log(f"附件 {path} 添加失败: {e}")

    with smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT, timeout=60) as server:
        server.login(config.EMAIL_ADDR, config.EMAIL_AUTH_CODE)
        server.sendmail(config.EMAIL_ADDR, [to_addr], msg.as_string())
    log(f"已回复 {to_addr}：{subject}")


LAST_RESULTS = {}  # 发件人邮箱 -> 最近一次「找」得到的文件列表


def _is_ext_keyword(kw):
    """判断关键词是否像是文件扩展名（如 docx/pdf），是则返回小写扩展名。"""
    kw = kw.strip().lstrip(".").lower()
    if re.fullmatch(r"[a-z0-9]{1,10}", kw):
        return kw
    return None


def _safe_mtime(p):
    try:
        return os.path.getmtime(p)
    except Exception:
        return 0


def _fmt_time(ts):
    """把时间戳格式化成 'YYYY-MM-DD HH:MM'。"""
    try:
        import datetime
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "时间未知"


def handle_find(to_addr, keyword):
    """处理「找」指令：先回文件清单（含修改时间），用户确认后再取。
    如果关键词是纯扩展名（如 docx/pdf），自动按「该类型的最新文件」搜索。"""
    log(f"指令：查找 「{keyword}」")
    ext = _is_ext_keyword(keyword)
    if ext:
        found = search_files.search_by_ext(ext)
        title = f"最新 .{ext} 文件"
        hint = f"扩展名为 .{ext} 的文件"
    else:
        found = search_files.search_files(keyword)
        title = f"文件清单：{keyword}"
        hint = f"文件名包含「{keyword}」的文件"
        found.sort(key=_safe_mtime, reverse=True)  # 按修改时间从新到旧

    if not found:
        send_reply(to_addr, "没有找到",
                   f"没有在电脑上找到 {hint}。\n\n"
                   f"可试试「列 C:/Users/<你的用户名>/Desktop」查看目录，"
                   f"或换个关键词/扩展名再试（如：找 docx）。")
        return

    LAST_RESULTS[to_addr] = found  # 记住结果，供「发 序号」使用

    lines = []
    for i, p in enumerate(found, 1):
        try:
            size = os.path.getsize(p) / 1024
        except Exception:
            size = 0
        tag = "  ← 最新" if i == 1 else ""
        lines.append(f"[{i}] {os.path.basename(p)}（{_fmt_time(_safe_mtime(p))}，{size:.0f} KB）{tag}")
        if i >= 15:
            lines.append(f"…… 共 {len(found)} 个")
            break

    text = (f"找到 {len(found)} 个 {hint}，按修改时间从新到旧：\n\n"
            + "\n".join(lines)
            + "\n\n回复「发 序号」获取完整文件，可一次多个（如：发 1,3）。\n"
              "注意：请新写一封邮件发指令，不要在旧邮件上点回复。")
    send_reply(to_addr, title, text)


def handle_download(to_addr, arg):
    """处理「发 序号」指令：把清单里选中的文件作为附件回传。"""
    log(f"指令：下载 「{arg}」")
    results = LAST_RESULTS.get(to_addr, [])
    if not results:
        send_reply(to_addr, "请先搜索",
                   "请先发「找 关键词」获得文件清单，再回复「发 序号」取文件。")
        return

    # 解析序号：支持 1、1,3、2-4
    nums = []
    for part in arg.replace("，", ",").replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            try:
                a, b = part.split("-")
                nums.extend(range(int(a), int(b) + 1))
            except Exception:
                continue
        else:
            try:
                nums.append(int(part))
            except Exception:
                continue

    if not nums:
        send_reply(to_addr, "序号格式不对",
                   "格式示例：发 1  或  发 1,3  或  发 1-2")
        return

    attachments = []
    sent_names = []
    skipped = []
    for n in nums:
        if 1 <= n <= len(results):
            p = results[n - 1]
            try:
                size = os.path.getsize(p)
            except Exception:
                size = 0
            if size <= config.MAX_ATTACH_SIZE:
                attachments.append(p)
                sent_names.append(f"[{n}] {os.path.basename(p)}")
            else:
                skipped.append(f"[{n}] {os.path.basename(p)}（超过附件限制，未发送）")
        else:
            skipped.append(f"[{n}] 序号超出范围（共 {len(results)} 个）")

    # 一次最多发 5 个，避免一封邮件附件太多被邮箱拒收
    MAX_DOWNLOAD = 5
    if len(attachments) > MAX_DOWNLOAD:
        attachments = attachments[:MAX_DOWNLOAD]
        sent_names = sent_names[:MAX_DOWNLOAD]
        skipped.append(f"（一次最多发送 {MAX_DOWNLOAD} 个，其余请分批发）")

    if attachments:
        text = "已发送以下文件：\n\n" + "\n".join(sent_names)
        if skipped:
            text += "\n\n未发送：\n" + "\n".join(skipped)
        send_reply(to_addr, "文件已发送", text, attachments)
    else:
        text = "没有可发送的文件：\n" + "\n".join(skipped)
        send_reply(to_addr, "无法发送", text)


def handle_list(to_addr, path):
    """处理「列」指令：列出目录内容。"""
    log(f"指令：列目录 {path}")
    entries = search_files.list_dir(path)
    if entries is None:
        send_reply(to_addr, "目录不存在",
                   f"路径不存在或不是文件夹：\n{path}\n\n"
                   f"请确认路径写法，例如：列 C:/Users/<你的用户名>/Desktop")
        return
    text = f"目录内容（{path}）：\n\n" + "\n".join(entries)
    send_reply(to_addr, f"目录列表：{path}", text)


CHAT_HISTORY = {}  # 发件人邮箱 -> 最近几轮的问答列表（对话记忆）


def handle_ask(to_addr, question):
    """处理「问」指令：调用 DeepSeek AI 回答（带对话记忆和可选背景设定）并回复邮件。"""
    log(f"指令：提问 「{question[:50]}」")
    if not config.DEEPSEEK_API_KEY or config.DEEPSEEK_API_KEY.startswith("你的"):
        send_reply(to_addr, "AI 未配置",
                   "「问」功能还没配置 API Key。请在 config.py 里填好 DEEPSEEK_API_KEY。")
        return
    try:
        messages = []
        if getattr(config, "AI_SYSTEM_PROMPT", ""):
            messages.append({"role": "system", "content": config.AI_SYSTEM_PROMPT})
        history = CHAT_HISTORY.get(to_addr, [])
        messages.extend(history)
        messages.append({"role": "user", "content": question})

        resp = requests.post(
            f"{config.DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}"},
            json={
                "model": config.DEEPSEEK_MODEL,
                "messages": messages,
                "max_tokens": 2000,
            },
            timeout=120,
        )
        if resp.status_code != 200:
            send_reply(to_addr, "AI 出错了",
                       f"AI 接口返回错误（HTTP {resp.status_code}）：\n{resp.text[:300]}")
            return
        answer = resp.json()["choices"][0]["message"]["content"]

        # 记录本轮问答，按配置保留最近几轮
        turns = max(0, int(getattr(config, "CHAT_HISTORY_TURNS", 0)))
        if turns > 0:
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": answer})
            max_msgs = turns * 2
            if len(history) > max_msgs:
                history = history[-max_msgs:]
            CHAT_HISTORY[to_addr] = history
        else:
            CHAT_HISTORY[to_addr] = []

        send_reply(to_addr, "AI 回答", f"你的问题：{question}\n\n{answer}")
    except Exception as e:
        send_reply(to_addr, "AI 出错了", f"调用 AI 失败：{e}")


# ---------------- 白名单 ----------------
def is_allowed(sender_addr):
    """发件人是否在白名单内。"""
    if not config.ALLOWED_SENDERS:
        return True
    allow_list = [s.strip().lower() for s in config.ALLOWED_SENDERS.split(",") if s.strip()]
    return any(a in sender_addr.lower() for a in allow_list)


# ---------------- 收信主循环 ----------------
PROCESSED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "已处理.txt")


def load_processed():
    if not os.path.isfile(PROCESSED_FILE):
        return set()
    with open(PROCESSED_FILE, encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_processed(processed):
    items = list(processed)[-500:]
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(items))


def mark_seen(server, uid):
    try:
        server.add_flags([uid], [b"\\Seen"])
    except Exception:
        pass


def poll_mailbox(processed):
    """连接邮箱处理新邮件，返回更新后的已处理 msg_id 集合。"""
    try:
        with IMAPClient(config.IMAP_SERVER, port=config.IMAP_PORT, ssl=True, timeout=60) as server:
            server.login(config.EMAIL_ADDR, config.EMAIL_AUTH_CODE)
            # 网易邮箱(163/126)要求发送 ID 命令声明客户端身份，否则报 Unsafe Login
            server.id_({"name": "MailBot", "version": "1.0"})
            server.select_folder("INBOX")
            uids = server.search(["UNSEEN"])
            for uid in uids:
                try:
                    msg_data = server.fetch([uid], ["RFC822"])
                    raw = msg_data[uid][b"RFC822"]
                    msg = email.message_from_bytes(raw)
                    msg_id = msg.get("Message-ID") or f"mail-{uid}"
                    if msg_id in processed:
                        mark_seen(server, uid)
                        continue
                    processed.add(msg_id)
                    save_processed(processed)

                    sender_raw = decode_str(msg.get("From", ""))
                    sender_addr = extract_addr(sender_raw)
                    subject = decode_str(msg.get("Subject", ""))
                    body = get_body(msg)

                    log(f"收到邮件 发件人={sender_addr} 主题={subject}")
                    if not is_allowed(sender_addr):
                        log("  发件人不在白名单，忽略")
                        mark_seen(server, uid)
                        continue

                    cmd, arg = parse_command(subject, body)
                    if cmd is None:
                        send_reply(sender_addr, "看不懂指令", build_help_text())
                    elif cmd == "help":
                        send_reply(sender_addr, "使用说明", build_help_text())
                    elif cmd == "find":
                        handle_find(sender_addr, arg)
                    elif cmd == "download":
                        handle_download(sender_addr, arg)
                    elif cmd == "ask":
                        handle_ask(sender_addr, arg)
                    elif cmd == "list":
                        handle_list(sender_addr, arg)
                    mark_seen(server, uid)
                except Exception as e:
                    log(f"处理邮件出错: {e}")
    except Exception as e:
        log(f"连接邮箱失败: {e}")
    return processed


# ---------------- 启动 ----------------
def main():
    log("=" * 50)
    log("邮件取件机器人已启动")
    log(f"邮箱：{config.EMAIL_ADDR}")
    log(f"白名单：{config.ALLOWED_SENDERS}")
    log(f"轮询间隔：{config.POLL_INTERVAL} 秒")
    log("=" * 50)
    processed = load_processed()
    while True:
        processed = poll_mailbox(processed)
        time.sleep(config.POLL_INTERVAL)


if __name__ == "__main__":
    main()
