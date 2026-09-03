from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_SECRET_KEY: str
    GEMINI_API_KEY: str = ""  # unused; embeddings are local MPNet
    GROQ_API_KEY: str

    MEMORY_SIMILARITY_THRESHOLD: float = 0.60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()