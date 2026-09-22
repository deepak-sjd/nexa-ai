from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    app_name: str = "AI Chat Assistant API"
    app_env: str = "development"
    debug: bool = True

    database_url: str

    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"
    gemini_image_model: str = "gemini-3.1-flash-image"

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

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()