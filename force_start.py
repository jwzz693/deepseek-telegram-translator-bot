"""强制启动脚本 — 通过连续设置/删除 webhook 抢占 polling 通道"""

import urllib.request
import urllib.parse
import time
import subprocess
import sys

TOKEN = "8457225198:AAHbTqS_xaCDSiItryj_frdf_4sbNhTfBjs"
BASE = f"https://api.telegram.org/bot{TOKEN}"

def api_call(method, params=None):
    """调用 Telegram API"""
    try:
        if params:
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(f"{BASE}/{method}", data=data)
        else:
            req = f"{BASE}/{method}"
        r = urllib.request.urlopen(req, timeout=10)
        return r.read().decode()
    except Exception as e:
        return str(e)

print("🔨 步骤1: 连续10次 setWebhook 中断服务器 polling...")
for i in range(10):
    result = api_call("setWebhook", {"url": "https://example.com/kill"})
    time.sleep(0.5)
    result = api_call("deleteWebhook", {"drop_pending_updates": "true"})
    time.sleep(0.5)

print("🔨 步骤2: 设置 webhook 锁住 polling 通道...")
api_call("setWebhook", {"url": "https://example.com/block"})

print("⏳ 等待15秒让服务器 systemd 放弃重试...")
time.sleep(15)

print("🔨 步骤3: 删除 webhook 并立即启动 bot...")
api_call("deleteWebhook", {"drop_pending_updates": "true"})

# 验证 polling 可用
try:
    r = urllib.request.urlopen(f"{BASE}/getUpdates?timeout=1&offset=-1", timeout=5)
    resp = r.read().decode()
    if '"ok":true' in resp:
        print("✅ Polling 通道已释放!")
    else:
        print(f"⚠️ 响应: {resp[:200]}")
except Exception as e:
    print(f"❌ getUpdates 失败: {e}")
    print("服务器可能还在 polling，请 SSH 到服务器执行:")
    print("  sudo systemctl stop telegram-translator-bot")
    sys.exit(1)

print("🚀 启动机器人...")
# 直接 exec 替换当前进程
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.execv(sys.executable, [sys.executable, "src/main.py"])
