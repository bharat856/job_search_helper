from pathlib import Path

from sqlalchemy import create_engine
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
