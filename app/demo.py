import json

from .db import SessionLocal, init_db
from .models import CandidateProfile, Job, Settings
from .services.normalize import dedupe_key


def seed():
    init_db()
    with SessionLocal() as s:
        if not s.get(Settings, 1):
            s.add(Settings())
        if not s.scalar(__import__("sqlalchemy", fromlist=["select"]).select(Job)):
            s.add(
                Job(
                    title="Junior Project Coordinator (Demo)",
                    company="Fictional GmbH",
                    location="Berlin, Germany",
                    source="demo",
                    canonical_url="https://example.com/demo-job",
                    description=(
                        "Coordinate projects, improve processes, communicate in English, "
                        "and work with stakeholders."
                    ),
                    dedupe_key=dedupe_key(
                        "Junior Project Coordinator",
                        "Fictional GmbH",
                        "Berlin",
                        "https://example.com/demo-job",
                    ),
                )
            )
        if not s.scalar(__import__("sqlalchemy", fromlist=["select"]).select(CandidateProfile)):
            s.add(
                CandidateProfile(
                    approved=True,
                    data_json=json.dumps(
                        {
                            "personal_details": {
                                "name": "Demo Candidate",
                                "email": "demo@example.com",
                            },
                            "verified_skills": [
                                "project coordination",
                                "process improvement",
                                "stakeholder management",
                            ],
                            "languages": ["English"],
                            "employment_history": [
                                {
                                    "title": "Project Coordinator",
                                    "company": "Fictional Co",
                                    "bullets": [
                                        {"text": "Coordinated cross-functional project milestones."}
                                    ],
                                }
                            ],
                            "education": [],
                            "certifications": [],
                            "projects": [],
                            "achievements": [],
                            "original_bullets": [],
                        }
                    ),
                )
            )
        s.commit()


if __name__ == "__main__":
    seed()
    print("Seeded clearly fictional demo data.")
