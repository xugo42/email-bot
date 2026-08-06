# -*- coding: utf-8 -*-
"""
AI 配置测试工具
验证 config.py 里的 DeepSeek API Key 是否配置正确、能否正常调用。
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import requests
import config

print("=" * 50)
print("开始测试 AI 配置……")
print(f"模型：{config.DEEPSEEK_MODEL}")
print(f"API 地址：{config.DEEPSEEK_BASE_URL}")
key_display = config.DEEPSEEK_API_KEY[:8] + "..." if config.DEEPSEEK_API_KEY and not config.DEEPSEEK_API_KEY.startswith("你的") else "未配置"
print(f"API Key：{key_display}")
print("=" * 50)

if not config.DEEPSEEK_API_KEY or config.DEEPSEEK_API_KEY.startswith("你的"):
    print("\n[FAIL] API Key 未配置")
    print("  请在 config.py 的 DEEPSEEK_API_KEY 填你的 DeepSeek API Key（DeepSeek 官网获取）")
    input("按回车退出……")
    sys.exit(1)

print("\n正在调用 DeepSeek API 测试……")
try:
    resp = requests.post(
        f"{config.DEEPSEEK_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}"},
        json={
            "model": config.DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": "只回复两个字：正常"}],
            "max_tokens": 100,
        },
        timeout=60,
    )
    if resp.status_code == 200:
        data = resp.json()
        answer = data["choices"][0]["message"]["content"]
        print(f"  [OK] AI 调用成功")
        print(f"  模型返回：{answer}")
        print(f"  实际模型：{data.get('model', config.DEEPSEEK_MODEL)}")
    else:
        print(f"  [FAIL] AI 接口返回错误（HTTP {resp.status_code}）")
        print(resp.text[:300])
except Exception as e:
    print(f"  [FAIL] 调用 AI 失败：{e}")

print("\n" + "=" * 50)
print("测试完成。")
print("=" * 50)
input("按回车退出……")
