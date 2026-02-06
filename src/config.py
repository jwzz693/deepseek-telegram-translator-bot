"""全局配置管理"""

import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 版本 & 启动时间
VERSION = "2.1.0"
_STARTED_AT = time.time()

# .env 文件路径
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def uptime_str() -> str:
    """返回可读的运行时间"""
    s = int(time.time() - _STARTED_AT)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = []
    if d:
        parts.append(f"{d}天")
    if h:
        parts.append(f"{h}时")
    if m:
        parts.append(f"{m}分")
    parts.append(f"{s}秒")
    return "".join(parts)


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

    # 翻译限制
    MAX_TEXT_LENGTH: int = int(os.getenv("MAX_TEXT_LENGTH", "5000"))
    RATE_LIMIT_PER_MIN: int = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))

    # 管理员（第一个 ID 为主管理员，不可被移除）
    ADMIN_USER_IDS: list[int] = [
        int(uid.strip())
        for uid in os.getenv("ADMIN_USER_IDS", "").split(",")
        if uid.strip().isdigit()
    ]

    # 主管理员 ID（首个配置的管理员）
    PRIMARY_ADMIN: int = ADMIN_USER_IDS[0] if ADMIN_USER_IDS else 0

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

    @classmethod
    def add_admin(cls, user_id: int) -> bool:
        """添加授权用户，返回是否新增成功"""
        if user_id in cls.ADMIN_USER_IDS:
            return False
        cls.ADMIN_USER_IDS.append(user_id)
        cls._save_admin_ids()
        return True

    @classmethod
    def add_admins(cls, user_ids: list[int]) -> list[int]:
        """批量添加授权用户，返回新增成功的 ID 列表"""
        added = []
        for uid in user_ids:
            if uid not in cls.ADMIN_USER_IDS:
                cls.ADMIN_USER_IDS.append(uid)
                added.append(uid)
        if added:
            cls._save_admin_ids()
        return added

    @classmethod
    def remove_admin(cls, user_id: int) -> bool:
        """移除授权用户，主管理员不可移除，返回是否成功"""
        if user_id == cls.PRIMARY_ADMIN:
            return False
        if user_id not in cls.ADMIN_USER_IDS:
            return False
        cls.ADMIN_USER_IDS.remove(user_id)
        cls._save_admin_ids()
        return True

    @classmethod
    def _save_admin_ids(cls):
        """将 ADMIN_USER_IDS 持久化到 .env 文件"""
        new_value = ",".join(str(uid) for uid in cls.ADMIN_USER_IDS)
        if _ENV_FILE.exists():
            content = _ENV_FILE.read_text(encoding="utf-8")
            if re.search(r'^ADMIN_USER_IDS=.*$', content, re.MULTILINE):
                content = re.sub(
                    r'^ADMIN_USER_IDS=.*$',
                    f'ADMIN_USER_IDS={new_value}',
                    content,
                    flags=re.MULTILINE,
                )
            else:
                content += f"\nADMIN_USER_IDS={new_value}\n"
            _ENV_FILE.write_text(content, encoding="utf-8")
        else:
            _ENV_FILE.write_text(f"ADMIN_USER_IDS={new_value}\n", encoding="utf-8")


Config.init()
