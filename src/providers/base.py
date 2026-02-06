"""AI 提供商基类"""

import json
import re
from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """所有 AI 翻译提供商的基类"""

    name: str = "base"

    @abstractmethod
    async def translate(self, text: str, target_lang: str, source_lang: str = "auto") -> dict:
        """翻译文本，返回 {"detected_lang": "...", "translation": "..."}"""
        ...

    def _build_system_prompt(self, target_lang: str, source_lang: str) -> str:
        """构建高精度翻译系统提示词"""
        source_instruction = (
            f"The source language is {source_lang}."
            if source_lang and source_lang != "auto"
            else "Auto-detect the source language."
        )
        return (
            "You are a world-class professional translator.\n\n"
            "## Task:\n"
            f"{source_instruction}\n"
            f"Translate the given text into **{target_lang}**.\n\n"
            "## Output format (STRICTLY FOLLOW):\n"
            "You MUST respond with a valid JSON object and NOTHING else:\n"
            '{"detected_lang": "<source language name>", "translation": "<translated text>"}\n\n'
            "## Translation rules:\n"
            "1. Translate accurately and naturally, matching target language conventions\n"
            "2. Preserve formatting: line breaks, punctuation, spacing, paragraphs\n"
            "3. Translate idioms/slang into natural equivalents\n"
            "4. Maintain original tone (formal/informal/technical/casual)\n"
            "5. Keep proper nouns in original or widely accepted translation\n"
            "6. Use standard terminology for technical terms\n"
            "7. If text is ALREADY in the target language, set translation to the original text\n"
            "8. For mixed-language text, translate only the non-target-language parts\n"
            "9. detected_lang: readable name (English, 中文, 日本語, etc.)\n"
            "10. Do NOT wrap JSON in markdown code blocks\n"
        )

    def _build_user_prompt(self, text: str) -> str:
        return f"<text_to_translate>\n{text}\n</text_to_translate>"

    @staticmethod
    def parse_response(raw: str) -> dict:
        """解析 AI 返回的 JSON"""
        raw = raw.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        raw = raw.strip()

        # 尝试直接 JSON
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "translation" in data:
                return {
                    "detected_lang": data.get("detected_lang", "未知"),
                    "translation": data["translation"],
                }
        except json.JSONDecodeError:
            pass

        # 回退：提取 JSON 子串
        match = re.search(r'\{[^{}]*"translation"\s*:\s*"((?:[^"\\]|\\.)*)"[^{}]*\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                return {
                    "detected_lang": data.get("detected_lang", "未知"),
                    "translation": data["translation"],
                }
            except json.JSONDecodeError:
                pass

        # 最终回退
        cleaned = raw
        for prefix in ['翻译：', '翻译:', 'Translation:', 'Translation：']:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        cleaned = re.sub(r'</?text_to_translate>', '', cleaned).strip()
        return {"detected_lang": "未知", "translation": cleaned}
