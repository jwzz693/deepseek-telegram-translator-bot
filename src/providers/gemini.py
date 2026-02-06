"""Google Gemini 提供商"""

from google import genai
from google.genai import types
from .base import BaseProvider


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str | None = None):
        self.model = model or "gemini-2.0-flash"
        self.client = genai.Client(api_key=api_key)

    async def translate(self, text: str, target_lang: str, source_lang: str = "auto") -> dict:
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=self._build_user_prompt(text),
                config=types.GenerateContentConfig(
                    system_instruction=self._build_system_prompt(target_lang, source_lang),
                    temperature=0.1,
                    top_p=0.95,
                    max_output_tokens=4096,
                ),
            )
            return self.parse_response(response.text.strip())
        except Exception as e:
            raise RuntimeError(f"[Gemini] 翻译失败: {e}") from e
