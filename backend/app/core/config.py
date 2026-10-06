"""应用配置。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "xiaohuiji-rebuild"
    API_PREFIX: str = "/api"

    # 数据库：默认 SQLite（开发），生产用 Postgres
    # 例：postgresql+psycopg://user:pass@host:5432/dbname
    DATABASE_URL: str = "sqlite:///./data.db"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30


settings = Settings()

# JWT 默认密钥 fail-fast：生产环境必须配置真实密钥，否则拒绝启动
import os as _os  # noqa: E402
if settings.JWT_SECRET_KEY == "change-me-in-production":
    _env = _os.getenv("APP_ENV", "dev").lower()
    if _env in ("prod", "production"):
        raise RuntimeError(
            "JWT_SECRET_KEY 未配置：生产环境禁止使用默认密钥，"
            "请在 .env 或环境变量中设置 JWT_SECRET_KEY（建议 32 位以上随机字符串）")
    import logging as _logging  # noqa: E402
    _logging.getLogger(__name__).warning(
        "JWT_SECRET_KEY 使用默认值，仅限开发环境；生产请务必配置！")
