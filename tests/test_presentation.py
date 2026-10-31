from app.services.job_format import format_job_description


def test_job_description_is_split_into_safe_sections():
    sections = format_job_description(
        "<h2>Responsibilities</h2><ul><li>Plan projects</li>"
        "<li>Report progress</li></ul><h2>Requirements</h2>English"
    )
    assert sections[0]["heading"] == "Responsibilities"
    assert sections[0]["bullets"] == ["Plan projects", "Report progress"]
    assert sections[1]["heading"] == "Requirements"


def test_job_description_does_not_render_html():
    sections = format_job_description("<script>alert(1)</script><p>Safe text</p>")
    assert "<script>" not in str(sections)
