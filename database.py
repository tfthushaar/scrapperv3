import hashlib
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.exc import IntegrityError

from config import get_first_secret, get_secret
from utils import logger

DEFAULT_DB_PATH = Path("data") / "leads.db"
metadata = MetaData()

sessions_table = Table(
    "sessions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("sector", Text),
    Column("city", Text),
    Column("created_at", String(64)),
    Column("result_count", Integer, default=0, nullable=False),
)

leads_table = Table(
    "leads",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("session_id", Integer, ForeignKey("sessions.id")),
    Column("fingerprint", String(64), unique=True, nullable=False),
    Column("name", Text),
    Column("sector", Text),
    Column("city", Text),
    Column("instagram_url", Text),
    Column("website", Text),
    Column("phone", Text),
    Column("email", Text),
    Column("bio", Text),
    Column("source_url", Text),
    Column("source", Text),
    Column("snippet", Text),
    Column("digital_presence_score", Integer, default=0, nullable=False),
    Column("lead_quality_score", Float, default=0.0, nullable=False),
    Column("tag", String(32), default="Untagged", nullable=False),
    Column("created_at", String(64)),
    Column("all_phones", Text),
    Column("all_emails", Text),
    Column("all_instagram_urls", Text),
    Column("digital_presence_notes", Text, default="", nullable=False),
)

Index("idx_leads_session", leads_table.c.session_id)
Index("idx_leads_fingerprint", leads_table.c.fingerprint)
Index("idx_leads_tag", leads_table.c.tag)


def _raw_database_target() -> str:
    database_url = str(get_secret("DATABASE_URL", "") or "").strip()
    if database_url:
        return database_url

    user = str(get_first_secret(["user", "USER", "DB_USER"], "") or "").strip()
    password = str(
        get_first_secret(["password", "PASSWORD", "DB_PASSWORD"], "") or ""
    ).strip()
    host = str(get_first_secret(["host", "HOST", "DB_HOST"], "") or "").strip()
    port = str(get_first_secret(["port", "PORT", "DB_PORT"], "") or "").strip()
    dbname = str(
        get_first_secret(["dbname", "DBNAME", "DB_NAME"], "") or ""
    ).strip()
    if user and password and host and port and dbname:
        return (
            f"postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}"
            "?sslmode=require"
        )

    db_path = Path(str(get_secret("LEADS_DB_PATH", DEFAULT_DB_PATH))).expanduser()
    return f"sqlite:///{db_path.resolve().as_posix()}"


def _normalized_database_url() -> str:
    database_url = _raw_database_target()
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def _redact_database_target(database_url: str) -> str:
    if "://" not in database_url:
        return database_url
    parts = urlsplit(database_url)
    if "@" not in parts.netloc:
        return database_url
    auth, host = parts.netloc.rsplit("@", 1)
    username = auth.split(":", 1)[0] if auth else "user"
    redacted = f"{username}:***@{host}"
    return urlunsplit((parts.scheme, redacted, parts.path, parts.query, parts.fragment))


def get_database_path() -> str:
    return _redact_database_target(_raw_database_target())


@lru_cache(maxsize=1)
def _engine():
    database_url = _normalized_database_url()
    connect_args = {}
    if database_url.startswith("sqlite:///"):
        sqlite_path = database_url.removeprefix("sqlite:///")
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        connect_args["check_same_thread"] = False
    return create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def reset_engine_cache():
    try:
        _engine().dispose()
    except Exception:
        pass
    _engine.cache_clear()


def _ensure_column(table: str, column: str, ddl: str):
    inspector = inspect(_engine())
    columns = {item["name"] for item in inspector.get_columns(table)}
    if column in columns:
        return
    with _engine().begin() as con:
        con.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def init_db():
    metadata.create_all(_engine())
    _ensure_column("leads", "digital_presence_notes", "TEXT DEFAULT ''")


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
    with _engine().begin() as con:
        result = con.execute(
            insert(sessions_table).values(
                sector=sector,
                city=city,
                created_at=datetime.utcnow().isoformat(),
                result_count=0,
            )
        )
        inserted_id = result.inserted_primary_key[0] if result.inserted_primary_key else None
        if inserted_id is None:
            inserted_id = getattr(result, "lastrowid", None)
        return int(inserted_id)


def save_leads(leads: list, session_id: int) -> int:
    saved = 0
    now = datetime.utcnow().isoformat()
    with _engine().begin() as con:
        for lead in leads:
            values = {
                "session_id": session_id,
                "fingerprint": _fingerprint(lead),
                "name": lead.get("name", ""),
                "sector": lead.get("sector", ""),
                "city": lead.get("city", ""),
                "instagram_url": lead.get("instagram_url", ""),
                "website": lead.get("website", ""),
                "phone": lead.get("phone", ""),
                "email": lead.get("email", ""),
                "bio": (lead.get("bio") or "")[:500],
                "source_url": lead.get("source_url", ""),
                "source": lead.get("source", ""),
                "snippet": (lead.get("snippet") or "")[:300],
                "digital_presence_score": lead.get("digital_presence_score", 0),
                "lead_quality_score": lead.get("lead_quality_score", 0.0),
                "tag": "Untagged",
                "created_at": now,
                "all_phones": json.dumps(lead.get("all_phones", [])),
                "all_emails": json.dumps(lead.get("all_emails", [])),
                "all_instagram_urls": json.dumps(lead.get("all_instagram_urls", [])),
                "digital_presence_notes": lead.get("digital_presence_notes", ""),
            }
            try:
                con.execute(insert(leads_table).values(**values))
                saved += 1
            except IntegrityError:
                continue
            except Exception as exc:
                logger.error(f"DB insert error: {exc}")

        if saved:
            con.execute(
                update(sessions_table)
                .where(sessions_table.c.id == session_id)
                .values(result_count=sessions_table.c.result_count + saved)
            )
    return saved


def get_session_leads(session_id: int) -> list:
    with _engine().connect() as con:
        rows = con.execute(
            select(leads_table)
            .where(leads_table.c.session_id == session_id)
            .order_by(
                leads_table.c.digital_presence_score.desc(),
                leads_table.c.lead_quality_score.desc(),
            )
        ).mappings()
        return [dict(row) for row in rows]


def get_all_sessions() -> list:
    with _engine().connect() as con:
        rows = con.execute(
            select(sessions_table)
            .order_by(sessions_table.c.created_at.desc())
            .limit(100)
        ).mappings()
        return [dict(row) for row in rows]


def update_tag(lead_id: int, tag: str):
    with _engine().begin() as con:
        con.execute(
            update(leads_table)
            .where(leads_table.c.id == lead_id)
            .values(tag=tag)
        )


def get_all_leads(filters: dict | None = None) -> list:
    query = select(leads_table)
    if filters:
        if filters.get("sector"):
            query = query.where(leads_table.c.sector == filters["sector"])
        if filters.get("city"):
            query = query.where(leads_table.c.city == filters["city"])
        if filters.get("tag") and filters["tag"] != "All":
            query = query.where(leads_table.c.tag == filters["tag"])
        if filters.get("has_instagram"):
            query = query.where(leads_table.c.instagram_url != "")
        if filters.get("has_phone"):
            query = query.where(leads_table.c.phone != "")
        if filters.get("min_dp_score") is not None:
            query = query.where(
                leads_table.c.digital_presence_score >= filters["min_dp_score"]
            )

    query = query.order_by(
        leads_table.c.digital_presence_score.desc(),
        leads_table.c.lead_quality_score.desc(),
    )

    with _engine().connect() as con:
        rows = con.execute(query).mappings()
        return [dict(row) for row in rows]
