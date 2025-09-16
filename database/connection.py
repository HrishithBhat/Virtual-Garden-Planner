import psycopg
from psycopg.rows import dict_row
from config import Config

config = Config()

def get_db_connection():
    """Get database connection using psycopg v3"""
    try:
        conn = psycopg.connect(
            host=config.DB_HOST,
            dbname=config.DB_NAME,  # Note: dbname, not database
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            port=config.DB_PORT,
            row_factory=dict_row  # psycopg v3 way for dict rows
        )
        return conn
    except psycopg.Error as e:
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
