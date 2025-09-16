from flask import Flask
from config import Config

def create_app():
    app = Flask(__name__, 
                template_folder='../frontend/templates',
                static_folder='../frontend/static')
    
    # Load configuration
    app.config.from_object(Config)
    
    # Register API routes
    from api.routes import api_bp
    app.register_blueprint(api_bp)
    
    return app

def init_database():
    """Initialize database tables and ensure required columns exist"""
    from database.connection import get_db_cursor, close_db
    import os

    schema_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'schema.sql')
    try:
        with open(schema_path, 'r') as f:
            schema = f.read()
    except FileNotFoundError:
        schema = None

    conn, cur = get_db_cursor()
    try:
        if schema:
            try:
                # Execute schema (split by semicolon for multiple statements)
                statements = [stmt.strip() for stmt in schema.split(';') if stmt.strip()]
                for statement in statements:
                    cur.execute(statement)
                conn.commit()
                print("✅ Database initialized successfully from schema.sql")
            except Exception as e:
                print(f"❌ Error executing schema.sql: {e}")
                conn.rollback()

        else:
            # If schema not found, ensure users table exists
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            print("✅ Basic users table ensured (schema.sql not found)")

        # Ensure plants table exists and has required columns (safe to run multiple times)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS plants (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                scientific_name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Add missing columns safely
        alter_statements = [
            "ALTER TABLE plants ADD COLUMN IF NOT EXISTS duration_days INTEGER",
            "ALTER TABLE plants ADD COLUMN IF NOT EXISTS type VARCHAR(100)",
            "ALTER TABLE plants ADD COLUMN IF NOT EXISTS photo_url TEXT",
            "ALTER TABLE plants ADD COLUMN IF NOT EXISTS description TEXT"
        ]
        for stmt in alter_statements:
            try:
                cur.execute(stmt)
            except Exception as e:
                print(f"⚠️ Warning: failed to run alter statement '{stmt}': {e}")

        # Ensure user_gardens table exists
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS user_gardens (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    plant_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, plant_id)
                )
            ''')
        except Exception as e:
            print(f"⚠️ Warning: failed to ensure user_gardens table: {e}")

        # Add custom per-user garden fields to user_gardens safely
        garden_alter_statements = [
            "ALTER TABLE user_gardens ADD COLUMN IF NOT EXISTS nickname VARCHAR(100)",
            "ALTER TABLE user_gardens ADD COLUMN IF NOT EXISTS planted_on DATE",
            "ALTER TABLE user_gardens ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 1",
            "ALTER TABLE user_gardens ADD COLUMN IF NOT EXISTS location VARCHAR(100)",
            "ALTER TABLE user_gardens ADD COLUMN IF NOT EXISTS watering_interval_days INTEGER",
            "ALTER TABLE user_gardens ADD COLUMN IF NOT EXISTS notes TEXT",
            "ALTER TABLE user_gardens ADD COLUMN IF NOT EXISTS last_watered TIMESTAMP"
        ]
        for stmt in garden_alter_statements:
            try:
                cur.execute(stmt)
            except Exception as e:
                print(f"⚠️ Warning: failed to run alter statement '{stmt}': {e}")

        # Ensure unique constraint exists for (user_id, plant_id) to support ON CONFLICT if used elsewhere
        try:
            cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'user_gardens_user_plant_unique'
                ) THEN
                    ALTER TABLE user_gardens ADD CONSTRAINT user_gardens_user_plant_unique UNIQUE (user_id, plant_id);
                END IF;
            END
            $$;
            """)
        except Exception as e:
            print(f"⚠️ Warning: failed to create unique constraint: {e}")

        conn.commit()
        print("✅ Plants and user_gardens tables ensured with required columns")

        # Ensure schedules table exists
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS schedules (
                    id SERIAL PRIMARY KEY,
                    garden_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    schedule_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Chat messages for schedules (per-schedule AI chat)
            cur.execute('''
                CREATE TABLE IF NOT EXISTS schedule_chats (
                    id SERIAL PRIMARY KEY,
                    schedule_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    message TEXT,
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Indexes for faster lookups
            try:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_schedule_chats_schedule ON schedule_chats(schedule_id)")
            except Exception as _e:
                print(f"⚠️ Warning creating index: {_e}")
            conn.commit()
            print("✅ schedules and schedule_chats tables ensured")
            # Ensure general_chats table for global AI assistant
            cur.execute('''
                CREATE TABLE IF NOT EXISTS general_chats (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            try:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_general_chats_user ON general_chats(user_id)")
            except Exception as _e:
                print(f"⚠️ Warning creating general_chats index: {_e}")
            conn.commit()
            print("✅ general_chats table ensured")
        except Exception as e:
            print(f"⚠️ Warning: failed to ensure schedules or chats table: {e}")
            conn.rollback()

        # Ensure market_products table exists and columns are present
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS market_products (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    type VARCHAR(100) NOT NULL,
                    image_url TEXT NOT NULL,
                    buy_url TEXT NOT NULL,
                    price NUMERIC(10,2) DEFAULT 0,
                    quantity INTEGER DEFAULT 0,
                    unit VARCHAR(50) DEFAULT 'unit',
                    brand VARCHAR(100),
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # be safe: add missing columns
            market_alter_statements = [
                "ALTER TABLE market_products ADD COLUMN IF NOT EXISTS type VARCHAR(100)",
                "ALTER TABLE market_products ADD COLUMN IF NOT EXISTS image_url TEXT",
                "ALTER TABLE market_products ADD COLUMN IF NOT EXISTS buy_url TEXT",
                "ALTER TABLE market_products ADD COLUMN IF NOT EXISTS price NUMERIC(10,2) DEFAULT 0",
                "ALTER TABLE market_products ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 0",
                "ALTER TABLE market_products ADD COLUMN IF NOT EXISTS unit VARCHAR(50) DEFAULT 'unit'",
                "ALTER TABLE market_products ADD COLUMN IF NOT EXISTS brand VARCHAR(100)",
                "ALTER TABLE market_products ADD COLUMN IF NOT EXISTS description TEXT",
                "ALTER TABLE market_products ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "ALTER TABLE market_products ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ]
            for stmt in market_alter_statements:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    print(f"⚠️ Warning: failed to run alter statement '{stmt}': {e}")
            conn.commit()
            print("✅ market_products table ensured")
        except Exception as e:
            print(f"⚠️ Warning: failed to ensure market_products table: {e}")
            conn.rollback()
    except Exception as e:
        print(f"❌ Unexpected error initializing database: {e}")
        conn.rollback()
    finally:
        close_db(conn, cur)
