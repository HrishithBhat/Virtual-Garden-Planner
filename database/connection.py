import os
import psycopg
from psycopg.rows import dict_row
from config import Config

config = Config()

def get_db_connection():
    """Get database connection using psycopg v3.
    Connection priority:
    1) DSN env vars (DATABASE_URL/INTERNAL_DATABASE_URL/EXTERNAL_DATABASE_URL/DB_URL)
    2) If DB_HOST is itself a DSN, use it directly
    3) Otherwise use discrete connection params
    Automatically add sslmode=require for Render external hosts when missing.
    """
    try:
        # 1) Prefer DSN-like environment variables
        env_dsn = (
            os.getenv('DATABASE_URL')
            or os.getenv('INTERNAL_DATABASE_URL')
            or os.getenv('postgresql://ai_database_q9ex_user:NO4Bo7O7MiYDoZMbVcEY7xAXZsm73oJB@dpg-d3n74pje5dus73emjtlg-a.oregon-postgres.render.com/ai_database_q9ex')
            or os.getenv('DB_URL')
        )
        if env_dsn:
            dsn = env_dsn.strip()
            if 'render.com' in dsn and 'sslmode=' not in dsn:
                sep = '&' if '?' in dsn else '?'
                dsn = f"{dsn}{sep}sslmode=require"
            return psycopg.connect(dsn, row_factory=dict_row)

        # 2) If DB_HOST was set to a full URL by mistake, support it gracefully
        host = (config.DB_HOST or '').strip()
        if host.startswith('postgres://') or host.startswith('postgresql://'):
            dsn = host
            if 'render.com' in dsn and 'sslmode=' not in dsn:
                sep = '&' if '?' in dsn else '?'
                dsn = f"{dsn}{sep}sslmode=require"
            return psycopg.connect(dsn, row_factory=dict_row)

        # 3) Fall back to discrete params
        return psycopg.connect(
            host=host or 'localhost',
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            port=config.DB_PORT,
            row_factory=dict_row
        )
    except Exception as e:
        print(f"Database connection error: {e}")
        raise

def get_db_cursor():
    """Get database cursor with dict rows"""
    conn = get_db_connection()
    return conn, conn.cursor()

def close_db(conn, cur):
    """Close database connection and cursor"""
    if cur:
        cur.close()
    if conn:
        conn.close()
