# 🌐 AI 全自动翻译 Telegram 机器人

支持 **6 大 AI 引擎** 的 Telegram 全自动翻译机器人，可自动检测语言并翻译。

## ✨ 支持的 AI 引擎

| 引擎 | 默认模型 | API 格式 |
|------|---------|---------|
| **DeepSeek** | deepseek-chat | OpenAI 兼容 |
| **OpenAI** | gpt-4o-mini | OpenAI |
| **Claude** | claude-sonnet-4-20250514 | Anthropic |
| **Gemini** | gemini-2.0-flash | Google GenAI |
| **Groq** | llama-3.3-70b-versatile | OpenAI 兼容 |
| **Mistral** | mistral-small-latest | OpenAI 兼容 |

## 🚀 功能特性

- 🔄 **全自动翻译**：群组消息自动翻译，无需手动触发
- 🌍 **自动语言检测**：自动识别源语言
- 🤖 **多 AI 引擎**：支持 6 大 AI 引擎，随时切换
- ⚙️ **每群独立配置**：每个群组/私聊可单独设置语言和引擎
- 💾 **持久化存储**：设置自动保存，重启不丢失
- 🧠 **自定义模型**：可指定使用特定模型

## 📋 命令列表

| 命令 | 说明 |
|------|------|
| `/start` | 显示帮助信息 |
| `/set_lang 语言` | 设置目标翻译语言（如：中文、English、日本語） |
| `/set_provider 名称` | 切换 AI 引擎（如：deepseek、openai、claude） |
| `/set_model 模型名` | 设置自定义模型 |
| `/auto_on` | 开启自动翻译（群组默认关闭） |
| `/auto_off` | 关闭自动翻译 |
| `/status` | 查看当前设置 |
| `/translate 文本` | 手动翻译指定文本 |
| `/providers` | 查看所有支持的 AI 引擎及状态 |

## 🛠️ 安装部署

### 1. 克隆项目

```bash
git clone <repo-url>
cd deepseek-telegram-translator-bot
```

### 2. 创建虚拟环境

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写：
- `TELEGRAM_BOT_TOKEN` — 从 [@BotFather](https://t.me/BotFather) 获取
- 至少一个 AI API Key

### 5. 启动机器人

```bash
python src/main.py
```

## 📁 项目结构

```
deepseek-telegram-translator-bot/
├── .env.example          # 环境变量模板
├── .gitignore
├── README.md
├── requirements.txt
├── data/
│   └── settings.json     # 持久化设置
└── src/
    ├── __init__.py
    ├── main.py            # 主入口
    ├── config.py          # 全局配置
    ├── store.py           # 持久化存储
    ├── translator.py      # 翻译核心逻辑
    ├── handlers.py        # Telegram 消息处理
    └── providers/         # AI 提供商
        ├── __init__.py    # 工厂函数
        ├── base.py        # 基类
        ├── openai_compatible.py  # OpenAI/DeepSeek/Groq/Mistral
        ├── claude.py      # Claude
        └── gemini.py      # Gemini
```

## 💡 使用示例

**私聊翻译**：直接发送任何语言的文本，机器人自动翻译成目标语言。

**群组翻译**：
1. 将机器人加入群组
2. 发送 `/auto_on` 开启自动翻译
3. 所有群组消息会自动被翻译并以回复形式展示

**切换引擎**：
```
/set_provider claude
/set_lang English
```

## 📄 License

MIT
