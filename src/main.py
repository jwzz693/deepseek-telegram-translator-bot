"""AI 全自动翻译 Telegram 机器人 — 主入口 v2.1"""

import warnings
warnings.filterwarnings("ignore", message="Core Pydantic V1")

import asyncio
import logging
import signal
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from src.config import Config, VERSION
from src.store import flush_all
from src.handlers import (
    cmd_start, cmd_help, cmd_settings, cmd_lang, cmd_set_lang,
    cmd_set_provider, cmd_set_model, cmd_auto_on, cmd_auto_off,
    cmd_status, cmd_translate, cmd_providers, cmd_reset,
    cmd_clear_stats, cmd_id, cmd_ping,
    cmd_authorize, cmd_unauthorize, cmd_authorized,
    callback_handler, handle_message, setup_commands, error_handler,
)

# ═══════════════════════════════════════════
#  日志配置
# ═══════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
# 降低 httpx / urllib3 日志级别
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

_shutdown_event = asyncio.Event()


def _handle_signal(sig, _frame):
    """收到终止信号 → 优雅关停"""
    logger.info("🛑 收到信号 %s，正在优雅关停...", signal.Signals(sig).name)
    flush_all()
    _shutdown_event.set()


def main():
    """启动机器人"""
    if not Config.TELEGRAM_BOT_TOKEN:
        logger.error("❌ 未设置 TELEGRAM_BOT_TOKEN")
        sys.exit(1)

    available = Config.available_providers()
    if not available:
        logger.error("❌ 未配置任何 AI API Key")
        sys.exit(1)

    # ── 启动信息 ──
    logger.info("╔══════════════════════════════════════╗")
    logger.info("║  🌐 AI Translator Bot v%s          ║", VERSION)
    logger.info("╚══════════════════════════════════════╝")
    logger.info("  🤖 引擎: %s", ", ".join(available))
    logger.info("  🎯 默认: %s → %s", Config.DEFAULT_PROVIDER, Config.DEFAULT_TARGET_LANG)
    logger.info("  👑 管理: %d 位授权用户", len(Config.ADMIN_USER_IDS))
    logger.info("  📝 文本上限: %d 字符 | 频率限制: %d/分钟", Config.MAX_TEXT_LENGTH, Config.RATE_LIMIT_PER_MIN)

    # ── 信号处理（优雅关停）──
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except (OSError, ValueError):
            pass  # Windows 下 SIGTERM 可能不可用

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
        "authorize": cmd_authorize,
        "unauthorize": cmd_unauthorize,
        "authorized": cmd_authorized,
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
    logger.info("✅ 机器人已启动，等待消息...")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app.run_polling(drop_pending_updates=True)
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 机器人关停中...")
    finally:
        flush_all()
        logger.info("👋 数据已保存，再见！")


if __name__ == "__main__":
    main()
