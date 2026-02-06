"""AI 提供商工厂"""

from .base import BaseProvider
from .openai_compatible import OpenAICompatibleProvider, PROVIDER_CONFIGS
from .claude import ClaudeProvider
from .gemini import GeminiProvider


ALL_PROVIDERS = ("deepseek", "openai", "claude", "gemini", "groq", "mistral")


def create_provider(provider_name: str, api_key: str, model: str | None = None) -> BaseProvider:
    """根据名称创建 AI 提供商实例"""
    name = provider_name.lower().strip()
    if name in PROVIDER_CONFIGS:
        return OpenAICompatibleProvider(name, api_key, model)
    elif name == "claude":
        return ClaudeProvider(api_key, model)
    elif name == "gemini":
        return GeminiProvider(api_key, model)
    else:
        raise ValueError(f"不支持: {name}  可选: {', '.join(ALL_PROVIDERS)}")


PROVIDER_MODELS = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o-mini",
    "claude": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile",
    "mistral": "mistral-small-latest",
}

# 引擎显示名称
PROVIDER_DISPLAY = {
    "deepseek": "🧠 DeepSeek",
    "openai": "💚 OpenAI",
    "claude": "🟠 Claude",
    "gemini": "🔵 Gemini",
    "groq": "⚡ Groq",
    "mistral": "🌬️ Mistral",
}

__all__ = ["create_provider", "BaseProvider", "PROVIDER_MODELS", "PROVIDER_DISPLAY", "ALL_PROVIDERS"]
