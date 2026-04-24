# Lead Research Dashboard

A Streamlit app for ethical B2B prospecting. Give it a sector and city, and it searches the public web for business profiles, extracts contact details, scores digital presence, and stores the results in a reviewable lead table.

## What Changed

- Digital presence scoring is now much richer and less primitive.
- Authentication now supports real user accounts with signup and login.
- User data is isolated, so each account only sees its own sessions and leads.
- Persistence supports hosted Postgres through `DATABASE_URL`, which is the recommended deployment setup.
- SQLite remains the local fallback for development.
- The app no longer creates empty sessions when a search returns no results.
- Several small text and encoding issues were cleaned up.

## Features

- Free search with DuckDuckGo by default
- Optional SerpAPI or Google CSE upgrades
- Extracts Instagram, website, email, phone, and bio data from public pages
- Digital Presence Score with human-readable `DP Notes`
- Lead Quality Score for actionability
- Inline tagging with `Hot`, `Warm`, and `Skip`
- CSV export
- Reloadable past sessions
- SQLite for local development and Postgres for deployment
- Signup and login with per-user workspaces

## Local Setup

```bash
git clone https://github.com/tfthushaar/scrapperv3.git
cd scrapperv3
python -m venv .venv
```

Activate the environment:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
streamlit run app.py
```

## Local Configuration

You can optionally create a `.env` file from `.env.example`.

Supported values:

```env
# Auth controls
AUTH_REQUIRED=true
ALLOW_SIGNUP=true

# Optional bootstrap admin account
APP_USERNAME=admin
APP_PASSWORD=change-me

# Preferred for deployment persistence
DATABASE_URL=

# Optional alternative split Postgres settings
user=
password=
host=
port=
dbname=

# Local SQLite fallback
LEADS_DB_PATH=data/leads.db

# Optional search upgrades
SERPAPI_KEY=
GOOGLE_CSE_KEY=
GOOGLE_CSE_ID=
```

## Exact Free Deployment Path

The simplest free deployment for this repo is:

- Hosting: Streamlit Community Cloud
- Database persistence: Supabase Postgres free project
- Authentication: in-app signup and login backed by the same database

### 1. Push this repo to GitHub

Make sure your latest changes are committed and pushed.

### 2. Create a free Supabase project

In Supabase:

1. Create a new project.
2. Open the project dashboard.
3. Click `Connect`.
4. Choose `Direct`.
5. Choose `Session pooler`.
6. Choose `SQLAlchemy`.
7. Copy either the full connection string, or the split host/user/port/dbname details plus your database password.

You do not need to create tables manually. This app will create them on first launch.

### 3. Create your Streamlit secrets

Use `.streamlit/secrets.example.toml` as the template.

Recommended secrets for deployment:

```toml
AUTH_REQUIRED = true
ALLOW_SIGNUP = true

user = "postgres.your_project_ref"
password = "your-supabase-db-password"
host = "aws-1-your-region.pooler.supabase.com"
port = "5432"
dbname = "postgres"
```

Optional bootstrap admin account:

```toml
APP_USERNAME = "admin"
APP_PASSWORD = "set-a-strong-password"
```

If you prefer a single connection string instead of split fields:

```toml
DATABASE_URL = "postgresql+psycopg://postgres.your_project_ref:your-supabase-db-password@aws-1-your-region.pooler.supabase.com:5432/postgres?sslmode=require"
```

### 4. Deploy on Streamlit Community Cloud

In Streamlit Community Cloud:

1. Click `Create app`.
2. Choose the `tfthushaar/scrapperv3` repo.
3. Choose the `main` branch.
4. Set the main file path to `app.py`.
5. Open `Advanced settings`.
6. Choose Python `3.11`.
7. Paste your TOML secrets into the `Secrets` field.
8. Click `Deploy`.

On first startup, the app will:

- connect to Supabase using your database settings
- create the `users`, `sessions`, and `leads` tables automatically
- show signup and login forms

### 5. Sign up

Open the deployed app URL and create an account with a username and password.

If you added `APP_USERNAME` and `APP_PASSWORD`, that account will also exist automatically as a bootstrap admin user.

## Persistence Notes

- If `DATABASE_URL` or the split Postgres settings are set, the app uses Postgres and your data persists across redeploys.
- If no Postgres settings are set, the app uses SQLite.
- Free hosts often wipe local files, so SQLite is not reliable for deployed persistence.
- For deployment, use Postgres.

## Scoring Summary

Higher Digital Presence Score means weaker digital presence and usually a better outreach target.

The score considers:

- no owned website
- social-only or link-in-bio presence
- directory dependence
- weak site-builder domains
- missing or generic email
- short or thin bios
- portfolio, booking, pricing, and testimonials signals
- visible trust indicators like clients, years, studio, featured, and team

Higher Lead Quality Score means the lead is easier to work with.

## Tests

Run tests with:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

You can also test database connectivity directly with:

```bash
python test_db_connection.py
```

## Project Structure

```text
scrapperv3/
|- app.py
|- auth.py
|- config.py
|- database.py
|- extractor.py
|- scoring.py
|- search.py
|- utils.py
|- .streamlit/
\- tests/
```
