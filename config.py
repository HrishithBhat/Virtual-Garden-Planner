import os
from dotenv import load_dotenv

load_dotenv()
# Also load .env.example as a fallback for local testing if .env is not present
load_dotenv('.env.example', override=False)

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_NAME = os.getenv('DB_NAME', 'authdb')
    DB_USER = os.getenv('DB_USER', 'authuser')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'authpass')
    DB_PORT = os.getenv('DB_PORT', '5432')
    
    @property
    def DATABASE_URL(self):
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
