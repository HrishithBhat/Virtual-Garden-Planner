-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user' NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Ensure role column exists for older installations
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user' NOT NULL;

-- Plants table
CREATE TABLE IF NOT EXISTS plants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    scientific_name VARCHAR(255) NOT NULL,
    duration_days INTEGER NOT NULL,
    type VARCHAR(100) NOT NULL,
    photo_url TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Schedules table (AI generated schedules per garden item)
CREATE TABLE IF NOT EXISTS schedules (
    id SERIAL PRIMARY KEY,
    garden_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    schedule_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks for schedules (persistent checklist)
CREATE TABLE IF NOT EXISTS schedule_tasks (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    day INTEGER NOT NULL,
    task_index INTEGER NOT NULL,
    task_text TEXT NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (schedule_id, day, task_index)
);

-- User notifications (persistent)
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    schedule_id INTEGER NULL,
    day INTEGER NULL,
    url TEXT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Ensure columns exist for older DBs
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS schedule_id INTEGER NULL;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS day INTEGER NULL;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS url TEXT NULL;
