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
