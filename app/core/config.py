from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str
    db_name: str = "premed_portal"

    # Security
    matric_pepper: str
    admin_pepper: str
    jwt_secret: str
    jwt_expire_hours: int = 2

    # CORS
    frontend_url: str = "http://localhost:5173"

    # Rate limiting
    login_rate_limit: str = "5/15minutes"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
