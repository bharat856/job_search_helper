from ..db import SessionLocal, init_db
from ..services.discovery import run_discovery


def discover():
    init_db()
    with SessionLocal() as session:
        return run_discovery(session)


if __name__ == "__main__":
    result = discover()
    print(f"discovery {result.status}: {result.jobs_seen} jobs")
