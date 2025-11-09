from flask import Flask
from config import Config
import os
from flask import Blueprint
from jinja2 import ChoiceLoader, FileSystemLoader

def create_app():
    app = Flask(__name__,
                template_folder='../frontend/templates',
                static_folder='../frontend/static')

    # Prefer AR templates, then fallback to frontend templates
    ar_templates_path = os.path.join(os.path.dirname(__file__), '..', 'AR', 'templates')
    fe_templates_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'templates')
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(ar_templates_path),
        FileSystemLoader(fe_templates_path)
    ])

    # Expose AR static at /ar-static/*
    ar_static_folder = os.path.join(os.path.dirname(__file__), '..', 'AR', 'static')
    ar_assets = Blueprint('ar', __name__, static_folder=ar_static_folder, static_url_path='/ar-static')
    app.register_blueprint(ar_assets)

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

        # Ensure required user columns exist regardless of schema source
        try:
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user' NOT NULL")
        except Exception as _e:
            print(f"⚠️ Warning ensuring users.role column: {_e}")
        try:
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_pro BOOLEAN DEFAULT FALSE NOT NULL")
        except Exception as _e:
            print(f"⚠️ Warning ensuring users.is_pro column: {_e}")
        conn.commit()
        print("✅ users table has role and is_pro columns ensured")

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
            "ALTER TABLE plants ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE plants ADD COLUMN IF NOT EXISTS created_by INTEGER",
            "ALTER TABLE plants ADD COLUMN IF NOT EXISTS sunlight VARCHAR(50)",
            "ALTER TABLE plants ADD COLUMN IF NOT EXISTS spacing_cm INTEGER",
            "ALTER TABLE plants ADD COLUMN IF NOT EXISTS watering_needs VARCHAR(100)",
            "ALTER TABLE plants ADD COLUMN IF NOT EXISTS model_url TEXT",
            "ALTER TABLE plants ADD COLUMN IF NOT EXISTS growth_height_cm INTEGER",
            "ALTER TABLE plants ADD COLUMN IF NOT EXISTS growth_width_cm INTEGER"
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
            # Weed analyses table for Weed Detection feature
            cur.execute('''
                CREATE TABLE IF NOT EXISTS weed_analyses (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    image_url TEXT,
                    result_type VARCHAR(20) NOT NULL,
                    name VARCHAR(255),
                    harmful_effects TEXT,
                    control_methods TEXT,
                    confidence NUMERIC(5,2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Weed sessions and messages (history and chat)
            cur.execute('''
                CREATE TABLE IF NOT EXISTS weed_sessions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    image_url TEXT,
                    result_name VARCHAR(255),
                    result_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS weed_session_messages (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Indexes for weed session tables
            try:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_weed_session_msgs_session ON weed_session_messages(session_id)")
            except Exception as _e:
                print(f"⚠️ Warning creating index: {_e}")
            try:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_weed_sessions_user ON weed_sessions(user_id)")
            except Exception as _e:
                print(f"⚠️ Warning creating index: {_e}")
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
                    print(f"⚠�� Warning: failed to run alter statement '{stmt}': {e}")
            conn.commit()
            print("✅ market_products table ensured")
        except Exception as e:
            print(f"⚠️ Warning: failed to ensure market_products table: {e}")
            conn.rollback()

        # Ensure garden journal tables exist
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS garden_journals (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    plant_id INTEGER NOT NULL,
                    garden_id INTEGER,
                    title VARCHAR(120) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS garden_journal_entries (
                    id SERIAL PRIMARY KEY,
                    journal_id INTEGER NOT NULL REFERENCES garden_journals(id) ON DELETE CASCADE,
                    entry_date DATE NOT NULL,
                    growth_height_cm NUMERIC(6,2),
                    growth_width_cm NUMERIC(6,2),
                    notes TEXT,
                    photo_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Ensure legacy schemas have required columns and FK
            try:
                cur.execute("ALTER TABLE garden_journal_entries ADD COLUMN IF NOT EXISTS journal_id INTEGER")
            except Exception as _e:
                print(f"⚠️ Warning ensuring garden_journal_entries.journal_id: {_e}")
            try:
                cur.execute("ALTER TABLE garden_journal_entries ADD COLUMN IF NOT EXISTS entry_date DATE")
            except Exception as _e:
                print(f"⚠️ Warning ensuring garden_journal_entries.entry_date: {_e}")
            try:
                cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'garden_journal_entries_journal_id_fk'
                    ) THEN
                        ALTER TABLE garden_journal_entries
                        ADD CONSTRAINT garden_journal_entries_journal_id_fk
                        FOREIGN KEY (journal_id) REFERENCES garden_journals(id) ON DELETE CASCADE;
                    END IF;
                END
                $$;
                """)
            except Exception as _e:
                print(f"⚠️ Warning ensuring garden_journal_entries FK: {_e}")
            conn.commit()
            try:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_garden_journals_user ON garden_journals(user_id)")
            except Exception as _e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                print(f"⚠️ Warning creating idx_garden_journals_user: {_e}")
            try:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_garden_journals_plant ON garden_journals(plant_id)")
            except Exception as _e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                print(f"⚠️ Warning creating idx_garden_journals_plant: {_e}")
            try:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_garden_journal_entries_journal ON garden_journal_entries(journal_id)")
            except Exception as _e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                print(f"⚠️ Warning creating idx_garden_journal_entries_journal: {_e}")
            try:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_garden_journal_entries_date ON garden_journal_entries(entry_date)")
            except Exception as _e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                print(f"⚠️ Warning creating idx_garden_journal_entries_date: {_e}")
            try:
                cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'garden_journals_user_plant_title_unique'
                    ) THEN
                        ALTER TABLE garden_journals ADD CONSTRAINT garden_journals_user_plant_title_unique UNIQUE (user_id, plant_id, title);
                    END IF;
                END
                $$;
                """)
            except Exception as _e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                print(f"⚠️ Warning creating garden journal unique constraint: {_e}")
            conn.commit()
            print("✅ garden journal tables ensured")

            # Ensure AI memories table exists for unified AI memory
            try:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS ai_memories (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        memory_type VARCHAR(50) NOT NULL,
                        k TEXT,
                        v_json TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                try:
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_memories_user ON ai_memories(user_id)")
                except Exception as _e:
                    print(f"⚠️ Warning creating ai_memories user index: {_e}")
                try:
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_memories_type ON ai_memories(memory_type)")
                except Exception as _e:
                    print(f"⚠️ Warning creating ai_memories type index: {_e}")
                try:
                    cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = 'ai_memories_user_type_key_unique'
                        ) THEN
                            ALTER TABLE ai_memories ADD CONSTRAINT ai_memories_user_type_key_unique UNIQUE (user_id, memory_type, k);
                        END IF;
                    END
                    $$;
                    """)
                except Exception as _e:
                    print(f"⚠️ Warning ensuring ai_memories unique constraint: {_e}")
                conn.commit()
                print("✅ ai_memories table ensured")
            except Exception as _e:
                conn.rollback()
                print(f"⚠️ Warning: failed to ensure ai_memories table: {_e}")

            # Ensure rewards / gamification tables
            try:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS rewards_points (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        action_type VARCHAR(100) NOT NULL,
                        points INTEGER NOT NULL,
                        multiplier NUMERIC(6,3) DEFAULT 1.0,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS rewards_badges (
                        id SERIAL PRIMARY KEY,
                        code VARCHAR(50) UNIQUE NOT NULL,
                        name VARCHAR(120) NOT NULL,
                        description TEXT,
                        criteria_json TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS user_badges (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        badge_code VARCHAR(50) NOT NULL,
                        awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, badge_code)
                    )
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS user_streaks (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER UNIQUE NOT NULL,
                        current_streak INTEGER DEFAULT 0,
                        last_action_date DATE
                    )
                ''')
                try:
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_rewards_points_user ON rewards_points(user_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_user_badges_user ON user_badges(user_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_user_streaks_user ON user_streaks(user_id)")
                except Exception as _e:
                    print(f"⚠️ Warning creating rewards indexes: {_e}")

                # Seed default badges if not present
                try:
                    cur.execute("INSERT INTO rewards_badges (code, name, description, criteria_json) VALUES (%s,%s,%s,%s) ON CONFLICT (code) DO NOTHING",
                                ('green_thumb','Green Thumb 🌱','First successful plant care streak','{"type":"streak","days":1}'))
                    cur.execute("INSERT INTO rewards_badges (code, name, description, criteria_json) VALUES (%s,%s,%s,%s) ON CONFLICT (code) DO NOTHING",
                                ('pest_protector','Pest Protector 🐛','Used pest/weed detection 5 times','{"type":"detection","kind":"weed_or_pest","count":5}'))
                    cur.execute("INSERT INTO rewards_badges (code, name, description, criteria_json) VALUES (%s,%s,%s,%s) ON CONFLICT (code) DO NOTHING",
                                ('eco_champion','Eco Champion 🌍','Logged 10 eco-friendly actions','{"type":"eco","count":10}'))
                    cur.execute("INSERT INTO rewards_badges (code, name, description, criteria_json) VALUES (%s,%s,%s,%s) ON CONFLICT (code) DO NOTHING",
                                ('community_helper','Community Helper 🤝','Answered 10 questions in the community','{"type":"community","answers":10}'))
                    cur.execute("INSERT INTO rewards_badges (code, name, description, criteria_json) VALUES (%s,%s,%s,%s) ON CONFLICT (code) DO NOTHING",
                                ('garden_guardian','Garden Guardian 🏅','Reached 500 points total','{"type":"points","threshold":500}'))
                    cur.execute("INSERT INTO rewards_badges (code, name, description, criteria_json) VALUES (%s,%s,%s,%s) ON CONFLICT (code) DO NOTHING",
                                ('dedicated_gardener','Dedicated Gardener','7 day plant care streak','{"type":"streak","days":7}'))
                    cur.execute("INSERT INTO rewards_badges (code, name, description, criteria_json) VALUES (%s,%s,%s,%s) ON CONFLICT (code) DO NOTHING",
                                ('master_grower','Master Grower','30 day plant care streak','{"type":"streak","days":30}'))
                except Exception as _e:
                    print(f"⚠️ Warning seeding rewards badges: {_e}")

                conn.commit()
                print("✅ rewards tables ensured and badges seeded")
            except Exception as _e:
                conn.rollback()
                print(f"⚠️ Warning: failed to ensure rewards tables: {_e}")
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Warning: failed to ensure garden journal tables: {e}")

        # Ensure experts table exists for community module
        try:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS experts (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    expertise VARCHAR(120) NOT NULL,
                    bio TEXT,
                    profile_photo_url TEXT,
                    resume_path TEXT,
                    samples_path TEXT,
                    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                    user_id INTEGER,
                    approved_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Add missing columns safely if schema evolves
            expert_alters = [
                "ALTER TABLE experts ADD COLUMN IF NOT EXISTS bio TEXT",
                "ALTER TABLE experts ADD COLUMN IF NOT EXISTS profile_photo_url TEXT",
                "ALTER TABLE experts ADD COLUMN IF NOT EXISTS resume_path TEXT",
                "ALTER TABLE experts ADD COLUMN IF NOT EXISTS samples_path TEXT",
                "ALTER TABLE experts ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending' NOT NULL",
                "ALTER TABLE experts ADD COLUMN IF NOT EXISTS user_id INTEGER",
                "ALTER TABLE experts ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP",
                "ALTER TABLE experts ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ]
            for stmt in expert_alters:
                try:
                    cur.execute(stmt)
                except Exception as _e:
                    print(f"⚠️ Warning: failed to run alter statement '{stmt}': {_e}")
            # Index for status filtering
            try:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_experts_status ON experts(status)")
            except Exception as _e:
                print(f"⚠️ Warning creating experts index: {_e}")
            conn.commit()
            print("✅ experts table ensured")
            # Ensure conversations (user-to-expert and expert-to-expert) messaging tables
            try:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        title TEXT,
                        created_by INTEGER NOT NULL,
                        is_group BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS conversation_participants (
                        id SERIAL PRIMARY KEY,
                        conversation_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (conversation_id, user_id)
                    )
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS conversation_messages (
                        id SERIAL PRIMARY KEY,
                        conversation_id INTEGER NOT NULL,
                        sender_id INTEGER NOT NULL,
                        message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                # Indexes for performance
                try:
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_messages_conv ON conversation_messages(conversation_id)")
                except Exception as _e:
                    print(f"⚠️ Warning creating conversation_messages index: {_e}")
                try:
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_participants_user ON conversation_participants(user_id)")
                except Exception as _e:
                    print(f"⚠️ Warning creating conv_participants index: {_e}")
                conn.commit()
                print("✅ conversations tables ensured")
                # Ensure conversation_reads to track per-user read state
                try:
                    cur.execute('''
                        CREATE TABLE IF NOT EXISTS conversation_reads (
                            id SERIAL PRIMARY KEY,
                            conversation_id INTEGER NOT NULL,
                            user_id INTEGER NOT NULL,
                            last_read_message_id INTEGER,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE (conversation_id, user_id)
                        )
                    ''')
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_reads_user ON conversation_reads(user_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_reads_conv ON conversation_reads(conversation_id)")
                    conn.commit()
                    print("✅ conversation_reads table ensured")
                except Exception as _e:
                    print(f"⚠️ Warning ensuring conversation_reads: {_e}")
                    conn.rollback()
            except Exception as e:
                print(f"⚠️ Warning: failed to ensure conversations tables: {e}")
                conn.rollback()
        except Exception as e:
            print(f"⚠️ Warning: failed to ensure experts table: {e}")
            conn.rollback()
    except Exception as e:
        print(f"❌ Unexpected error initializing database: {e}")
        conn.rollback()
    finally:
        close_db(conn, cur)
