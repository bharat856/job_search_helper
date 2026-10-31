from app.schemas import CandidateData, MatchResult
from app.services.latex import latex_escape, render_tex
from app.services.normalize import dedupe_key, normalize_url
from app.services.scoring import fallback_match


def test_url_and_dedupe_are_stable():
    assert normalize_url("HTTPS://Example.com/jobs/1/?utm_source=x") == "https://example.com/jobs/1"
    assert dedupe_key("A", "B", "C", "https://x.test/a") == dedupe_key(
        "A", "B", "C", "https://x.test/a/"
    )


def test_profile_schema_and_fallback_match():
    profile = CandidateData(verified_skills=["python", "project management"], languages=["English"])
    job = type(
        "J", (), {"title": "Project Manager", "description": "Python project management English"}
    )()
    result = fallback_match(job, profile)
    assert isinstance(result, MatchResult)
    assert result.overall_score > 0


def test_latex_escapes_untrusted_text():
    assert r"50\%" in latex_escape("50%")
    assert "\\begin{document}" in render_tex({"personal_details": {"name": "A&B"}})
