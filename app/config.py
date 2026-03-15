from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str  # required — set OPENAI_API_KEY in .env

    # SQLite by default so the app runs locally without Docker.
    # Set DATABASE_URL in .env or environment to switch to Postgres.
    database_url: str = "sqlite+aiosqlite:///./data/invoice.db"

    # Folder paths
    incoming_folder: str = "./data/incoming"
    processed_folder: str = "./data/processed"
    duplicates_folder: str = "./data/duplicates"
    failed_folder: str = "./data/failed"
    exports_folder: str = "./data/exports"
    log_file: str = "./logs/app.log"

    # LLM settings
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0

    # Extraction settings
    confidence_threshold: float = 0.85
    ocr_fallback_char_limit: int = 50

    # Business rules
    default_payment_days: int = 14

    # Vendor template learning
    layout_change_threshold: float = 0.70
    template_monitor_window: int = 10

    # API defaults
    default_page_limit: int = 100
    export_limit: int = 1000

    # Watcher timeouts (seconds)
    pdf_processing_timeout: int = 120
    db_init_timeout: int = 30

    class Config:
        env_file = ".env"


settings = Settings()