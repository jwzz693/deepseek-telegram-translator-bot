# 🌐 AI 翻译机器人 — Debian 服务器部署指南

## ⚡ 一键部署

### 1. 上传代码到服务器

```bash
# 方式一: scp 上传（Windows → 服务器）
scp -r deepseek-telegram-translator-bot/ root@你的IP:/root/

# 方式二: git clone（如果已推送到仓库）
git clone https://github.com/你的用户名/deepseek-telegram-translator-bot.git
cd deepseek-telegram-translator-bot
```

### 2. 执行一键部署

```bash
cd /root/deepseek-telegram-translator-bot
chmod +x deploy.sh
sudo bash deploy.sh
```

脚本会自动完成：
- ✅ 安装系统依赖 (Python3, pip, venv...)
- ✅ 创建专用运行用户 `botuser`
- ✅ 部署代码到 `/opt/telegram-translator-bot/`
- ✅ 交互式配置 `.env` (Token, API Keys, 管理员ID)
- ✅ 创建 Python 虚拟环境 + 安装依赖
- ✅ 配置 systemd 服务 (开机自启、崩溃重启)
- ✅ 安装 `bot` 快捷管理命令

---

## 🛠 日常管理

部署完成后，使用 `bot` 命令管理：

```bash
bot status       # 查看状态
bot log          # 实时日志 (Ctrl+C 退出)
bot restart      # 重启
bot stop         # 停止
bot start        # 启动
bot config       # 编辑 .env 配置
bot health       # 健康检查
bot backup       # 备份数据
bot restore FILE # 恢复备份
bot update       # 更新代码
bot uninstall    # 完全卸载
```

或使用 systemctl：

```bash
systemctl status telegram-translator-bot
systemctl restart telegram-translator-bot
journalctl -u telegram-translator-bot -f
```

---

## 📁 部署后目录结构

```
/opt/telegram-translator-bot/
├── .env                      # 配置文件 (权限600)
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── config.py             # 全局配置
│   ├── main.py               # 主入口
│   ├── store.py              # 数据持久化
│   ├── translator.py         # 翻译核心
│   ├── handlers.py           # 命令处理器
│   └── providers/
│       ├── __init__.py       # 工厂
│       ├── base.py           # 基类
│       ├── openai_compatible.py  # DeepSeek/OpenAI/Groq/Mistral
│       ├── claude.py         # Claude
│       └── gemini.py         # Gemini
├── data/
│   ├── settings.json         # 聊天设置
│   └── stats.json            # 翻译统计
└── venv/                     # Python虚拟环境
```

---

## ⚙️ 配置说明

`.env` 文件内容：

```env
# Telegram
TELEGRAM_BOT_TOKEN=你的Bot_Token

# AI API Keys (至少填一个)
DEEPSEEK_API_KEY=你的Key
OPENAI_API_KEY=
CLAUDE_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
MISTRAL_API_KEY=

# 默认设置
DEFAULT_PROVIDER=deepseek
DEFAULT_TARGET_LANG=中文

# 管理员 (多个用逗号分隔)
ADMIN_USER_IDS=你的TelegramID
```

修改配置后重启：
```bash
bot config    # 编辑后自动提示重启
# 或
nano /opt/telegram-translator-bot/.env
systemctl restart telegram-translator-bot
```

---

## 🔒 安全特性

- **专用用户**: 以 `botuser` 身份运行，非 root
- **文件隔离**: systemd `ProtectSystem=strict`
- **权限控制**: `.env` 仅 owner 可读 (chmod 600)
- **自动重启**: 崩溃后 10 秒自动重启
- **频率限制**: 5 分钟内最多重启 5 次
- **管理员模式**: 所有功能仅管理员可用

---

## 🔧 故障排查

```bash
# 查看详细日志
journalctl -u telegram-translator-bot -n 50 --no-pager

# 手动测试运行
cd /opt/telegram-translator-bot
sudo -u botuser venv/bin/python src/main.py

# 检查依赖
venv/bin/pip list

# 健康检查
bot health
```

---

## 📋 系统要求

| 项目 | 要求 |
|------|------|
| 系统 | Debian 10+ / Ubuntu 20.04+ |
| Python | ≥ 3.10 |
| 内存 | ≥ 256MB |
| 磁盘 | ≥ 200MB |
| 网络 | 可访问 Telegram API + AI API |
