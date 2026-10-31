import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    p = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_")])
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), query, ""))


def dedupe_key(title: str, company: str, location: str, url: str = "", source_id: str = "") -> str:
    if url:
        raw = "url:" + normalize_url(url)
    elif source_id:
        raw = "id:" + source_id.lower().strip()
    else:
        raw = "fp:" + "|".join(
            re.sub(r"\W+", " ", x.lower()).strip() for x in (company, title, location)
        )
    return hashlib.sha256(raw.encode()).hexdigest()
