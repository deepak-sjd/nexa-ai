from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    app_name: str = "AI Chat Assistant API"
    app_env: str = "development"
    # Verbose logging. Set DEBUG=true in your local .env only.
    debug: bool = False

    database_url: str

    gemini_api_key: str
    gemini_model: str = "gemini-3.5-flash"
    # Used automatically if the main model keeps returning 503/429.
    gemini_fallback_model: str = "gemini-3.1-flash-lite"
    gemini_max_retries: int = 3
    gemini_image_model: str = "gemini-3.1-flash-image"

    # Comma-separated list of frontend URLs allowed to call this API.
    # Production example: CORS_ORIGINS=https://yourapp.com,https://www.yourapp.com
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 20

    # Generated images are stored here (filename only is kept in
    # the database). Point this at a persistent volume in production.
    generated_images_dir: str = "data/generated_images"
    max_image_prompt_chars: int = 1000

    # ------------------------------------------------------------
    # MOCK IMAGE GENERATION (dev only)
    # ------------------------------------------------------------
    # When on, /images/generate never calls Gemini: it returns one
    # of a few bundled placeholder images after a short simulated
    # delay. Lets you build/test the whole image UI (pending state,
    # errors, retry, gallery, ...) for free and without a quota.
    #
    # Set MOCK_IMAGE_GENERATION=true in backend/.env to enable.
    # Never enable this in production — GEMINI_API_KEY is also not
    # required while it's on, so leaving it on would silently stop
    # generating real images.
    mock_image_generation: bool = False
    mock_image_delay_seconds: float = 1.5

    # ------------------------------------------------------------
    # RATE LIMITING (per client IP, per minute)
    # ------------------------------------------------------------
    rate_limit_enabled: bool = True
    rate_limit_chat_per_minute: int = 20
    rate_limit_image_per_minute: int = 5
    rate_limit_upload_per_minute: int = 10
    # Set TRUST_PROXY_HEADERS=true only when the API sits behind your
    # own reverse proxy / platform load balancer (Render, Railway,
    # nginx...). Otherwise every user would look like one IP.
    trust_proxy_headers: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()