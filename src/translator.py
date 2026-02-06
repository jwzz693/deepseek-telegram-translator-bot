"""翻译核心逻辑 — 智能互翻 + 自动降级 + 重试 + 超时控制"""

import asyncio
import logging
import time
from src.config import Config
from src.providers import create_provider, BaseProvider

logger = logging.getLogger(__name__)

_provider_cache: dict[str, BaseProvider] = {}

MAX_RETRIES = 2
RETRY_DELAY = 1.0
TRANSLATE_TIMEOUT = 30.0  # 单次翻译超时（秒）

# 引擎延迟统计
_engine_latency: dict[str, list[float]] = {}
_MAX_LATENCY_SAMPLES = 20

# 智能互翻映射：源语言==目标语言时自动切换
SMART_FALLBACK_LANG = {
    "中文": "English", "chinese": "English",
    "english": "中文",
    "日本語": "English", "japanese": "English",
    "한국어": "English", "korean": "English",
    "русский": "English", "russian": "English",
    "français": "English", "french": "English",
    "español": "English", "spanish": "English",
    "deutsch": "English", "german": "English",
    "português": "English", "portuguese": "English",
    "italiano": "English", "italian": "English",
    "العربية": "English", "arabic": "English",
    "ไทย": "English", "thai": "English",
    "tiếng việt": "English", "vietnamese": "English",
    "bahasa indonesia": "English", "indonesian": "English",
    "हिन्दी": "English", "hindi": "English",
    "tagalog": "English", "filipino": "English",
}


def _record_latency(engine: str, elapsed: float):
    """记录引擎延迟"""
    samples = _engine_latency.setdefault(engine, [])
    samples.append(elapsed)
    if len(samples) > _MAX_LATENCY_SAMPLES:
        samples.pop(0)


def get_engine_avg_latency(engine: str) -> float | None:
    """获取引擎平均延迟（秒），无数据返回 None"""
    samples = _engine_latency.get(engine)
    return sum(samples) / len(samples) if samples else None


def get_provider(provider_name: str | None = None) -> BaseProvider:
    """获取或创建 AI 提供商实例"""
    name = (provider_name or Config.DEFAULT_PROVIDER).lower().strip()
    if name in _provider_cache:
        return _provider_cache[name]

    api_key = Config.PROVIDER_KEYS.get(name)
    if not api_key:
        raise ValueError(f"未配置 {name} 的 API Key")

    provider = create_provider(name, api_key)
    _provider_cache[name] = provider
    logger.info("已创建提供商: %s", name)
    return provider


def clear_provider_cache():
    """清空提供商缓存（热重载时使用）"""
    _provider_cache.clear()


def _get_fallback_providers(primary: str) -> list[str]:
    """获取降级备选列表（按平均延迟排序）"""
    others = [p for p in Config.available_providers() if p != primary]
    others.sort(key=lambda p: get_engine_avg_latency(p) or 999)
    return others


def _is_same_lang(detected: str, target: str) -> bool:
    """判断源语言和目标语言是否相同"""
    d, t = detected.lower().strip(), target.lower().strip()
    return d == t or d in t or t in d


async def _call_with_timeout(provider: BaseProvider, text: str, target: str, source: str) -> dict:
    """带超时的翻译调用"""
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(
            provider.translate(text, target, source),
            timeout=TRANSLATE_TIMEOUT,
        )
        elapsed = time.monotonic() - start
        _record_latency(provider.__class__.__name__, elapsed)
        return result
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start
        raise TimeoutError(f"翻译超时 ({elapsed:.1f}s > {TRANSLATE_TIMEOUT}s)")


async def translate_text(
    text: str,
    target_lang: str | None = None,
    source_lang: str = "auto",
    provider_name: str | None = None,
    custom_model: str | None = None,
) -> dict:
    """
    翻译文本（智能互翻 + 超时 + 重试 + 降级）

    Returns:
        {"translation": str, "detected_lang": str, "target_lang": str,
         "engine": str, "latency": float}
    """
    if not text or not text.strip():
        return {"translation": "", "detected_lang": "", "target_lang": "", "engine": "", "latency": 0}

    # 文本长度检查
    if len(text) > Config.MAX_TEXT_LENGTH:
        raise ValueError(f"文本过长：{len(text)} 字符（最大 {Config.MAX_TEXT_LENGTH}）")

    target = target_lang or Config.DEFAULT_TARGET_LANG
    primary = (provider_name or Config.DEFAULT_PROVIDER).lower().strip()
    try_list = [primary] + _get_fallback_providers(primary)

    all_errors = []

    for engine in try_list:
        try:
            provider = get_provider(engine)
        except ValueError:
            continue

        for attempt in range(1, MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                logger.info("[%s] 翻译(第%d次): %s... → %s", engine, attempt, text[:60], target)
                result = await _call_with_timeout(provider, text, target, source_lang)

                translation = result.get("translation", "") if isinstance(result, dict) else str(result)
                if not translation or not translation.strip():
                    logger.warning("[%s] 第%d次返回空结果", engine, attempt)
                    continue

                detected = result.get("detected_lang", "未知") if isinstance(result, dict) else "未知"
                latency = time.monotonic() - t0

                # 智能互翻：源语言==目标语言 且 翻译结果==原文 → 切换目标语言
                if _is_same_lang(detected, target) and translation.strip() == text.strip():
                    alt = SMART_FALLBACK_LANG.get(
                        target.lower().strip(),
                        "English" if "中" in target else "中文"
                    )
                    logger.info("[%s] 🔄 %s=%s，切换到 %s", engine, detected, target, alt)
                    try:
                        r2 = await _call_with_timeout(provider, text, alt, source_lang)
                        t2 = r2.get("translation", "") if isinstance(r2, dict) else str(r2)
                        if t2 and t2.strip() and t2.strip() != text.strip():
                            logger.info("[%s] ✅ %s → %s: %s...", engine, detected, alt, t2[:60])
                            return {
                                "translation": t2,
                                "detected_lang": detected,
                                "target_lang": alt,
                                "engine": engine,
                                "latency": time.monotonic() - t0,
                            }
                    except Exception as e2:
                        logger.warning("[%s] 互翻失败: %s", engine, e2)

                logger.info("[%s] ✅ %s → %s: %s...", engine, detected, target, translation[:60])
                return {
                    "translation": translation,
                    "detected_lang": detected,
                    "target_lang": target,
                    "engine": engine,
                    "latency": latency,
                }

            except TimeoutError as e:
                all_errors.append(f"[{engine}] ⏱️ {e}")
                logger.warning("[%s] 第%d次超时: %s", engine, attempt, e)
            except Exception as e:
                all_errors.append(f"[{engine}] {e}")
                logger.warning("[%s] 第%d次出错: %s", engine, attempt, e)

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)

        if engine != primary:
            logger.info("[%s] 降级引擎也失败", engine)

    errors_summary = "\n".join(all_errors[-3:])
    raise RuntimeError(f"所有引擎均失败:\n{errors_summary}")
