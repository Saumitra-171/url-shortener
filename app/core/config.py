from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "URL Shortener"
    base_url: str = "http://localhost:8000"
    database_url: str = ""
    redis_url: str = ""
    secret_key: str  # no default on purpose: the app refuses to start without one
    access_token_expire_minutes: int = 60
    run_click_worker: bool = True
    trusted_proxy_hops: int = 0


settings = Settings()