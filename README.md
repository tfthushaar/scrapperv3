# 🔍 Lead Research Dashboard

A **free, local Streamlit app** for ethical B2B prospecting. Give it a sector and city, and it searches the web for publicly listed businesses and social profiles, then scores and organises them into an outreach-ready lead table.

> **No paid API keys required.** Uses DuckDuckGo by default.

---

## Features

- **Zero-cost search** via DuckDuckGo (optional upgrade to SerpAPI / Google CSE)
- Discovers **Instagram profiles**, websites, phone numbers, and emails from public search snippets and pages
- **Digital Presence Score** — ranks leads by how weak their online presence is (higher = better outreach target)
- **Lead Quality Score** — how complete and actionable the contact information is
- Sortable, filterable **Streamlit data table** with inline tag editing (**Hot / Warm / Skip**)
- **CSV export** with one click
- Results persisted in a **local SQLite database** — sessions are reloadable
- Duplicate removal, rate limiting, and source attribution built in

---

## Screenshots

> Run `streamlit run app.py` and open `http://localhost:8501`

| Dashboard | Leads table |
|---|---|
| Enter city + sector in the sidebar | Results appear with scores and tags |

---

## Tech Stack

| Layer | Library |
|---|---|
| UI | [Streamlit](https://streamlit.io) |
| Search | [duckduckgo-search](https://github.com/deedy5/duckduckgo_search) |
| HTML parsing | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) + lxml |
| Phone extraction | [phonenumbers](https://github.com/daviddrysdale/python-phonenumbers) |
| Data | pandas + SQLite3 |
| Config | python-dotenv |

---

## Setup

### 1. Clone

```bash
git clone https://github.com/KernelLex/scrapper.git
cd scrapper
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment (optional)

```bash
cp .env.example .env
```

The app works without editing `.env` at all — DuckDuckGo needs no key.  
If you want higher quotas, uncomment and fill in `SERPAPI_KEY` or `GOOGLE_CSE_KEY` + `GOOGLE_CSE_ID`.

### 5. Run

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## Usage

1. **Enter City** — e.g. `Bangalore`
2. **Enter Sector** — e.g. `wedding photographers`, `bridal makeup artists`, `fitness coaches`, `real estate agents`
3. Apply optional filters (must have Instagram, must have phone, weak presence only)
4. Click **Start Search**
5. Review the leads table — sort by any column
6. Tag each lead: **Hot**, **Warm**, or **Skip** (saved automatically)
7. Export to CSV

---

## Scoring Reference

### Digital Presence Score (DP Score)

Higher score = weaker online presence = better outreach candidate.

| Signal | Points |
|---|---|
| No website at all | +3 |
| Instagram URL used as website | +2 |
| Linktree / link-in-bio tool only | +2 |
| Website built on Wix / Weebly / WordPress.com etc. | +2 |
| Short bio with no portfolio mention | +2 |
| WhatsApp-only contact (no email) | +1 |
| Instagram present but no website | +1 |
| Strong professional website with portfolio | −5 |

### Lead Quality Score

How complete the contact information is (0–10).

| Signal | Points |
|---|---|
| Name found | +1.5 |
| Instagram URL | +2.0 |
| Phone / WhatsApp | +2.5 |
| Email | +2.0 |
| Website | +1.0 |
| Bio / description | +1.0 |

---

## Project Structure

```
scrapper/
├── app.py          — Streamlit UI, search orchestration
├── search.py       — DuckDuckGo / SerpAPI / Google CSE integration
├── extractor.py    — Page fetching, phone/email/Instagram extraction
├── scoring.py      — DP score + lead quality score
├── database.py     — SQLite: sessions, leads, tags
├── utils.py        — Rate limiting, deduplication, logger
├── requirements.txt
└── .env.example
```

---

## Ethical Use

This tool queries **publicly available** search results only.

- It does **not** scrape private Instagram profiles or bypass authentication
- It does **not** access contact info behind logins or paywalls
- It respects rate limits with random delays between requests
- Intended for **manual outreach research**, not mass automation

Please use responsibly and comply with applicable data protection laws.

---

## Optional: Upgrade Search API

| Provider | Free tier | Setup |
|---|---|---|
| DuckDuckGo | Unlimited (rate-limited) | None — works by default |
| SerpAPI | 100 searches/month | Add `SERPAPI_KEY` to `.env` |
| Google CSE | 100 searches/day | Add `GOOGLE_CSE_KEY` + `GOOGLE_CSE_ID` to `.env` |

---

## License

MIT
