import re

SECTION_NAMES = {
    "about",
    "about the role",
    "the role",
    "responsibilities",
    "what you'll do",
    "requirements",
    "qualifications",
    "what we're looking for",
    "your profile",
    "benefits",
    "what we offer",
    "nice to have",
    "preferred qualifications",
}


def format_job_description(raw: str) -> list[dict]:
    """Turn untrusted ATS HTML/plain text into safe, readable sections for Jinja."""
    text = raw or ""
    text = re.sub(r"<(?:br|/p|/div|/li|/h[1-6])\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\r\n?", "\n", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    sections = []
    current = {"heading": "Job description", "paragraphs": [], "bullets": []}
    for line in lines:
        normalized = re.sub(r"[:：]$", "", line).strip().lower()
        if normalized in SECTION_NAMES:
            if current["paragraphs"] or current["bullets"]:
                sections.append(current)
            current = {"heading": line.rstrip(":："), "paragraphs": [], "bullets": []}
        elif line.startswith("•") or line.startswith("-") or line.startswith("*"):
            current["bullets"].append(line.lstrip("•-* "))
        else:
            current["paragraphs"].append(line)
    if current["paragraphs"] or current["bullets"]:
        sections.append(current)
    return sections or [
        {
            "heading": "Job description",
            "paragraphs": ["Description needed from the original posting."],
            "bullets": [],
        }
    ]
