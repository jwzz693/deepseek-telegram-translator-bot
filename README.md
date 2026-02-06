# 🌐 AI 全自动翻译 Telegram 机器人 v2.1

支持 **6 大 AI 引擎** 的 Telegram 全自动翻译机器人，自动检测语言、智能互翻、多引擎降级。

## ✨ 支持的 AI 引擎

| 引擎 | 默认模型 | API 格式 |
|------|---------|---------|
| 🧠 **DeepSeek** | deepseek-chat | OpenAI 兼容 |
| 💚 **OpenAI** | gpt-4o-mini | OpenAI |
| 🟠 **Claude** | claude-sonnet-4-20250514 | Anthropic |
| 🔵 **Gemini** | gemini-2.0-flash | Google GenAI |
| ⚡ **Groq** | llama-3.3-70b-versatile | OpenAI 兼容 |
| 🌬️ **Mistral** | mistral-small-latest | OpenAI 兼容 |

## 🚀 功能特性

- 🔄 **全自动翻译** — 群组消息自动翻译，无需手动触发
- 🌍 **自动语言检测** — AI 自动识别源语言
- 🤖 **多引擎支持** — 6 大 AI 引擎随时切换，失败自动降级
- 🔁 **智能互翻** — 同语言自动切换目标语言（中→英/英→中）
- ⚙️ **每群独立配置** — 每个群组/私聊可单独设置语言和引擎
- 💾 **持久化存储** — 设置自动保存，原子写入防损坏
- 🧠 **自定义模型** — 可指定使用特定模型
- ⏱ **超时控制** — 30 秒翻译超时，自动降级到其他引擎
- 📊 **延迟统计** — 记录每个引擎的平均延迟
- 🔐 **管理员锁** — 所有功能仅授权用户可用
- 👥 **批量授权** — 支持 `/authorize ID1 ID2 ID3` 批量添加
- 📋 **一键复制** — 译文下方有复制按钮
- ⚙️ **设置面板** — `/settings` 交互式按钮面板

## 📋 命令列表（19 个）

| 命令 | 说明 |
|------|------|
| `/start` | 🚀 启动 + 显示当前配置 |
| `/help` | 📖 完整帮助信息 |
| `/settings` | ⚙️ 交互式设置面板（推荐）|
| `/translate 文本` | 📝 手动翻译（支持回复消息）|
| `/lang` | 🌍 快捷语言切换（15 种）|
| `/set_lang 语言` | 🌍 自定义目标语言 |
| `/set_provider` | 🤖 切换 AI 引擎 |
| `/set_model 模型` | 🧠 自定义模型 |
| `/providers` | 📋 查看所有引擎状态 |
| `/auto_on` | 🟢 开启自动翻译 |
| `/auto_off` | 🔴 关闭自动翻译 |
| `/status` | 📊 设置与统计 |
| `/reset` | 🔄 恢复默认设置 |
| `/clear_stats` | 🗑 清除统计数据 |
| `/id` | 🆔 查看用户/聊天 ID |
| `/ping` | 🏓 测试 Bot + AI 延迟 |
| `/authorize ID` | 🔐 授权用户（支持批量）|
| `/unauthorize ID` | 🔐 取消授权 |
| `/authorized` | 📋 查看授权列表 |

## 🛠️ 安装部署

### 方式一：一键部署（推荐，零交互）

```bash
curl -sL https://raw.githubusercontent.com/jwzz693/deepseek-telegram-translator-bot/main/install.sh | sudo bash
```

### 方式二：本地部署

```bash
git clone https://github.com/jwzz693/deepseek-telegram-translator-bot.git
cd deepseek-telegram-translator-bot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填写 Token 和 API Key
python src/main.py
```

### 方式三：服务器部署

```bash
cd deepseek-telegram-translator-bot
sudo bash deploy.sh
```

## ⚙️ 配置说明

`.env` 文件：

```env
TELEGRAM_BOT_TOKEN=你的Bot_Token
DEEPSEEK_API_KEY=你的Key
OPENAI_API_KEY=
CLAUDE_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
MISTRAL_API_KEY=
DEFAULT_PROVIDER=deepseek
DEFAULT_TARGET_LANG=中文
MAX_TEXT_LENGTH=5000
RATE_LIMIT_PER_MIN=30
ADMIN_USER_IDS=你的TelegramID
```

## 📁 项目结构

```
deepseek-telegram-translator-bot/
├── .env.example          # 环境变量模板
├── .gitignore
├── README.md
├── DEPLOY.md             # 部署文档
├── requirements.txt
├── deploy.sh             # 本地服务器部署脚本
├── install.sh            # GitHub 一键部署脚本
├── bot.sh                # 服务管理脚本（14 命令）
├── data/
│   ├── settings.json     # 聊天设置（自动备份）
│   └── stats.json        # 翻译统计
└── src/
    ├── config.py          # 全局配置 + 版本 + 运行时间
    ├── main.py            # 主入口 + 信号处理
    ├── store.py           # 持久化（内存缓存 + 原子写入）
    ├── translator.py      # 翻译核心（超时 + 降级 + 延迟统计）
    ├── handlers.py        # 19 命令处理器 + 设置面板
    └── providers/
        ├── __init__.py    # 工厂 + 引擎显示名
        ├── base.py        # 基类 + 翻译提示词
        ├── openai_compatible.py  # DeepSeek/OpenAI/Groq/Mistral
        ├── claude.py      # Claude
        └── gemini.py      # Gemini
```

## 🔒 安全特性

- **管理员模式** — 所有功能仅授权用户可用
- **主管理员** — 不可被移除，独享授权管理权限
- **专用用户** — 服务器以 `botuser` 身份运行
- **文件保护** — `.env` 权限 600，systemd 安全加固
- **频率限制** — 可配置每分钟请求上限
- **优雅关停** — SIGINT/SIGTERM 信号处理，数据不丢失

## 📄 License

MIT
