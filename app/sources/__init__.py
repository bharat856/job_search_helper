from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

from ..services.normalize import dedupe_key


@dataclass
class JobRecord:
    title: str
    company: str
    location: str
    url: str
    description: str
    source: str
    source_id: str = ""
    posted_at: datetime | None = None

    @property
    def dedupe_key(self):
        return dedupe_key(self.title, self.company, self.location, self.url, self.source_id)


class Source:
    name = "source"

    def fetch(self) -> list[JobRecord]:
        raise NotImplementedError


class GreenhouseSource(Source):
    name = "greenhouse"

    def __init__(self, board: str, company: str = ""):
        self.board, self.company = board, company or board

    def fetch(self):
        data = httpx.get(
            f"https://boards-api.greenhouse.io/v1/boards/{self.board}/jobs?content=true", timeout=20
        ).json()
        return [
            JobRecord(
                j.get("title", ""),
                self.company,
                (j.get("location") or {}).get("name", ""),
                j.get("absolute_url", ""),
                j.get("content", ""),
                self.name,
                str(j.get("id", "")),
            )
            for j in data.get("jobs", [])
        ]


class LeverSource(Source):
    name = "lever"

    def __init__(self, company: str):
        self.company = company

    def fetch(self):
        data = httpx.get(
            f"https://api.lever.co/v0/postings/{self.company}?mode=json", timeout=20
        ).json()
        return [
            JobRecord(
                j.get("text", ""),
                self.company,
                (j.get("categories") or {}).get("location", ""),
                j.get("hostedUrl", ""),
                j.get("descriptionPlain", ""),
                self.name,
                j.get("id", ""),
            )
            for j in data
        ]


class AshbySource(Source):
    name = "ashby"

    def __init__(self, board: str, company: str = ""):
        self.board, self.company = board, company or board

    def fetch(self):
        data = httpx.post(
            "https://api.ashbyhq.com/posting-api/job-board",
            json={"jobBoardName": self.board},
            timeout=20,
        ).json()
        return [
            JobRecord(
                j.get("title", ""),
                self.company,
                j.get("location", ""),
                j.get("jobUrl", ""),
                j.get("descriptionHtml", ""),
                self.name,
                j.get("jobUrl", ""),
            )
            for j in data.get("jobs", [])
        ]


class ManualSource(Source):
    name = "manual"

    def __init__(self, record: JobRecord):
        self.record = record

    def fetch(self):
        return [self.record]
