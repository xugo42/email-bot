# -*- coding: utf-8 -*-
"""
文件搜索模块
优先使用 Everything（es.exe）秒搜全盘；若未安装 Everything，则退回 Python 慢速遍历。
"""
import os
import subprocess
import config


def find_es_exe():
    """定位 Everything 的命令行工具 es.exe，找不到返回 None。"""
    if config.ES_EXE and os.path.isfile(config.ES_EXE):
        return config.ES_EXE
    # 项目自带的 es.exe（发布包 tools/ES/es.exe，装了 Everything 主程序即可用）
    bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "ES", "es.exe")
    if os.path.isfile(bundled):
        return bundled
    for candidate in [
        r"C:\Program Files\Everything\es.exe",
        r"C:\Program Files (x86)\Everything\es.exe",
    ]:
        if os.path.isfile(candidate):
            return candidate
    return None


EVERYTHING_EXE = r"C:\Program Files\Everything\Everything.exe"


def _ensure_everything_running():
    """确保 Everything 主程序在运行（es.exe 依赖它的索引）。"""
    import time
    try:
        out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=10).stdout
        if "Everything.exe" in out:
            return True
    except Exception:
        pass
    if os.path.isfile(EVERYTHING_EXE):
        try:
            subprocess.Popen([EVERYTHING_EXE])
            time.sleep(4)
            return True
        except Exception:
            return False
    return False


def search_with_everything(keyword, limit=50):
    """用 Everything 搜索文件名包含 keyword 的文件。
    若 Everything 未运行导致 es.exe 报错，会自动启动 Everything 并重试一次。
    """
    es = find_es_exe()
    if not es:
        return None  # 表示未安装 Everything
    try:
        result = subprocess.run(
            [es, "-n", str(limit), "-s", keyword],
            capture_output=True, text=True, timeout=30,
        )
        # es.exe 报错 = Everything 主程序没在运行，自动启动它并重试一次
        if result.stderr.strip():
            _ensure_everything_running()
            result = subprocess.run(
                [es, "-n", str(limit), "-s", keyword],
                capture_output=True, text=True, timeout=30,
            )
        paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        # 排除 .lnk 快捷方式、.asd 自动恢复文件，用户要的是实际文件
        return [p for p in paths if os.path.isfile(p) and not p.lower().endswith((".lnk", ".asd"))]
    except Exception:
        return None


def search_with_walk(keyword, dirs, limit=50):
    """慢速遍历搜索文件名包含 keyword 的文件。"""
    found = []
    for base in dirs:
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for name in files:
                # 排除 .lnk 快捷方式、.asd 自动恢复文件，用户要的是实际文件
                if keyword.lower() in name.lower() and not name.lower().endswith((".lnk", ".asd")):
                    found.append(os.path.join(root, name))
                    if len(found) >= limit:
                        return found
    return found


def default_search_dirs():
    """没有配置目录时，扫描所有本地磁盘根目录。"""
    import string
    dirs = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if os.path.exists(root):
            dirs.append(root)
    return dirs


def search_files(keyword, limit=50):
    """统一入口：先 Everything 秒搜，失败则慢速遍历。"""
    found = search_with_everything(keyword, limit)
    if found is not None:
        return found
    dirs = config.SEARCH_DIRS if config.SEARCH_DIRS else default_search_dirs()
    return search_with_walk(keyword, dirs, limit)


def _mtime(p):
    try:
        return os.path.getmtime(p)
    except Exception:
        return 0


def search_by_ext(ext, limit=200):
    """按扩展名搜索文件，按修改时间从新到旧排序返回。ext 不带点，如 'docx'。"""
    ext = ext.lstrip(".").lower()
    found = []
    es = find_es_exe()
    if es:
        try:
            result = subprocess.run(
                [es, "-n", str(limit), "-s", f"ext:{ext}"],
                capture_output=True, text=True, timeout=30,
            )
            # es.exe 报错 = Everything 没在运行，自动启动并重试一次
            if result.stderr.strip():
                _ensure_everything_running()
                result = subprocess.run(
                    [es, "-n", str(limit), "-s", f"ext:{ext}"],
                    capture_output=True, text=True, timeout=30,
                )
            found = [p.strip() for p in result.stdout.splitlines() if p.strip()]
            found = [p for p in found if os.path.isfile(p)
                     and not p.lower().endswith((".lnk", ".asd"))]
        except Exception:
            found = []
    if not found:
        # 退回慢速遍历常见目录
        dirs = config.SEARCH_DIRS if config.SEARCH_DIRS else default_search_dirs()
        for base in dirs:
            if not os.path.isdir(base):
                continue
            for root, _d, files in os.walk(base):
                for name in files:
                    if name.lower().endswith("." + ext) and not name.lower().endswith((".lnk", ".asd")):
                        found.append(os.path.join(root, name))
                        if len(found) >= limit:
                            break
                if len(found) >= limit:
                    break
    # 按修改时间从新到旧排序
    found.sort(key=_mtime, reverse=True)
    return found


def list_dir(path):
    """列出目录下的文件和子目录（只列一层）。返回字符串列表，目录不存在返回 None。"""
    path = os.path.normpath(path)
    if not os.path.isdir(path):
        return None
    entries = []
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        kind = "目录" if os.path.isdir(full) else "文件"
        size = ""
        if os.path.isfile(full):
            try:
                size = f" ({os.path.getsize(full) / 1024:.0f} KB)"
            except Exception:
                pass
        entries.append(f"[{kind}] {name}{size}")
    return entries
