from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine():
    url = get_settings().database_url
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, **kwargs)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db():
    if get_settings().database_url.startswith("sqlite:///./"):
        Path(get_settings().database_url.replace("sqlite:///./", "")).parent.mkdir(
            parents=True, exist_ok=True
        )
    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        migrations = {
            "jobs": {
                "source_links_json": "TEXT DEFAULT '[]'",
                "city": "VARCHAR(120) DEFAULT ''",
                "work_arrangement": "VARCHAR(30) DEFAULT 'unknown'",
                "geo_eligibility": "VARCHAR(30) DEFAULT 'unknown'",
                "role_category": "VARCHAR(80) DEFAULT ''",
            },
            "discovery_runs": {
                "current_source": "VARCHAR(80) DEFAULT ''",
                "fetched_count": "INTEGER DEFAULT 0",
                "new_count": "INTEGER DEFAULT 0",
                "duplicate_count": "INTEGER DEFAULT 0",
                "filtered_count": "INTEGER DEFAULT 0",
                "matched_count": "INTEGER DEFAULT 0",
                "pending_count": "INTEGER DEFAULT 0",
            },
            "settings": {
                "gemini_match_model": "VARCHAR(120) DEFAULT 'gemini-3.5-flash-lite'",
                "gemini_tailor_model": "VARCHAR(120) DEFAULT 'gemini-3.5-flash-lite'",
            },
        }
        with engine.begin() as connection:
            for table, columns in migrations.items():
                existing = {x["name"] for x in inspect(engine).get_columns(table)}
                for name, definition in columns.items():
                    if name not in existing:
                        connection.execute(
                            text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
                        )
