"""持久化存储 — 聊天设置 + 翻译统计（带内存缓存 & 原子写入）"""

import json
import time
import tempfile
import threading
import logging
from pathlib import Path
from copy import deepcopy

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
STATS_FILE = DATA_DIR / "stats.json"
BACKUP_SUFFIX = ".bak"

_lock = threading.Lock()

# 内存缓存，避免每次读盘
_cache: dict[str, dict] = {}
_dirty: set[str] = set()  # 标记需要落盘的文件
_DEBOUNCE_INTERVAL = 5.0  # 攒 5 秒再写盘
_last_flush: dict[str, float] = {}


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in (SETTINGS_FILE, STATS_FILE):
        if not f.exists():
            f.write_text("{}", encoding="utf-8")


def _load_json(path: Path) -> dict:
    """读 JSON — 命中缓存直接返回"""
    key = str(path)
    if key in _cache:
        return deepcopy(_cache[key])
    _ensure_data_dir()
    with _lock:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            data = {}
        _cache[key] = data
        return deepcopy(data)


def _save_json(path: Path, data: dict, *, force: bool = False):
    """原子写入 JSON（先写临时文件再 rename），支持防抖"""
    key = str(path)
    _cache[key] = deepcopy(data)
    _dirty.add(key)

    now = time.time()
    if not force and (now - _last_flush.get(key, 0)) < _DEBOUNCE_INTERVAL:
        return  # 防抖，不立即落盘

    _flush(path, data)


def _flush(path: Path, data: dict):
    """实际落盘：备份 → 原子写入"""
    key = str(path)
    _ensure_data_dir()
    with _lock:
        try:
            # 备份旧文件
            if path.exists():
                bak = path.with_suffix(path.suffix + BACKUP_SUFFIX)
                try:
                    bak.write_bytes(path.read_bytes())
                except OSError:
                    pass

            # 原子写入：写到临时文件 → rename
            content = json.dumps(data, ensure_ascii=False, indent=2)
            fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
            try:
                with open(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                Path(tmp).replace(path)
            except OSError:
                Path(tmp).unlink(missing_ok=True)
                # 降级直接写入
                path.write_text(content, encoding="utf-8")

            _dirty.discard(key)
            _last_flush[key] = time.time()
        except Exception as e:
            logger.error("store flush error for %s: %s", path, e)


def flush_all():
    """强制落盘所有脏数据（关停时调用）"""
    for key in list(_dirty):
        path = Path(key)
        data = _cache.get(key)
        if data is not None:
            _flush(path, data)


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
    _save_json(SETTINGS_FILE, settings, force=True)


def reset_chat_config(chat_id: int | str):
    """重置聊天配置为默认"""
    settings = _load_json(SETTINGS_FILE)
    settings.pop(str(chat_id), None)
    _save_json(SETTINGS_FILE, settings, force=True)


# ═══════════════════════════════════════════
#  翻译统计
# ═══════════════════════════════════════════

def record_translation(chat_id: int | str, provider: str, chars: int, success: bool = True):
    """记录一次翻译（攒 5 秒再写盘，减少 IO）"""
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
    success = sum(s.get("success", 0) for s in stats.values())
    fail = sum(s.get("fail", 0) for s in stats.values())
    return {
        "total_translations": total,
        "total_chars": chars,
        "total_chats": len(stats),
        "success": success,
        "fail": fail,
        "success_rate": f"{success / total * 100:.1f}%" if total else "N/A",
    }


def clear_chat_stats(chat_id: int | str):
    """清除聊天统计"""
    stats = _load_json(STATS_FILE)
    stats.pop(str(chat_id), None)
    _save_json(STATS_FILE, stats, force=True)


def export_all_stats() -> dict:
    """导出全部统计原始数据"""
    return _load_json(STATS_FILE)
