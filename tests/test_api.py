import os

os.environ["DATABASE_URL"] = "sqlite:///./storage/test.db"
from fastapi.testclient import TestClient

from app.db import init_db
from app.demo import seed
from app.main import app


def test_dashboard_and_job_page():
    init_db()
    seed()
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert "Fictional GmbH" in client.get("/").text
        assert client.get("/jobs/1").status_code == 200
