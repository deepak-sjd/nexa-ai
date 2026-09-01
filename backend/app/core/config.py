from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    app_name: str = "AI Chat Assistant API"
    app_env: str = "development"
    debug: bool = True

    database_url: str

    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()