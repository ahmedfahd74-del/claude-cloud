from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Zero-Cost AI Trading OS API"
    app_env: str = "development"
    paper_trading_only: bool = True
    live_execution_enabled: bool = False
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/trading_os"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
