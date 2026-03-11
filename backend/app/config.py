from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://contributr:contributr_secret@localhost:5432/contributr"
    database_url_sync: str = "postgresql+psycopg://contributr:contributr_secret@localhost:5432/contributr"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me"
    jwt_secret: str = "change-me"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    backend_cors_origins: list[str] = ["http://localhost:3000"]
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    repos_cache_dir: str = "/tmp/contributr_repos"
    auto_sast_on_sync: bool = False
    auto_dep_scan_on_sync: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
