from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "URL Shortener"
    base_url: str = "http://localhost:8000"
    database_url: str = ""
    redis_url: str = ""

    class Config:
        env_file = ".env"


settings = Settings()