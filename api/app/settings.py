from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    jwt_private_key: str
    jwt_public_key: str
    demo_replay: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
