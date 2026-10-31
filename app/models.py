from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now():
    return datetime.now(timezone.utc)


class Settings(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    preferred_roles: Mapped[str] = mapped_column(
        Text, default="Junior Project Manager,PMO,Project Coordinator"
    )
    locations: Mapped[str] = mapped_column(Text, default="Germany")
    languages: Mapped[str] = mapped_column(Text, default="English")
    seniority: Mapped[str] = mapped_column(String(100), default="junior,associate")
    excluded_keywords: Mapped[str] = mapped_column(Text, default="")
    preferred_companies: Mapped[str] = mapped_column(Text, default="")
    work_arrangements: Mapped[str] = mapped_column(Text, default="remote,hybrid,on-site")
    minimum_score: Mapped[int] = mapped_column(Integer, default=70)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    source_filename: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class JobSource(Base):
    __tablename__ = "job_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    kind: Mapped[str] = mapped_column(String(40))
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_job_dedupe"),
        Index("ix_job_score", "match_score"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255), default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(80), default="manual")
    source_id: Mapped[Optional[str]] = mapped_column(String(255))
    canonical_url: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    fetch_status: Mapped[str] = mapped_column(String(40), default="ok")
    expired: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_manual_description: Mapped[bool] = mapped_column(Boolean, default=False)
    dedupe_key: Mapped[str] = mapped_column(String(512))
    match_score: Mapped[Optional[float]] = mapped_column(Float)
    application_status: Mapped[str] = mapped_column(String(30), default="new")
    match: Mapped[Optional["JobMatch"]] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )


class JobMatch(Base):
    __tablename__ = "job_matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    profile_version: Mapped[int] = mapped_column(Integer)
    description_hash: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    overall_score: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    job: Mapped[Job] = relationship(back_populates="match")


class GeneratedResume(Base):
    __tablename__ = "generated_resumes"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_json: Mapped[str] = mapped_column(Text, default="{}")
    tex_content: Mapped[str] = mapped_column(Text, default="")
    pdf_path: Mapped[Optional[str]] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="new")
    notes: Mapped[str] = mapped_column(Text, default="")
    applied_date: Mapped[Optional[date]] = mapped_column(Date)
    follow_up_date: Mapped[Optional[date]] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), default="running")
    jobs_seen: Mapped[int] = mapped_column(Integer, default=0)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
