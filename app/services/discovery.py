import json
from datetime import datetime, timezone

from sqlalchemy import select

from ..config import get_settings
from ..models import DiscoveryRun, Job, JobMatch
from ..schemas import CandidateData
from ..sources import AshbySource, GreenhouseSource, LeverSource
from .scoring import deterministic_score, fallback_match


def run_discovery(session, profile=None):
    settings = get_settings()
    run = DiscoveryRun()
    session.add(run)
    session.flush()
    records = []
    try:
        configs = json.loads(settings.company_boards_json or "{}")
        for item in configs.get("greenhouse", []):
            records += GreenhouseSource(item["board"], item.get("company", "")).fetch()
        for item in configs.get("lever", []):
            records += LeverSource(item["company"]).fetch()
        for item in configs.get("ashby", []):
            records += AshbySource(item["board"], item.get("company", "")).fetch()
        records = records[: settings.max_jobs_per_run]
        candidate = (
            CandidateData.model_validate(json.loads(profile.data_json))
            if profile
            else CandidateData()
        )
        for record in records:
            job = session.scalar(select(Job).where(Job.dedupe_key == record.dedupe_key))
            if not job:
                job = Job(
                    title=record.title,
                    company=record.company,
                    location=record.location,
                    canonical_url=record.url,
                    description=record.description,
                    source=record.source,
                    source_id=record.source_id,
                    posted_at=record.posted_at,
                    dedupe_key=record.dedupe_key,
                    needs_manual_description=not bool(record.description),
                )
                session.add(job)
                session.flush()
            job.last_seen = datetime.now(timezone.utc)
            allowed, _, _ = deterministic_score(
                job,
                candidate,
                session.get(__import__("app.models", fromlist=["Settings"]).Settings, 1)
                or __import__("app.models", fromlist=["Settings"]).Settings(),
            )
            if allowed and job.description and profile:
                result = fallback_match(job, candidate)
                job.match_score = result.overall_score
                session.merge(
                    JobMatch(
                        job_id=job.id,
                        profile_version=profile.version,
                        description_hash="local",
                        result_json=result.model_dump_json(),
                        overall_score=result.overall_score,
                    )
                )
        run.jobs_seen = len(records)
        run.status = "complete"
        run.completed_at = datetime.now(timezone.utc)
        session.commit()
        return run
    except Exception as exc:
        run.status = "partial"
        run.error = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        session.commit()
        return run
