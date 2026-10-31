from app.services.board_registry import identify_board
from app.sources import AdzunaSource, ArbeitnowSource, HimalayasSource, JobRecord
from app.sources.email_alerts import parse_alert_message


class Response:
    status_code = 200
    content = b""

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


def test_arbeitnow_pagination_and_keyword_filter(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs["params"]["page"])
        if kwargs["params"]["page"] == 1:
            return Response(
                {
                    "data": [
                        {
                            "title": "Projektmanager",
                            "company_name": "Acme",
                            "location": "Berlin, Germany",
                            "url": "https://x/1",
                            "description": "<p>Plan</p>",
                        }
                    ]
                }
            )
        return Response({"data": []})

    monkeypatch.setattr("app.sources.httpx.get", fake_get)
    jobs = ArbeitnowSource(["Projektmanager"], pages=3).fetch()
    assert len(jobs) == 1 and jobs[0].description == "Plan"
    assert calls == [1, 2]


def test_himalayas_filters_non_germany(monkeypatch):
    monkeypatch.setattr(
        "app.sources.httpx.get",
        lambda *a, **k: Response(
            {
                "jobs": [
                    {
                        "title": "DE role",
                        "companyName": "A",
                        "countries": ["Germany"],
                        "applicationLink": "https://a",
                    },
                    {
                        "title": "US role",
                        "countries": ["United States"],
                        "applicationLink": "https://b",
                    },
                ],
                "nextCursor": "",
            }
        ),
    )
    jobs = HimalayasSource().fetch()
    assert [x.title for x in jobs] == ["DE role"]


def test_adzuna_missing_credentials_is_noop():
    assert AdzunaSource("", "", ["PM"]).fetch() == []


def test_email_alert_and_board_detection():
    raw = b"From: jobs@linkedin.com\nSubject: Job alert: Project Manager\nContent-Type: text/plain\n\nhttps://www.linkedin.com/jobs/view/123"
    record = parse_alert_message(raw)
    assert record.source == "linkedin"
    assert identify_board("https://boards.greenhouse.io/acme/jobs/123") == ("greenhouse", "acme")
    assert identify_board("https://jobs.ashbyhq.com/linear/123") == ("ashby", "linear")


def test_record_deduplication_key():
    assert (
        JobRecord("A", "B", "Berlin", "https://x", "", "a").dedupe_key
        == JobRecord("A", "B", "Berlin", "https://x", "", "b").dedupe_key
    )
