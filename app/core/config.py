import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM Provider Configurations
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.inceptionlabs.ai/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/mercury-2.5")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    LLM_TIMEOUT_S: int = int(os.getenv("LLM_TIMEOUT_S", "60"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))

    # Retrieval Configurations
    EMBEDDING_BACKEND: str = os.getenv("EMBEDDING_BACKEND", "auto")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    RERANKER_BACKEND: str = os.getenv("RERANKER_BACKEND", "auto")

    DENSE_TOP_K: int = int(os.getenv("DENSE_TOP_K", "20"))
    SPARSE_TOP_K: int = int(os.getenv("SPARSE_TOP_K", "20"))
    RERANK_TOP_K: int = int(os.getenv("RERANK_TOP_K", "6"))

    # Paths
    POLICY_PDF: str = os.getenv("POLICY_PDF", "data/policy/policy.pdf")
    INDEX_DIR: str = os.getenv("INDEX_DIR", "artifacts/index")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()