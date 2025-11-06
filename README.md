# AI-Garden

AI-Garden is a complete gardening companion that leverages artificial intelligence to help users manage their plants, diagnose diseases, and receive personalized care schedules.

## Features

- Smart plant management with personalized collections
- AI-powered disease detection from leaf photos
- Customized care schedules and task tracking
- Gardening assistant chat for instant help
- Marketplace for gardening tools and supplies
- Expert community for gardening advice
- Admin dashboard with role-based access
- Location-aware plant recommendations on the dashboard (shows plants suitable for the user's saved location with a toggle to view all)

## Setup

### Environment Setup

1. Create a virtual environment:
```bash
python3 -m venv .venv
```

2. Activate the virtual environment:
```bash
# On Linux/macOS
source .venv/bin/activate

# On Windows
.venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root with the following variables (customize as needed):

```
SECRET_KEY=your-secret-key
DB_HOST=localhost
DB_NAME=authdb
DB_USER=authuser
DB_PASSWORD=authpass
DB_PORT=5432

# Optional AI service keys
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
STABILITY_API_KEY=your-stability-key
```

### Running the Application

Start the server:
```bash
python run.py
```

The application will be available at `http://localhost:5000`

### Database Setup and Migrations

This project uses PostgreSQL. Ensure the database defined in your `.env` exists and is reachable.

1. Create the database and user that match your `.env` (example names shown below):

```sql
-- Run in psql or your SQL client (adjust names/passwords)
CREATE USER authuser WITH PASSWORD 'authpass';
CREATE DATABASE authdb OWNER authuser;
GRANT ALL PRIVILEGES ON DATABASE authdb TO authuser;
```

2. Apply the schema and migrations in `database/schema.sql` to your database. It is safe to re-run; statements use IF NOT EXISTS where applicable.

Examples with psql:

```bash
# On Windows PowerShell (assuming psql is in PATH)
psql -h localhost -U authuser -d authdb -f database/schema.sql
```

Notes:
- The schema contains an ALTER to add `users.location` if it doesn't exist. This supports the location-aware dashboard feature.
- Always back up production data before applying schema changes.

## Usage

### Location-aware dashboard

- During registration, you'll be asked for your location (city, state, or country). This is saved to your profile.
- After logging in, the dashboard defaults to showing plants suitable for your location. A small notice appears with a link to “View all plants”.
- Click the link to toggle between “plants for my location” and “all plants”.

### Plant images: tips for reliable display

- Paste direct image URLs that end in a valid image extension (e.g., .jpg, .png, .webp) or use data URIs (`data:image/...`).
- Avoid pasting Google Images redirect links (those containing `/imgres`); they don't point directly to the image. If needed, extract the `imgurl` parameter.
- The backend normalizes common cases to help, but storing a clean, direct URL gives the best results.

## ML Training

To train the disease detection model, add plant disease images to `ML/dataset` organized by disease name as folder names, then:

```bash
python -m ML.train
```


