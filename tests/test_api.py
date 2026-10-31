import os

os.environ["DATABASE_URL"] = "sqlite:///./storage/test.db"
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.demo import seed
from app.main import app
from app.models import Application


def test_dashboard_and_job_page():
    init_db()
    seed()
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert "Fictional GmbH" in client.get("/").text
        assert client.get("/jobs/1").status_code == 200


def test_marking_applied_records_today():
    with TestClient(app) as client:
        response = client.post(
            "/jobs/1/status",
            data={"status": "applied", "notes": "Applied manually"},
            follow_redirects=False,
        )
        assert response.status_code == 303
    with SessionLocal() as session:
        application = session.scalar(select(Application).where(Application.job_id == 1))
        assert application.status == "applied"
        assert application.applied_date is not None


def test_settings_saves_model_choices():
    init_db()
    with TestClient(app) as client:
        response = client.post(
            "/settings",
            follow_redirects=False,
            data={
                "preferred_roles": "PM",
                "locations": "Germany",
                "languages": "English",
                "excluded_keywords": "",
                "minimum_score": "70",
                "gemini_match_model": "gemini-match",
                "gemini_tailor_model": "gemini-tailor",
            },
        )
        assert response.status_code == 303
    from app.db import SessionLocal
    from app.models import Settings

    with SessionLocal() as session:
        item = session.get(Settings, 1)
        assert item.gemini_match_model == "gemini-match"
        assert item.gemini_tailor_model == "gemini-tailor"
