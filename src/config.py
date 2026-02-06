"""全局配置管理"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # AI API Keys
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")

    # 默认设置
    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "deepseek")
    DEFAULT_TARGET_LANG: str = os.getenv("DEFAULT_TARGET_LANG", "中文")

    # 管理员
    ADMIN_USER_IDS: list[int] = [
        int(uid.strip())
        for uid in os.getenv("ADMIN_USER_IDS", "").split(",")
        if uid.strip().isdigit()
    ]

    # 提供商 → API Key 映射
    PROVIDER_KEYS: dict[str, str] = {}

    @classmethod
    def init(cls):
        cls.PROVIDER_KEYS = {
            "deepseek": cls.DEEPSEEK_API_KEY,
            "openai": cls.OPENAI_API_KEY,
            "claude": cls.CLAUDE_API_KEY,
            "gemini": cls.GEMINI_API_KEY,
            "groq": cls.GROQ_API_KEY,
            "mistral": cls.MISTRAL_API_KEY,
        }

    @classmethod
    def available_providers(cls) -> list[str]:
        """返回已配置 API Key 的提供商列表"""
        return [name for name, key in cls.PROVIDER_KEYS.items() if key]


Config.init()
