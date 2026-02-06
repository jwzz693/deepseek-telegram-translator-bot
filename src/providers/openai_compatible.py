"""OpenAI 兼容提供商（DeepSeek / OpenAI / Groq / Mistral）"""

from openai import AsyncOpenAI
from .base import BaseProvider

PROVIDER_CONFIGS = {
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    "mistral": {"base_url": "https://api.mistral.ai/v1", "model": "mistral-small-latest"},
}


class OpenAICompatibleProvider(BaseProvider):

    def __init__(self, provider_name: str, api_key: str, model: str | None = None):
        if provider_name not in PROVIDER_CONFIGS:
            raise ValueError(f"不支持的提供商: {provider_name}")
        cfg = PROVIDER_CONFIGS[provider_name]
        self.name = provider_name
        self.model = model or cfg["model"]
        self.client = AsyncOpenAI(api_key=api_key, base_url=cfg["base_url"])

    async def translate(self, text: str, target_lang: str, source_lang: str = "auto") -> dict:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt(target_lang, source_lang)},
                    {"role": "user", "content": self._build_user_prompt(text)},
                ],
                temperature=0.1,
                max_tokens=4096,
                top_p=0.95,
            )
            return self.parse_response(response.choices[0].message.content.strip())
        except Exception as e:
            raise RuntimeError(f"[{self.name}] 翻译失败: {e}") from e
