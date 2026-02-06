"""持久化存储 — 聊天设置 + 翻译统计"""

import json
import time
import threading
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
STATS_FILE = DATA_DIR / "stats.json"

_lock = threading.Lock()


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text("{}", encoding="utf-8")
    if not STATS_FILE.exists():
        STATS_FILE.write_text("{}", encoding="utf-8")


def _load_json(path: Path) -> dict:
    _ensure_data_dir()
    with _lock:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {}


def _save_json(path: Path, data: dict):
    _ensure_data_dir()
    with _lock:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ═══════════════════════════════════════════
#  聊天设置
# ═══════════════════════════════════════════

def get_chat_config(chat_id: int | str) -> dict:
    """获取聊天配置"""
    return _load_json(SETTINGS_FILE).get(str(chat_id), {})


def set_chat_config(chat_id: int | str, config: dict):
    """更新聊天配置（合并）"""
    settings = _load_json(SETTINGS_FILE)
    key = str(chat_id)
    settings[key] = {**settings.get(key, {}), **config}
    _save_json(SETTINGS_FILE, settings)


def reset_chat_config(chat_id: int | str):
    """重置聊天配置为默认"""
    settings = _load_json(SETTINGS_FILE)
    settings.pop(str(chat_id), None)
    _save_json(SETTINGS_FILE, settings)


# ═══════════════════════════════════════════
#  翻译统计
# ═══════════════════════════════════════════

def record_translation(chat_id: int | str, provider: str, chars: int, success: bool = True):
    """记录一次翻译"""
    stats = _load_json(STATS_FILE)
    key = str(chat_id)
    if key not in stats:
        stats[key] = {
            "total": 0, "success": 0, "fail": 0, "chars": 0,
            "providers": {}, "first_use": time.time(),
        }
    s = stats[key]
    s["total"] += 1
    s["success" if success else "fail"] += 1
    s["chars"] += chars
    s["providers"][provider] = s["providers"].get(provider, 0) + 1
    s["last_use"] = time.time()
    _save_json(STATS_FILE, stats)


def get_stats(chat_id: int | str) -> dict:
    """获取聊天统计"""
    stats = _load_json(STATS_FILE)
    return stats.get(str(chat_id), {
        "total": 0, "success": 0, "fail": 0, "chars": 0, "providers": {},
    })


def get_global_stats() -> dict:
    """全局统计"""
    stats = _load_json(STATS_FILE)
    total = sum(s.get("total", 0) for s in stats.values())
    chars = sum(s.get("chars", 0) for s in stats.values())
    return {"total_translations": total, "total_chars": chars, "total_chats": len(stats)}


def clear_chat_stats(chat_id: int | str):
    """清除聊天统计"""
    stats = _load_json(STATS_FILE)
    stats.pop(str(chat_id), None)
    _save_json(STATS_FILE, stats)
