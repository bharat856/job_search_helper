from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from ..models import CompanyBoard

PATTERNS = {
    "greenhouse": re.compile(
        r"boards\.greenhouse\.io/([^/?#]+)|job-boards\.greenhouse\.io/([^/?#]+)"
    ),
    "lever": re.compile(r"jobs\.lever\.co/([^/?#]+)"),
    "ashby": re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)"),
    "smartrecruiters": re.compile(r"careers\.smartrecruiters\.com/([^/?#]+)"),
    "personio": re.compile(r"([a-z0-9-]+)\.jobs\.personio\.(?:de|com)"),
    "recruitee": re.compile(r"([a-z0-9-]+)\.recruitee\.com"),
    "workable": re.compile(r"apply\.workable\.com/([^/?#]+)"),
    "teamtailor": re.compile(r"([a-z0-9-]+)\.teamtailor\.com"),
}


def identify_board(url: str):
    for provider, pattern in PATTERNS.items():
        match = pattern.search(url or "")
        if match:
            return provider, next(x for x in match.groups() if x)
    return None


def register_from_url(session, url: str, company: str, discovery_source: str):
    identified = identify_board(url)
    if not identified:
        return None
    provider, identifier = identified
    existing = session.scalar(
        select(CompanyBoard).where(
            CompanyBoard.provider == provider, CompanyBoard.identifier == identifier
        )
    )
    if existing:
        return existing
    board = CompanyBoard(
        company=company or identifier,
        provider=provider,
        identifier=identifier,
        discovery_source=discovery_source,
        validation_status="pending",
        last_checked=datetime.now(timezone.utc),
    )
    try:
        if provider == "greenhouse":
            response = httpx.get(
                f"https://boards-api.greenhouse.io/v1/boards/{identifier}/jobs", timeout=10
            )
            valid = response.status_code == 200
        elif provider == "lever":
            valid = (
                httpx.get(
                    f"https://api.lever.co/v0/postings/{identifier}?mode=json", timeout=10
                ).status_code
                == 200
            )
        elif provider == "ashby":
            valid = (
                httpx.post(
                    "https://api.ashbyhq.com/posting-api/job-board",
                    json={"jobBoardName": identifier},
                    timeout=10,
                ).status_code
                == 200
            )
        elif provider == "personio":
            valid = (
                httpx.get(f"https://{identifier}.jobs.personio.de/xml", timeout=10).status_code
                == 200
            )
        else:
            valid = True
        board.validation_status = "valid" if valid else "invalid"
    except httpx.HTTPError:
        board.validation_status = "inaccessible"
    session.add(board)
    return board
