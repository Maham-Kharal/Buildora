import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Buildora Enterprise Field Console"
    VERSION: str = "2.6.0"
    API_V1_STR: str = "/api/v1"
    
    # Security / Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super_secret_buildora_key_2026_change_in_prod")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 Days
    
    # Database Connection (PostgreSQL with SQLite fallback)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite:///./buildora.db"
    )
    
    # AI Keys (Google Gemini Free API & Tavily Search)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    GEMINI_FALLBACK_MODEL: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    
    # Local Disk Storage Path
    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "receipt_images")
    )
    POLICY_UPLOAD_DIR: str = os.getenv(
        "POLICY_UPLOAD_DIR",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "policy_documents")
    )

    # Qdrant Vector DB Settings
    QDRANT_URL: str = os.getenv("QDRANT_URL", "")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "buildora_company_policies")

    # Gemini Embedding Model & Chunk Settings
    GEMINI_EMBEDDING_MODEL: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
    GEMINI_EMBEDDING_DIMENSION: int = int(os.getenv("GEMINI_EMBEDDING_DIMENSION", "768"))
    POLICY_CHUNK_SIZE: int = int(os.getenv("POLICY_CHUNK_SIZE", "600"))
    POLICY_CHUNK_OVERLAP: int = int(os.getenv("POLICY_CHUNK_OVERLAP", "100"))
    
    # Policy RAG Retrieval Settings
    POLICY_RETRIEVAL_TOP_K: int = int(os.getenv("POLICY_RETRIEVAL_TOP_K", "5"))
    POLICY_RETRIEVAL_SCORE_THRESHOLD: float = float(os.getenv("POLICY_RETRIEVAL_SCORE_THRESHOLD", "0.3"))
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()

# Ensure local upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.POLICY_UPLOAD_DIR, exist_ok=True)