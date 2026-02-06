"""Telegram 消息处理器 — 全功能优化版"""

import re
import logging
import time
import asyncio
from collections import defaultdict
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from telegram.error import BadRequest, Forbidden, TimedOut, NetworkError, RetryAfter

from src.config import Config
from src.store import (
    get_chat_config, set_chat_config, record_translation,
    get_stats, get_global_stats, reset_chat_config, clear_chat_stats,
)
from src.translator import translate_text, get_provider, _provider_cache
from src.providers import PROVIDER_MODELS

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════

QUICK_LANGS = [
    ("🇨🇳 中文", "中文"),
    ("🇺🇸 English", "English"),
    ("🇯🇵 日本語", "日本語"),
    ("🇰🇷 한국어", "한국어"),
    ("🇷🇺 Русский", "Русский"),
    ("🇫🇷 Français", "Français"),
    ("🇪🇸 Español", "Español"),
    ("🇩🇪 Deutsch", "Deutsch"),
    ("🇵🇹 Português", "Português"),
    ("🇸🇦 العربية", "العربية"),
    ("🇹🇭 ไทย", "ไทย"),
    ("🇻🇳 Tiếng Việt", "Tiếng Việt"),
    ("🇮🇹 Italiano", "Italiano"),
    ("🇮🇩 Bahasa", "Bahasa Indonesia"),
    ("🇮🇳 हिन्दी", "हिन्दी"),
]

RATE_LIMIT_PER_MIN = 30
_rate_limiter: dict[int, list[float]] = defaultdict(list)

_translate_cache: dict[str, dict] = {}
CACHE_MAX_SIZE = 500


# ═══════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════

def _is_admin(user_id: int) -> bool:
    """检查用户是否为管理员"""
    return user_id in Config.ADMIN_USER_IDS


async def _admin_only(update: Update) -> bool:
    """管理员权限拦截，非管理员返回 True（已拦截）"""
    if _is_admin(update.effective_user.id):
        return False
    await _safe_reply(update.message, "🔒 仅管理员可操作")
    return True


def _escape_md(text: str) -> str:
    for ch in ('_', '*', '`', '[', ']', '~'):
        text = text.replace(ch, f'\\{ch}')
    return text


def _truncate(text: str, max_len: int = 3000) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n\n⚠️ _(文本过长，已截断)_"


def _check_rate_limit(user_id: int) -> bool:
    now = time.time()
    _rate_limiter[user_id] = [t for t in _rate_limiter[user_id] if now - t < 60]
    if len(_rate_limiter[user_id]) >= RATE_LIMIT_PER_MIN:
        return False
    _rate_limiter[user_id].append(now)
    # 定期清理不活跃用户，防止内存泄漏
    if len(_rate_limiter) > 1000:
        stale = [uid for uid, ts in _rate_limiter.items() if not ts or now - ts[-1] > 300]
        for uid in stale:
            del _rate_limiter[uid]
    return True


def _cache_key(text: str, target_lang: str, provider: str) -> str:
    return f"{provider}:{target_lang}:{hash(text)}"


def _get_cached(text: str, target_lang: str, provider: str) -> dict | None:
    return _translate_cache.get(_cache_key(text, target_lang, provider))


def _set_cache(text: str, target_lang: str, provider: str, result: dict):
    if len(_translate_cache) >= CACHE_MAX_SIZE:
        keys = list(_translate_cache.keys())
        for k in keys[:CACHE_MAX_SIZE // 2]:
            del _translate_cache[k]
    _translate_cache[_cache_key(text, target_lang, provider)] = result


async def _safe_reply(message, text: str, **kwargs):
    try:
        return await message.reply_text(text, **kwargs)
    except BadRequest as e:
        if "parse" in str(e).lower() or "can't" in str(e).lower():
            kwargs.pop("parse_mode", None)
            clean = text.replace("\\", "")
            try:
                return await message.reply_text(clean, **kwargs)
            except Exception:
                kwargs.pop("reply_markup", None)
                return await message.reply_text(clean[:4000])
        raise
    except RetryAfter as e:
        await asyncio.sleep(e.retry_after)
        return await message.reply_text(text, **kwargs)
    except (TimedOut, NetworkError) as e:
        logger.error(f"网络异常: {e}")
        return None


# ═══════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    available = Config.available_providers()
    providers_text = ", ".join(available) if available else "（未配置）"
    chat_id = update.effective_chat.id
    cfg = get_chat_config(chat_id)
    auto = cfg.get("auto_translate", update.effective_chat.type == "private")
    await _safe_reply(
        update.message,
        "🌐 *AI 全自动翻译机器人*\n\n"
        "加入群组自动翻译，私聊直接发文本翻译。\n\n"
        f"🤖 引擎: `{cfg.get('provider', Config.DEFAULT_PROVIDER)}`\n"
        f"🌍 语言: *{cfg.get('target_lang', Config.DEFAULT_TARGET_LANG)}*\n"
        f"🔄 自动: {'🟢 开启' if auto else '🔴 关闭'}\n"
        f"✅ 可用: {providers_text}\n\n"
        "📋 /help 查看完整命令",
        parse_mode="Markdown",
    )


# ═══════════════════════════════════════════
#  /help
# ═══════════════════════════════════════════

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    await _safe_reply(
        update.message,
        "📖 *完整命令列表*\n\n"
        "*🌍 翻译:*\n"
        "/translate `文本` — 手动翻译\n"
        "  ↳ 回复消息 + /translate\n"
        "/lang — ⚡ 快捷切换语言\n"
        "/set\\_lang `语言` — 自定义语言\n\n"
        "*🤖 AI 引擎:*\n"
        "/set\\_provider — 切换引擎\n"
        "/set\\_model `模型` — 自定义模型\n"
        "/providers — 查看所有引擎\n\n"
        "*⚙️ 设置:*\n"
        "/settings — ⚙️ 设置面板 (推荐)\n"
        "/auto\\_on — 开启自动翻译\n"
        "/auto\\_off — 关闭自动翻译\n"
        "/status — 设置和统计\n"
        "/reset — 恢复默认\n"
        "/clear\\_stats — 清除统计\n\n"
        "*🛠 工具:*\n"
        "/id — 查看 ID\n"
        "/ping — 测试延迟\n\n"
        "*💡 技巧:*\n"
        "• 私聊默认自动翻译\n"
        "• 群组需 /auto\\_on 开启\n"
        "• 同语言自动互翻\n"
        "• 译文下方有复制按钮",
        parse_mode="Markdown",
    )


# ═══════════════════════════════════════════
#  /lang
# ═══════════════════════════════════════════

async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    cfg = get_chat_config(update.effective_chat.id)
    current = cfg.get("target_lang", Config.DEFAULT_TARGET_LANG)
    buttons, row = [], []
    for label, lang_code in QUICK_LANGS:
        display = f"✓ {label}" if lang_code == current else label
        row.append(InlineKeyboardButton(display, callback_data=f"lang:{lang_code}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    await _safe_reply(
        update.message,
        f"🌍 *选择目标语言*\n当前: *{current}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ═══════════════════════════════════════════
#  /settings 设置面板
# ═══════════════════════════════════════════

def _build_settings_panel(chat_id: int, chat_type: str = "private") -> tuple[str, InlineKeyboardMarkup]:
    """构建设置面板的文本和按钮"""
    cfg = get_chat_config(chat_id)
    provider = cfg.get("provider", Config.DEFAULT_PROVIDER)
    target = cfg.get("target_lang", Config.DEFAULT_TARGET_LANG)
    model = cfg.get("model", PROVIDER_MODELS.get(provider, "默认"))
    auto = cfg.get("auto_translate", chat_type == "private")
    stats = get_stats(chat_id)

    text = (
        "⚙️ *设置面板*\n\n"
        f"🤖 引擎: `{provider}`\n"
        f"🧠 模型: `{model}`\n"
        f"🌍 语言: *{target}*\n"
        f"🔄 自动翻译: {'🟢 开启' if auto else '🔴 关闭'}\n\n"
        f"📊 已翻译: {stats['total']} 次 | {stats['chars']:,} 字符"
    )

    auto_btn_text = "🔴 关闭自动翻译" if auto else "🟢 开启自动翻译"
    auto_btn_data = "settings:auto_off" if auto else "settings:auto_on"

    buttons = [
        [InlineKeyboardButton(f"🌍 切换语言 ({target})", callback_data="settings:lang")],
        [InlineKeyboardButton(f"🤖 切换引擎 ({provider})", callback_data="settings:provider")],
        [InlineKeyboardButton(auto_btn_text, callback_data=auto_btn_data)],
        [
            InlineKeyboardButton("🔄 恢复默认", callback_data="settings:reset"),
            InlineKeyboardButton("🗑 清除统计", callback_data="settings:clear_stats"),
        ],
        [InlineKeyboardButton("📊 详细统计", callback_data="settings:status")],
    ]

    return text, InlineKeyboardMarkup(buttons)


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示交互式设置面板"""
    if await _admin_only(update):
        return
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    text, markup = _build_settings_panel(chat_id, chat_type)
    await _safe_reply(update.message, text, parse_mode="Markdown", reply_markup=markup)


# ═══════════════════════════════════════════
#  回调处理
# ═══════════════════════════════════════════

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type

    # 所有设置操作需管理员权限
    if not _is_admin(query.from_user.id):
        await query.answer("🔒 仅管理员可操作", show_alert=True)
        return

    try:
        if data.startswith("lang:"):
            lang = data[5:]
            set_chat_config(chat_id, {"target_lang": lang})
            await query.answer(f"✅ 已切换到 {lang}")
            text, markup = _build_settings_panel(chat_id, chat_type)
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

        elif data.startswith("provider:"):
            provider = data[9:]
            set_chat_config(chat_id, {"provider": provider})
            await query.answer(f"✅ 已切换到 {provider}")
            text, markup = _build_settings_panel(chat_id, chat_type)
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

        elif data == "settings:lang":
            # 显示语言选择面板
            cfg = get_chat_config(chat_id)
            current = cfg.get("target_lang", Config.DEFAULT_TARGET_LANG)
            buttons, row = [], []
            for label, lang_code in QUICK_LANGS:
                display = f"✓ {label}" if lang_code == current else label
                row.append(InlineKeyboardButton(display, callback_data=f"lang:{lang_code}"))
                if len(row) == 3:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([InlineKeyboardButton("⬅️ 返回设置", callback_data="settings:back")])
            await query.answer()
            await query.edit_message_text(
                f"🌍 *选择目标语言*\n当前: *{current}*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )

        elif data == "settings:provider":
            # 显示引擎选择面板
            available = Config.available_providers()
            current = get_chat_config(chat_id).get("provider", Config.DEFAULT_PROVIDER)
            buttons = []
            for p in available:
                icon = "👉" if p == current else "🤖"
                buttons.append([InlineKeyboardButton(
                    f"{icon} {p} — {PROVIDER_MODELS.get(p, '')}",
                    callback_data=f"provider:{p}",
                )])
            buttons.append([InlineKeyboardButton("⬅️ 返回设置", callback_data="settings:back")])
            await query.answer()
            await query.edit_message_text(
                f"🤖 *选择引擎*\n当前: *{current}*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )

        elif data == "settings:auto_on":
            set_chat_config(chat_id, {"auto_translate": True})
            await query.answer("✅ 自动翻译已开启")
            text, markup = _build_settings_panel(chat_id, chat_type)
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

        elif data == "settings:auto_off":
            set_chat_config(chat_id, {"auto_translate": False})
            await query.answer("✅ 自动翻译已关闭")
            text, markup = _build_settings_panel(chat_id, chat_type)
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

        elif data == "settings:reset":
            reset_chat_config(chat_id)
            await query.answer("🔄 已恢复默认设置")
            text, markup = _build_settings_panel(chat_id, chat_type)
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

        elif data == "settings:clear_stats":
            clear_chat_stats(chat_id)
            await query.answer("🗑 统计已清除")
            text, markup = _build_settings_panel(chat_id, chat_type)
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

        elif data == "settings:status":
            # 显示详细统计
            cfg = get_chat_config(chat_id)
            stats = get_stats(chat_id)
            g = get_global_stats()
            provider = cfg.get("provider", Config.DEFAULT_PROVIDER)
            rate = f"{stats['success']/stats['total']*100:.1f}%" if stats["total"] > 0 else "N/A"
            top = max(stats["providers"], key=stats["providers"].get) if stats.get("providers") else "N/A"
            status_text = (
                "📊 *详细统计*\n\n"
                f"📈 翻译: {stats['total']} 次 | 字符: {stats['chars']:,}\n"
                f"✅ 成功: {stats['success']} | ❌ 失败: {stats['fail']}\n"
                f"📊 成功率: {rate} | 常用引擎: {top}\n\n"
                f"🌐 全局: {g['total_translations']:,} 次 | {g['total_chars']:,} 字\n"
                f"💬 聊天数: {g['total_chats']} | 缓存: {len(_translate_cache)}"
            )
            await query.answer()
            await query.edit_message_text(
                status_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ 返回设置", callback_data="settings:back")]]
                ),
            )

        elif data == "settings:back":
            await query.answer()
            text, markup = _build_settings_panel(chat_id, chat_type)
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

        else:
            await query.answer("未知操作")
    except BadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.warning(f"回调异常: {e}")
        await query.answer()


# ═══════════════════════════════════════════
#  /set_lang
# ═══════════════════════════════════════════

async def cmd_set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    if not context.args:
        current = get_chat_config(update.effective_chat.id).get("target_lang", Config.DEFAULT_TARGET_LANG)
        await _safe_reply(
            update.message,
            f"🌍 当前: *{current}*\n\n"
            "/set\\_lang 语言名\n示例: /set\\_lang English\n\n💡 或用 /lang",
            parse_mode="Markdown",
        )
        return
    lang = " ".join(context.args)
    set_chat_config(update.effective_chat.id, {"target_lang": lang})
    await _safe_reply(update.message, f"✅ 目标语言: *{lang}*", parse_mode="Markdown")


# ═══════════════════════════════════════════
#  /set_provider
# ═══════════════════════════════════════════

async def cmd_set_provider(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    available = Config.available_providers()
    if not available:
        await _safe_reply(update.message, "❌ 未配置任何 API Key")
        return

    if not context.args:
        current = get_chat_config(update.effective_chat.id).get("provider", Config.DEFAULT_PROVIDER)
        buttons = []
        for p in available:
            icon = "👉" if p == current else "🤖"
            buttons.append([InlineKeyboardButton(
                f"{icon} {p} — {PROVIDER_MODELS.get(p, '')}", callback_data=f"provider:{p}",
            )])
        await _safe_reply(
            update.message,
            f"🤖 *选择引擎*\n当前: *{current}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    name = context.args[0].lower().strip()
    if name not in available:
        await _safe_reply(update.message,
            f"❌ `{name}` 不可用\n可选: {', '.join(f'`{p}`' for p in available)}",
            parse_mode="Markdown")
        return

    set_chat_config(update.effective_chat.id, {"provider": name})
    await _safe_reply(update.message,
        f"✅ 引擎: *{name}*\n模型: `{PROVIDER_MODELS.get(name, 'N/A')}`",
        parse_mode="Markdown")


# ═══════════════════════════════════════════
#  /set_model
# ═══════════════════════════════════════════

async def cmd_set_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    chat_id = update.effective_chat.id
    cfg = get_chat_config(chat_id)
    provider = cfg.get("provider", Config.DEFAULT_PROVIDER)

    if not context.args:
        current = cfg.get("model", PROVIDER_MODELS.get(provider, "默认"))
        await _safe_reply(update.message,
            f"🧠 模型: `{current}` | 引擎: `{provider}`\n\n"
            "/set\\_model 模型名\n/set\\_model default 恢复",
            parse_mode="Markdown")
        return

    model = " ".join(context.args).strip()
    if model.lower() == "default":
        cfg.pop("model", None)
        set_chat_config(chat_id, cfg)
        await _safe_reply(update.message,
            f"✅ 恢复默认: `{PROVIDER_MODELS.get(provider, '默认')}`", parse_mode="Markdown")
    else:
        set_chat_config(chat_id, {"model": model})
        await _safe_reply(update.message, f"✅ 模型: `{model}`", parse_mode="Markdown")


# ═══════════════════════════════════════════
#  /auto_on, /auto_off
# ═══════════════════════════════════════════

async def cmd_auto_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    chat_id = update.effective_chat.id
    set_chat_config(chat_id, {"auto_translate": True})
    cfg = get_chat_config(chat_id)
    await _safe_reply(update.message,
        f"✅ 自动翻译 *开启*\n🌍 {cfg.get('target_lang', Config.DEFAULT_TARGET_LANG)} | 🤖 `{cfg.get('provider', Config.DEFAULT_PROVIDER)}`",
        parse_mode="Markdown")


async def cmd_auto_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    set_chat_config(update.effective_chat.id, {"auto_translate": False})
    await _safe_reply(update.message, "✅ 自动翻译 *关闭*\n用 /translate 手动翻译", parse_mode="Markdown")


# ═══════════════════════════════════════════
#  /status
# ═══════════════════════════════════════════

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    chat_id = update.effective_chat.id
    cfg = get_chat_config(chat_id)
    stats = get_stats(chat_id)
    g = get_global_stats()

    provider = cfg.get("provider", Config.DEFAULT_PROVIDER)
    auto = cfg.get("auto_translate", update.effective_chat.type == "private")
    model = cfg.get("model", PROVIDER_MODELS.get(provider, "默认"))
    rate = f"{stats['success']/stats['total']*100:.1f}%" if stats["total"] > 0 else "N/A"
    top = max(stats["providers"], key=stats["providers"].get) if stats.get("providers") else "N/A"

    await _safe_reply(update.message,
        "📊 *设置与统计*\n\n"
        f"🤖 `{provider}` | 🧠 `{model}`\n"
        f"🌍 *{cfg.get('target_lang', Config.DEFAULT_TARGET_LANG)}* | {'🟢' if auto else '🔴'} {'开启' if auto else '关闭'}\n\n"
        f"📈 翻译: {stats['total']} 次 | 字符: {stats['chars']:,}\n"
        f"✅ {stats['success']} | ❌ {stats['fail']} | 率: {rate} | 常用: {top}\n\n"
        f"🌐 全局: {g['total_translations']:,} 次 | {g['total_chars']:,} 字 | {g['total_chats']} 聊天 | 缓存: {len(_translate_cache)}",
        parse_mode="Markdown")


# ═══════════════════════════════════════════
#  /translate
# ═══════════════════════════════════════════

async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    if not _check_rate_limit(update.effective_user.id):
        await _safe_reply(update.message, "⚠️ 请求太频繁，请稍后")
        return

    reply_msg = update.message.reply_to_message
    if context.args:
        text = " ".join(context.args)
    elif reply_msg and (reply_msg.text or reply_msg.caption):
        text = reply_msg.text or reply_msg.caption
    else:
        await _safe_reply(update.message,
            "📝 /translate 文本\n或回复消息 + /translate", parse_mode="Markdown")
        return

    await _do_translate(update, context, text)


# ═══════════════════════════════════════════
#  /providers
# ═══════════════════════════════════════════

async def cmd_providers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    available = Config.available_providers()
    current = get_chat_config(update.effective_chat.id).get("provider", Config.DEFAULT_PROVIDER)
    lines = ["🤖 *AI 翻译引擎*\n"]
    for p in ["deepseek", "openai", "claude", "gemini", "groq", "mistral"]:
        m = PROVIDER_MODELS.get(p, "")
        if p == current:
            lines.append(f"  👉 `{p}` — {m} *(当前)*")
        elif p in available:
            lines.append(f"  ✅ `{p}` — {m}")
        else:
            lines.append(f"  ⬜ `{p}` — {m} _(未配置)_")
    lines.append("\n💡 /set\\_provider 切换")
    await _safe_reply(update.message, "\n".join(lines), parse_mode="Markdown")


# ═══════════════════════════════════════════
#  /reset
# ═══════════════════════════════════════════

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    reset_chat_config(update.effective_chat.id)
    await _safe_reply(update.message,
        f"🔄 *已恢复默认*\n`{Config.DEFAULT_PROVIDER}` | *{Config.DEFAULT_TARGET_LANG}*",
        parse_mode="Markdown")


# ═══════════════════════════════════════════
#  /clear_stats
# ═══════════════════════════════════════════

async def cmd_clear_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    clear_chat_stats(update.effective_chat.id)
    await _safe_reply(update.message, "🗑 统计已清除")


# ═══════════════════════════════════════════
#  /id
# ═══════════════════════════════════════════

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    chat, user = update.effective_chat, update.effective_user
    type_map = {"private": "私聊", "group": "群组", "supergroup": "超级群组", "channel": "频道"}
    lines = [
        "🆔 *ID 信息*\n",
        f"👤 用户: `{user.id}`",
        f"💬 聊天: `{chat.id}`",
        f"📌 类型: {type_map.get(chat.type, chat.type)}",
    ]
    if user.username:
        lines.append(f"🏷 @{user.username}")
    if chat.title:
        lines.append(f"📛 {chat.title}")
    await _safe_reply(update.message, "\n".join(lines), parse_mode="Markdown")


# ═══════════════════════════════════════════
#  /ping
# ═══════════════════════════════════════════

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _admin_only(update):
        return
    t0 = time.time()
    msg = await _safe_reply(update.message, "🏓 Pong!")
    bot_ms = (time.time() - t0) * 1000

    provider_name = get_chat_config(update.effective_chat.id).get("provider", Config.DEFAULT_PROVIDER)
    try:
        t1 = time.time()
        p = get_provider(provider_name)
        await p.translate("hello", "中文")
        ai_ms = (time.time() - t1) * 1000
        ai_txt = f"✅ {provider_name} ({ai_ms:.0f}ms)"
    except Exception as e:
        ai_txt = f"❌ {provider_name}: {str(e)[:50]}"

    if msg:
        try:
            await msg.edit_text(
                f"🏓 *Pong!*\n\n📡 Bot: `{bot_ms:.0f}ms`\n🤖 {_escape_md(ai_txt)}",
                parse_mode="Markdown")
        except Exception:
            pass


# ═══════════════════════════════════════════
#  核心翻译（复用）
# ═══════════════════════════════════════════

async def _do_translate(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id = update.effective_chat.id
    cfg = get_chat_config(chat_id)
    provider_name = cfg.get("provider", Config.DEFAULT_PROVIDER)
    target_lang = cfg.get("target_lang", Config.DEFAULT_TARGET_LANG)
    is_private = update.effective_chat.type == "private"

    cached = _get_cached(text, target_lang, provider_name)
    if cached:
        translation, detected, target, engine = cached["translation"], cached["detected_lang"], cached["target_lang"], cached["engine"]
        elapsed, cache_hit = 0.0, True
    else:
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass

        t0 = time.time()
        try:
            r = await translate_text(text, target_lang=target_lang, provider_name=provider_name)
            elapsed = time.time() - t0
            translation, detected, target, engine = r["translation"], r["detected_lang"], r["target_lang"], r["engine"]
            cache_hit = False
            _set_cache(text, target_lang, provider_name, r)
        except Exception as e:
            record_translation(chat_id, provider_name, len(text), success=False)
            logger.error(f"翻译失败: {e}")
            await _safe_reply(update.message, f"❌ 翻译失败: {e}")
            return

    record_translation(chat_id, engine, len(text), success=True)

    fallback = f"\n⚠️ _降级到 {engine}_" if provider_name and engine != provider_name else ""
    speed = "⚡ 缓存" if cache_hit else f"⚡ `{engine}` · {elapsed:.1f}s"

    reply = (
        f"🔤 *{_escape_md(detected)}* → *{_escape_md(target)}*\n\n"
        f"📝 *原文:*\n{_truncate(_escape_md(text))}\n\n"
        f"🌐 *译文:*\n{_truncate(_escape_md(translation))}\n\n"
        f"{speed}{fallback}"
    )
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 复制原文", copy_text=CopyTextButton(text=text)),
        InlineKeyboardButton("📋 复制译文", copy_text=CopyTextButton(text=translation)),
    ]])

    if is_private:
        await _safe_reply(update.message, reply, parse_mode="Markdown", reply_markup=buttons)
    else:
        try:
            await update.message.reply_text(
                reply, parse_mode="Markdown",
                reply_to_message_id=update.message.message_id,
                reply_markup=buttons)
        except BadRequest:
            clean = reply.replace("\\", "")
            await update.message.reply_text(
                clean, reply_to_message_id=update.message.message_id, reply_markup=buttons)


# ═══════════════════════════════════════════
#  自动翻译
# ═══════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    # 过滤 bot 自己的消息，防止自回复
    if update.message.from_user and update.message.from_user.is_bot:
        return

    text = update.message.text or update.message.caption
    if not text or not text.strip():
        return

    text = text.strip()
    if text.startswith("/") or len(text) <= 1:
        return

    if re.fullmatch(r'[\d\s\W]+', text) and len(text) < 5:
        return

    # 非管理员不可使用自动翻译
    if not _is_admin(update.effective_user.id):
        return

    chat_id = update.effective_chat.id
    cfg = get_chat_config(chat_id)
    is_private = update.effective_chat.type == "private"

    if not cfg.get("auto_translate", is_private):
        return

    if not _check_rate_limit(update.effective_user.id):
        return

    await _do_translate(update, context, text)


# ═══════════════════════════════════════════
#  全局错误处理
# ═══════════════════════════════════════════

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    if isinstance(error, Forbidden):
        logger.warning(f"Bot 被封禁: {error}")
        return
    if isinstance(error, RetryAfter):
        logger.warning(f"限速 {error.retry_after}s: {error}")
        return
    if isinstance(error, (TimedOut, NetworkError)):
        logger.warning(f"网络异常: {error}")
        return
    if isinstance(error, BadRequest):
        if "message is not modified" in str(error).lower():
            return
        logger.warning(f"请求异常: {error}")
        return
    logger.error(f"未处理异常: {error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(f"❌ 内部错误: {str(error)[:200]}")
        except Exception:
            pass


# ═══════════════════════════════════════════
#  命令菜单
# ═══════════════════════════════════════════

async def setup_commands(app):
    commands = [
        BotCommand("start", "🚀 启动"),
        BotCommand("help", "📖 帮助"),
        BotCommand("settings", "⚙️ 设置面板"),
        BotCommand("translate", "📝 手动翻译"),
        BotCommand("lang", "🌍 切换语言"),
        BotCommand("set_lang", "🌍 自定义语言"),
        BotCommand("set_provider", "🤖 切换引擎"),
        BotCommand("set_model", "🧠 自定义模型"),
        BotCommand("providers", "📋 查看引擎"),
        BotCommand("auto_on", "🟢 开启自动翻译"),
        BotCommand("auto_off", "🔴 关闭自动翻译"),
        BotCommand("status", "📊 统计"),
        BotCommand("reset", "🔄 恢复默认"),
        BotCommand("clear_stats", "🗑 清除统计"),
        BotCommand("id", "🆔 查看ID"),
        BotCommand("ping", "🏓 延迟"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("命令菜单已注册 (%d 个)", len(commands))
