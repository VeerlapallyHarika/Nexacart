import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/nexacart.db")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", '["http://localhost:3000"]')

# JWT Auth Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "nexacart-dev-secret-key-change-in-production-2026")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
