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
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    
    # Local Disk Storage Path
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "receipt_images")
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()

# Ensure local upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)