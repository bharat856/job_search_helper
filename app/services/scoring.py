import hashlib
import json
import re

from ..schemas import CandidateData, CriterionScore, MatchingSkill, MatchResult


def tokens(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}", text.lower())}


def deterministic_score(job, profile: CandidateData, settings) -> tuple[bool, float, list[str]]:
    text = f"{job.title} {job.description}".lower()
    excluded = [x.strip().lower() for x in settings.excluded_keywords.split(",") if x.strip()]
    if any(x in text for x in excluded):
        return False, 0, ["Excluded keyword match"]
    locations = [x.strip().lower() for x in settings.locations.split(",") if x.strip()]
    location_ok = not locations or any(
        x in (job.location or "").lower() or x in text for x in locations
    )
    if not location_ok:
        return False, 0, ["Location mismatch"]
    return True, 0, []


def fallback_match(job, profile: CandidateData) -> MatchResult:
    profile_tokens = tokens(
        " ".join(profile.verified_skills + profile.languages + profile.achievements)
    )
    job_tokens = tokens(job.description + " " + job.title)
    matched = sorted(profile_tokens & job_tokens)
    score = min(100, round(len(matched) / max(1, min(12, len(job_tokens))) * 100, 1))
    return MatchResult(
        matching_skills=[MatchingSkill(skill=x, evidence="verified profile") for x in matched],
        explanation="Deterministic local match; configure Gemini for evidence-rich analysis.",
        criterion_scores=[
            CriterionScore(criterion="required_skills", score=score),
            CriterionScore(criterion="relevant_experience", score=score),
            CriterionScore(criterion="responsibilities", score=score),
            CriterionScore(criterion="location", score=100),
            CriterionScore(criterion="language", score=100),
        ],
        overall_score=score,
        recommendation="strong_match" if score >= 70 else "review",
    )


def cache_hash(description: str, profile_version: int, config: str) -> str:
    return hashlib.sha256(
        json.dumps([description, profile_version, config], sort_keys=True).encode()
    ).hexdigest()
