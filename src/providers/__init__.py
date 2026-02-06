"""AI 提供商工厂"""

from .base import BaseProvider
from .openai_compatible import OpenAICompatibleProvider
from .claude import ClaudeProvider
from .gemini import GeminiProvider


def create_provider(provider_name: str, api_key: str, model: str | None = None) -> BaseProvider:
    """根据名称创建 AI 提供商实例"""
    name = provider_name.lower().strip()
    if name in ("openai", "deepseek", "groq", "mistral"):
        return OpenAICompatibleProvider(name, api_key, model)
    elif name == "claude":
        return ClaudeProvider(api_key, model)
    elif name == "gemini":
        return GeminiProvider(api_key, model)
    else:
        raise ValueError(f"不支持: {name}  可选: deepseek, openai, claude, gemini, groq, mistral")


PROVIDER_MODELS = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o-mini",
    "claude": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile",
    "mistral": "mistral-small-latest",
}

__all__ = ["create_provider", "BaseProvider", "PROVIDER_MODELS"]
