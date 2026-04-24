# Lead Research Dashboard

A Streamlit app for ethical B2B prospecting. Give it a sector and city, and it searches the public web for business profiles, extracts contact details, scores digital presence, and stores the results in a reviewable lead table.

## What Changed

- Digital presence scoring is now much richer and less primitive.
- Authentication can be enabled with a secrets-backed username and password.
- Persistence now supports hosted Postgres through `DATABASE_URL`, which is the recommended setup for deployment.
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
- Optional login gate for deployed apps

## Local Setup

```bash
git clone https://github.com/KernelLex/scrapper.git
cd scrapper
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
# Optional login gate
APP_USERNAME=admin
APP_PASSWORD=change-me

# Preferred for deployment persistence
DATABASE_URL=

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
- App authentication: `APP_USERNAME` and `APP_PASSWORD` stored in Streamlit secrets

### 1. Push this repo to GitHub

Make sure your latest changes are committed and pushed.

### 2. Create a free Supabase project

In Supabase:

1. Create a new project.
2. Open the project dashboard.
3. Click `Connect`.
4. Copy the `Session pooler` connection string.
5. If it starts with `postgres://`, change it to `postgresql+psycopg://`.
6. Keep `?sslmode=require` on the end if Supabase includes it.

You do not need to create tables manually. This app will create them on first launch.

### 3. Create your deployment secrets

Use `.streamlit/secrets.example.toml` as the template. Your final secrets should look like this:

```toml
APP_USERNAME = "admin"
APP_PASSWORD = "use-a-strong-password-here"
DATABASE_URL = "postgresql+psycopg://postgres.user:password@host:5432/postgres?sslmode=require"

# Optional
# SERPAPI_KEY = "..."
# GOOGLE_CSE_KEY = "..."
# GOOGLE_CSE_ID = "..."
```

### 4. Deploy on Streamlit Community Cloud

In Streamlit Community Cloud:

1. Click `Create app`.
2. Choose your GitHub repo.
3. Choose the branch you want to deploy.
4. Set the main file path to `app.py`.
5. Open `Advanced settings`.
6. Choose Python `3.11`.
7. Paste the TOML secrets from the previous step into the Secrets field.
8. Click `Deploy`.

On first startup, the app will:

- connect to Supabase using `DATABASE_URL`
- create the `sessions` and `leads` tables automatically
- require the username and password you configured

### 5. Log in

Open the deployed app URL and sign in with the same `APP_USERNAME` and `APP_PASSWORD` you stored in secrets.

## Persistence Notes

- If `DATABASE_URL` is set, the app uses Postgres and your data persists across redeploys.
- If `DATABASE_URL` is not set, the app uses SQLite.
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

## Project Structure

```text
scrapper/
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
