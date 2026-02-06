"""翻译核心逻辑 — 智能互翻 + 自动降级 + 重试"""

import asyncio
import logging
from src.config import Config
from src.providers import create_provider, BaseProvider

logger = logging.getLogger(__name__)

_provider_cache: dict[str, BaseProvider] = {}

MAX_RETRIES = 2
RETRY_DELAY = 1.0

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
    logger.info(f"已创建提供商: {name}")
    return provider


def _get_fallback_providers(primary: str) -> list[str]:
    """获取降级备选列表"""
    return [p for p in Config.available_providers() if p != primary]


def _is_same_lang(detected: str, target: str) -> bool:
    """判断源语言和目标语言是否相同"""
    d, t = detected.lower().strip(), target.lower().strip()
    return d == t or d in t or t in d


async def translate_text(
    text: str,
    target_lang: str | None = None,
    source_lang: str = "auto",
    provider_name: str | None = None,
) -> dict:
    """
    翻译文本（智能互翻 + 重试 + 降级）

    Returns:
        {"translation": str, "detected_lang": str, "target_lang": str, "engine": str}
    """
    if not text or not text.strip():
        return {"translation": "", "detected_lang": "", "target_lang": "", "engine": ""}

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
            try:
                logger.info(f"[{engine}] 翻译(第{attempt}次): {text[:60]}... → {target}")
                result = await provider.translate(text, target, source_lang)

                translation = result.get("translation", "") if isinstance(result, dict) else str(result)
                if not translation or not translation.strip():
                    logger.warning(f"[{engine}] 第{attempt}次返回空结果")
                    continue

                detected = result.get("detected_lang", "未知") if isinstance(result, dict) else "未知"

                # 智能互翻：源语言==目标语言 且 翻译结果==原文 → 切换目标语言
                if _is_same_lang(detected, target) and translation.strip() == text.strip():
                    alt = SMART_FALLBACK_LANG.get(
                        target.lower().strip(),
                        "English" if "中" in target else "中文"
                    )
                    logger.info(f"[{engine}] 🔄 {detected}={target}，切换到 {alt}")
                    try:
                        r2 = await provider.translate(text, alt, source_lang)
                        t2 = r2.get("translation", "") if isinstance(r2, dict) else str(r2)
                        if t2 and t2.strip() and t2.strip() != text.strip():
                            logger.info(f"[{engine}] ✅ {detected} → {alt}: {t2[:60]}...")
                            return {
                                "translation": t2,
                                "detected_lang": detected,
                                "target_lang": alt,
                                "engine": engine,
                            }
                    except Exception as e2:
                        logger.warning(f"[{engine}] 互翻失败: {e2}")

                logger.info(f"[{engine}] ✅ {detected} → {target}: {translation[:60]}...")
                return {
                    "translation": translation,
                    "detected_lang": detected,
                    "target_lang": target,
                    "engine": engine,
                }

            except Exception as e:
                all_errors.append(f"[{engine}] {e}")
                logger.warning(f"[{engine}] 第{attempt}次出错: {e}")

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)

        if engine != primary:
            logger.info(f"[{engine}] 降级引擎也失败")

    errors_summary = "\n".join(all_errors[-3:])
    raise RuntimeError(f"所有引擎均失败:\n{errors_summary}")
