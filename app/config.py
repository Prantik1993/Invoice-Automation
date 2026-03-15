from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/invoice_db"

    incoming_folder: str = "./data/incoming"
    processed_folder: str = "./data/processed"
    duplicates_folder: str = "./data/duplicates"
    failed_folder: str = "./data/failed"
    exports_folder: str = "./data/exports"
    log_file: str = "./logs/app.log"

    confidence_threshold: float = 0.85
    ocr_fallback_char_limit: int = 50

    class Config:
        env_file = ".env"


settings = Settings()
