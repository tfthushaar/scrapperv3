import sqlite3
import json
import hashlib
from datetime import datetime
from utils import logger

DB_PATH = "leads.db"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    con = _conn()
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sector      TEXT,
            city        TEXT,
            created_at  TEXT,
            result_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS leads (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id              INTEGER,
            fingerprint             TEXT UNIQUE,
            name                    TEXT,
            sector                  TEXT,
            city                    TEXT,
            instagram_url           TEXT,
            website                 TEXT,
            phone                   TEXT,
            email                   TEXT,
            bio                     TEXT,
            source_url              TEXT,
            source                  TEXT,
            snippet                 TEXT,
            digital_presence_score  INTEGER DEFAULT 0,
            lead_quality_score      REAL    DEFAULT 0.0,
            tag                     TEXT    DEFAULT 'Untagged',
            created_at              TEXT,
            all_phones              TEXT,
            all_emails              TEXT,
            all_instagram_urls      TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_leads_session     ON leads(session_id);
        CREATE INDEX IF NOT EXISTS idx_leads_fingerprint ON leads(fingerprint);
        CREATE INDEX IF NOT EXISTS idx_leads_tag         ON leads(tag);
        """
    )
    con.commit()
    con.close()


def _fingerprint(lead: dict) -> str:
    key = (
        lead.get("instagram_url")
        or lead.get("phone")
        or lead.get("source_url")
        or lead.get("name")
        or ""
    )
    return hashlib.md5(key.lower().strip().encode()).hexdigest()


def create_session(sector: str, city: str) -> int:
    con = _conn()
    cur = con.execute(
        "INSERT INTO sessions (sector, city, created_at) VALUES (?, ?, ?)",
        (sector, city, datetime.utcnow().isoformat()),
    )
    sid = cur.lastrowid
    con.commit()
    con.close()
    return sid


def save_leads(leads: list, session_id: int) -> int:
    con = _conn()
    saved = 0
    now = datetime.utcnow().isoformat()
    for lead in leads:
        fp = _fingerprint(lead)
        try:
            con.execute(
                """
                INSERT OR IGNORE INTO leads
                    (session_id, fingerprint, name, sector, city,
                     instagram_url, website, phone, email, bio,
                     source_url, source, snippet,
                     digital_presence_score, lead_quality_score,
                     tag, created_at,
                     all_phones, all_emails, all_instagram_urls)
                VALUES (?,?,?,?,?, ?,?,?,?,?, ?,?,?, ?,?, ?,?, ?,?,?)
                """,
                (
                    session_id,
                    fp,
                    lead.get("name", ""),
                    lead.get("sector", ""),
                    lead.get("city", ""),
                    lead.get("instagram_url", ""),
                    lead.get("website", ""),
                    lead.get("phone", ""),
                    lead.get("email", ""),
                    (lead.get("bio") or "")[:500],
                    lead.get("source_url", ""),
                    lead.get("source", ""),
                    (lead.get("snippet") or "")[:300],
                    lead.get("digital_presence_score", 0),
                    lead.get("lead_quality_score", 0.0),
                    "Untagged",
                    now,
                    json.dumps(lead.get("all_phones", [])),
                    json.dumps(lead.get("all_emails", [])),
                    json.dumps(lead.get("all_instagram_urls", [])),
                ),
            )
            saved += 1
        except Exception as e:
            logger.error(f"DB insert error: {e}")
    con.execute(
        "UPDATE sessions SET result_count = result_count + ? WHERE id = ?",
        (saved, session_id),
    )
    con.commit()
    con.close()
    return saved


def get_session_leads(session_id: int) -> list:
    con = _conn()
    rows = con.execute(
        "SELECT * FROM leads WHERE session_id = ? ORDER BY lead_quality_score DESC",
        (session_id,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_all_sessions() -> list:
    con = _conn()
    rows = con.execute(
        "SELECT * FROM sessions ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def update_tag(lead_id: int, tag: str):
    con = _conn()
    con.execute("UPDATE leads SET tag = ? WHERE id = ?", (tag, lead_id))
    con.commit()
    con.close()


def get_all_leads(filters: dict | None = None) -> list:
    con = _conn()
    q = "SELECT * FROM leads WHERE 1=1"
    params: list = []
    if filters:
        if filters.get("sector"):
            q += " AND sector = ?"
            params.append(filters["sector"])
        if filters.get("city"):
            q += " AND city = ?"
            params.append(filters["city"])
        if filters.get("tag") and filters["tag"] != "All":
            q += " AND tag = ?"
            params.append(filters["tag"])
        if filters.get("has_instagram"):
            q += " AND instagram_url != ''"
        if filters.get("has_phone"):
            q += " AND phone != ''"
        if filters.get("min_dp_score") is not None:
            q += " AND digital_presence_score >= ?"
            params.append(filters["min_dp_score"])
    q += " ORDER BY lead_quality_score DESC"
    rows = con.execute(q, params).fetchall()
    con.close()
    return [dict(r) for r in rows]
