from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from html import unescape

import httpx

from ..services.normalize import dedupe_key


def strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def parse_date(value: str | None):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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
    apply_url: str = ""
    city: str = ""
    work_arrangement: str = "unknown"
    geo_eligibility: str = "unknown"
    role_category: str = ""
    source_links: list[str] = field(default_factory=list)

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
                source_links=[j.get("absolute_url", "")],
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
                source_links=[j.get("hostedUrl", "")],
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
                source_links=[j.get("jobUrl", "")],
            )
            for j in data.get("jobs", [])
        ]


class ArbeitnowSource(Source):
    name = "arbeitnow"

    def __init__(self, keywords: list[str], pages: int = 3, timeout: int = 20):
        self.keywords, self.pages, self.timeout = keywords, pages, timeout

    def fetch(self):
        output = []
        for page in range(1, self.pages + 1):
            data = httpx.get(
                "https://www.arbeitnow.com/api/job-board-api",
                params={"page": page},
                timeout=self.timeout,
            ).json()
            jobs = data.get("data", [])
            if not jobs:
                break
            for item in jobs:
                title = item.get("title", "")
                if self.keywords and not any(k.lower() in title.lower() for k in self.keywords):
                    continue
                location = item.get("location", "")
                url = item.get("url", "")
                output.append(
                    JobRecord(
                        title,
                        item.get("company_name", ""),
                        location,
                        url,
                        strip_html(item.get("description", "")),
                        self.name,
                        str(item.get("slug", "") or item.get("id", "")),
                        parse_date(item.get("created_at")),
                        city=location,
                        geo_eligibility="eligible"
                        if "germany" in location.lower() or "deutschland" in location.lower()
                        else "unknown",
                        source_links=[url],
                    )
                )
        return output


class BundesagenturSource(Source):
    name = "bundesagentur"

    def __init__(self, keywords: list[str], api_key: str, pages: int = 3, timeout: int = 20):
        self.keywords, self.api_key, self.pages, self.timeout = keywords, api_key, pages, timeout

    def fetch(self):
        output = []
        for keyword in self.keywords[:10]:
            for page in range(self.pages):
                response = httpx.get(
                    "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs",
                    headers={"X-API-Key": self.api_key},
                    params={"was": keyword, "wo": "Deutschland", "page": page, "size": 100},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                jobs = response.json().get("stellenangebote", response.json().get("jobs", []))
                if not jobs:
                    break
                for item in jobs:
                    location_data = item.get("arbeitsort", {})
                    location = (
                        location_data.get("ort", "")
                        if isinstance(location_data, dict)
                        else location_data
                    )
                    url = item.get("externeUrl", item.get("url", ""))
                    output.append(
                        JobRecord(
                            item.get("beruf", item.get("titel", "")),
                            item.get("arbeitgeber", ""),
                            location,
                            url,
                            item.get("stellenbeschreibung", ""),
                            self.name,
                            str(item.get("referenznummer", item.get("refnr", ""))),
                            parse_date(item.get("aktuelleVeroeffentlichungsdatum")),
                            apply_url=url,
                            city=location,
                            geo_eligibility="eligible",
                            source_links=[url],
                        )
                    )
        return output


class AdzunaSource(Source):
    name = "adzuna"

    def __init__(
        self, app_id: str, app_key: str, keywords: list[str], pages: int = 3, timeout: int = 20
    ):
        self.app_id, self.app_key, self.keywords, self.pages, self.timeout = (
            app_id,
            app_key,
            keywords,
            pages,
            timeout,
        )

    def fetch(self):
        if not self.app_id or not self.app_key:
            return []
        output = []
        for keyword in self.keywords[:10]:
            for page in range(1, self.pages + 1):
                data = httpx.get(
                    f"https://api.adzuna.com/v1/api/jobs/de/search/{page}",
                    params={
                        "app_id": self.app_id,
                        "app_key": self.app_key,
                        "what": keyword,
                        "where": "Germany",
                        "results_per_page": 50,
                        "content-type": "application/json",
                    },
                    timeout=self.timeout,
                ).json()
                jobs = data.get("results", [])
                if not jobs:
                    break
                for item in jobs:
                    location = (item.get("location") or {}).get("display_name", "")
                    url = item.get("redirect_url", "")
                    output.append(
                        JobRecord(
                            item.get("title", ""),
                            (item.get("company") or {}).get("display_name", ""),
                            location,
                            url,
                            strip_html(item.get("description", "")),
                            self.name,
                            str(item.get("id", "")),
                            parse_date(item.get("created")),
                            apply_url=url,
                            city=location,
                            geo_eligibility="eligible"
                            if "germany" in location.lower()
                            else "unknown",
                            source_links=[url],
                        )
                    )
        return output


class JobicySource(Source):
    name = "jobicy"

    def fetch(self):
        data = httpx.get("https://jobicy.com/api/v2/remote-jobs", timeout=20).json()
        output = []
        for item in data.get("jobs", []):
            location = item.get("jobGeo", "")
            if location and not any(
                x in location.lower() for x in ("germany", "europe", "worldwide", "anywhere")
            ):
                continue
            url = item.get("url", "")
            output.append(
                JobRecord(
                    item.get("jobTitle", ""),
                    item.get("companyName", ""),
                    location,
                    url,
                    strip_html(item.get("jobDescription", "")),
                    self.name,
                    str(item.get("id", "")),
                    parse_date(item.get("pubDate")),
                    apply_url=url,
                    work_arrangement="remote",
                    geo_eligibility="eligible" if location else "unknown",
                    source_links=[url],
                )
            )
        return output


class HimalayasSource(Source):
    name = "himalayas"

    def __init__(self, pages: int = 3):
        self.pages = pages

    def fetch(self):
        output, cursor = [], ""
        for _ in range(self.pages):
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            data = httpx.get("https://himalayas.app/jobs/api", params=params, timeout=20).json()
            for item in data.get("jobs", []):
                countries = " ".join(
                    item.get("countries", [])
                    if isinstance(item.get("countries"), list)
                    else [str(item.get("countries", ""))]
                )
                if countries and not any(
                    x in countries.lower() for x in ("germany", "worldwide", "europe")
                ):
                    continue
                url = item.get("applicationLink") or item.get("url", "")
                output.append(
                    JobRecord(
                        item.get("title", ""),
                        item.get("companyName", ""),
                        countries or "Remote",
                        url,
                        strip_html(item.get("description", "")),
                        self.name,
                        str(item.get("guid", item.get("id", ""))),
                        parse_date(item.get("pubDate")),
                        apply_url=url,
                        work_arrangement="remote",
                        geo_eligibility="eligible" if countries else "unknown",
                        source_links=[url, "https://himalayas.app"],
                    )
                )
            cursor = data.get("nextCursor", "")
            if not cursor:
                break
        return output


class SmartRecruitersSource(Source):
    name = "smartrecruiters"

    def __init__(self, company: str, pages: int = 3):
        self.company, self.pages = company, pages

    def fetch(self):
        output = []
        for page in range(self.pages):
            data = httpx.get(
                f"https://api.smartrecruiters.com/v1/companies/{self.company}/postings",
                params={"limit": 100, "offset": page * 100, "country": "DE"},
                timeout=20,
            ).json()
            jobs = data.get("content", data.get("postings", []))
            if not jobs:
                break
            for item in jobs:
                detail = httpx.get(
                    f"https://api.smartrecruiters.com/v1/companies/{self.company}/postings/{item.get('id')}",
                    timeout=20,
                ).json()
                location = (item.get("location") or {}).get("city", "")
                url = item.get("ref", {}).get("jobAd", item.get("jobAdUrl", ""))
                text = (
                    detail.get("jobAd", {})
                    .get("sections", {})
                    .get("jobDescription", {})
                    .get("text", "")
                )
                output.append(
                    JobRecord(
                        item.get("name", ""),
                        self.company,
                        location,
                        url,
                        strip_html(text),
                        self.name,
                        str(item.get("id", "")),
                        parse_date(item.get("releasedDate")),
                        apply_url=url,
                        city=location,
                        geo_eligibility="eligible",
                        source_links=[url],
                    )
                )
        return output


class PersonioSource(Source):
    name = "personio"

    def __init__(self, company: str):
        self.company = company

    def fetch(self):
        root = ET.fromstring(
            httpx.get(f"https://{self.company}.jobs.personio.de/xml", timeout=20).content
        )
        output = []
        for item in root.findall(".//position"):
            url = item.findtext("id", "")
            location = item.findtext("office", "")
            description = " ".join(x.text or "" for x in item.findall(".//jobDescription/value"))
            output.append(
                JobRecord(
                    item.findtext("name", ""),
                    self.company,
                    location,
                    url,
                    strip_html(description),
                    self.name,
                    item.findtext("id", ""),
                    apply_url=url,
                    city=location,
                    geo_eligibility="eligible" if location else "unknown",
                    source_links=[url],
                )
            )
        return output


class RecruiteeSource(Source):
    name = "recruitee"

    def __init__(self, company: str, token: str = ""):
        self.company, self.token = company, token

    def fetch(self):
        headers = {"X-Careers-Sites-Token": self.token} if self.token else {}
        data = httpx.get(
            f"https://{self.company}.recruitee.com/api/offers", headers=headers, timeout=20
        ).json()
        output = []
        for item in data.get("offers", data if isinstance(data, list) else []):
            url = item.get(
                "careers_url", f"https://{self.company}.recruitee.com/o/{item.get('slug', '')}"
            )
            output.append(
                JobRecord(
                    item.get("title", ""),
                    self.company,
                    item.get("location", ""),
                    url,
                    strip_html(item.get("description", "")),
                    self.name,
                    str(item.get("id", item.get("slug", ""))),
                    parse_date(item.get("created_at")),
                    apply_url=item.get("careers_apply_url", url),
                    city=item.get("location", ""),
                    geo_eligibility="eligible"
                    if "germany" in str(item.get("location", "")).lower()
                    else "unknown",
                    source_links=[url],
                )
            )
        return output


class WorkableSource(Source):
    name = "workable"

    def __init__(self, company: str, token: str = ""):
        self.company, self.token = company, token

    def fetch(self):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        data = httpx.get(
            f"https://{self.company}.workable.com/spi/v3/jobs", headers=headers, timeout=20
        ).json()
        output = []
        for item in data.get("jobs", []):
            location = (item.get("location") or {}).get("location_str", "")
            url = item.get("url", item.get("shortlink", ""))
            output.append(
                JobRecord(
                    item.get("title", ""),
                    self.company,
                    location,
                    url,
                    strip_html(item.get("description", "")),
                    self.name,
                    str(item.get("id", item.get("shortcode", ""))),
                    parse_date(item.get("created_at")),
                    apply_url=item.get("application_url", url),
                    city=(item.get("location") or {}).get("city", ""),
                    work_arrangement="remote"
                    if (item.get("location") or {}).get("telecommuting")
                    else "unknown",
                    geo_eligibility="eligible" if "germany" in location.lower() else "unknown",
                    source_links=[url],
                )
            )
        return output


class TeamtailorSource(Source):
    name = "teamtailor"

    def __init__(self, company: str, token: str = ""):
        self.company, self.token = company, token

    def fetch(self):
        headers = (
            {"Authorization": f"Bearer {self.token}", "X-Api-Version": "20210218"}
            if self.token
            else {}
        )
        data = httpx.get(
            "https://api.teamtailor.com/v1/jobs",
            headers=headers,
            params={"filter[company]": self.company},
            timeout=20,
        ).json()
        output = []
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            url = attrs.get("apply-url", attrs.get("url", ""))
            output.append(
                JobRecord(
                    attrs.get("title", ""),
                    self.company,
                    attrs.get("location", ""),
                    url,
                    strip_html(attrs.get("body", "")),
                    self.name,
                    str(item.get("id", "")),
                    parse_date(attrs.get("created-at")),
                    apply_url=url,
                    geo_eligibility="eligible"
                    if "germany" in str(attrs.get("location", "")).lower()
                    else "unknown",
                    source_links=[url],
                )
            )
        return output


class ManualSource(Source):
    name = "manual"

    def __init__(self, record: JobRecord):
        self.record = record

    def fetch(self):
        return [self.record]
