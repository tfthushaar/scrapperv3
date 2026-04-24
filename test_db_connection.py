from sqlalchemy import create_engine, text

from database import get_database_path
from config import get_first_secret, get_secret


def _database_url() -> str:
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

    raise RuntimeError(
        "No database connection settings found. Set DATABASE_URL or the split "
        "user/password/host/port/dbname variables first."
    )


def main():
    database_url = _database_url()
    engine = create_engine(database_url, pool_pre_ping=True)

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print(f"Connection successful: {get_database_path()}")
    except Exception as exc:
        print(f"Failed to connect: {exc}")
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
