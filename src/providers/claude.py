"""Anthropic Claude 提供商"""

import httpx
from anthropic import AsyncAnthropic
from .base import BaseProvider, DEFAULT_API_TIMEOUT, DEFAULT_MAX_TOKENS


class ClaudeProvider(BaseProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str | None = None):
        self.model = model or "claude-sonnet-4-20250514"
        self.client = AsyncAnthropic(
            api_key=api_key,
            timeout=httpx.Timeout(DEFAULT_API_TIMEOUT, connect=10.0),
            max_retries=0,
        )

    async def translate(self, text: str, target_lang: str, source_lang: str = "auto") -> dict:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=DEFAULT_MAX_TOKENS,
                system=self._build_system_prompt(target_lang, source_lang),
                messages=[{"role": "user", "content": self._build_user_prompt(text)}],
                temperature=0.1,
                top_p=0.95,
            )
            return self.parse_response(response.content[0].text.strip())
        except Exception as e:
            raise RuntimeError(f"[Claude] 翻译失败: {e}") from e
