"""AI 全自动翻译 Telegram 机器人 — 主入口"""

import warnings
warnings.filterwarnings("ignore", message="Core Pydantic V1")

import asyncio
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from src.config import Config
from src.handlers import (
    cmd_start, cmd_help, cmd_settings, cmd_lang, cmd_set_lang,
    cmd_set_provider, cmd_set_model, cmd_auto_on, cmd_auto_off,
    cmd_status, cmd_translate, cmd_providers, cmd_reset,
    cmd_clear_stats, cmd_id, cmd_ping, callback_handler,
    handle_message, setup_commands, error_handler,
)

# ═══════════════════════════════════════════
#  日志配置
# ═══════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
# 降低 httpx 日志级别
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main():
    """启动机器人"""
    if not Config.TELEGRAM_BOT_TOKEN:
        logger.error("❌ 未设置 TELEGRAM_BOT_TOKEN")
        sys.exit(1)

    available = Config.available_providers()
    if not available:
        logger.error("❌ 未配置任何 AI API Key")
        sys.exit(1)

    logger.info("🚀 正在启动翻译机器人...")
    logger.info("   可用引擎: %s", ", ".join(available))
    logger.info("   默认引擎: %s", Config.DEFAULT_PROVIDER)
    logger.info("   默认语言: %s", Config.DEFAULT_TARGET_LANG)

    app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # 命令处理器
    commands = {
        "start": cmd_start,
        "help": cmd_help,
        "settings": cmd_settings,
        "lang": cmd_lang,
        "set_lang": cmd_set_lang,
        "set_provider": cmd_set_provider,
        "set_model": cmd_set_model,
        "auto_on": cmd_auto_on,
        "auto_off": cmd_auto_off,
        "status": cmd_status,
        "translate": cmd_translate,
        "providers": cmd_providers,
        "reset": cmd_reset,
        "clear_stats": cmd_clear_stats,
        "id": cmd_id,
        "ping": cmd_ping,
    }
    for name, handler in commands.items():
        app.add_handler(CommandHandler(name, handler))

    # 回调 + 消息 + 错误
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION) & ~filters.COMMAND,
        handle_message,
    ))
    app.add_error_handler(error_handler)

    # 注册命令菜单
    app.post_init = setup_commands

    # 启动（兼容 Python 3.14+）
    logger.info("✅ 机器人已启动")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
