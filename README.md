# Job Search Helper

Local, single-user MVP for discovering public ATS postings, reviewing heuristic fit, and producing a factual tailored resume for manual applications. It does not auto-submit applications.

## Quick start (macOS/Linux)

Requires Python 3.12 and, for PDF output, [Tectonic](https://tectonic-typesetting.github.io/). Copy `.env.example` to `.env`, set `GEMINI_API_KEY` only if you want Gemini analysis, then:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
python -m app.demo
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Demo content is fictional and clearly labeled in the seeded job. Upload a real PDF/DOCX/TEX resume from Settings; review the profile before approving it for tailoring. The current MVP preserves upload text locally and provides the structured profile storage; Gemini calls are server-side only and require explicit configuration.

Docker:

```bash
cp .env.example .env
docker compose up --build
```

## Sources and daily run

Configure known boards in `COMPANY_BOARDS_JSON`, for example:

```json
{"greenhouse":[{"board":"gitlab","company":"GitLab"}],"lever":[{"company":"canonical"}],"ashby":[{"board":"linear","company":"Linear"}]}
```

These are public board endpoints and require known identifiers; there is no invented global ATS search. Add adapters under `app/sources`. Run `python -m app.tasks.discover`. An authorized IMAP alert adapter exists separately and stores only links when a public description cannot be retrieved; it is not direct LinkedIn, Indeed, or StepStone API access. Never put mailbox passwords or API keys in source code.

The optional APScheduler integration can be added to the process with `ENABLE_SCHEDULER=true`; deploy only one instance because SQLite is single-user/local. A mounted `./storage` volume is the realistic always-on Docker strategy. GitHub Actions runners are ephemeral: use an explicitly configured durable external `DATABASE_URL` or build an artifact export/import workflow; a local SQLite file in Actions is not persistent.

## Gemini, model settings, and privacy

The official `google-genai` SDK is used. Models default to `gemini-3.5-flash-lite` for matching and tailoring and can be changed independently on Settings. The server-side connection test lists models accessible to the configured key, marks generation-capable models, sends a small request using the selected model, and surfaces authentication, model-not-found, and quota errors. API keys never enter the browser or logs. Availability/free-tier quotas can change by region and account; verify current limits in Google's Gemini API documentation before use. The app never silently switches to a paid provider and stops after `MAX_LLM_CALLS_PER_RUN`. Retries use bounded exponential backoff and structured Pydantic validation. Obtain informed consent before sending resume data to Gemini; free-tier inputs may be used by Google to improve products according to Google's current terms/settings.

## Tests and limitations

```bash
ruff check app tests
pytest
```

This MVP includes models for profiles, jobs, matches, resumes, applications, sources, settings, and discovery runs; public Greenhouse/Lever/Ashby adapters; deduplication; deterministic matching; upload extraction; safe LaTeX escaping; manual application statuses; and a Bootstrap dashboard. Tectonic is optional at runtime: without it, `.tex` remains downloadable and the UI reports that PDF compilation requires installation. Before public exposure, configure `APP_PASSWORD`, HTTPS, stronger session persistence, and a durable database. No private resume, database, API key, or production profile is committed.

## Germany-wide discovery expansion

Implemented and tested with mocked responses:

- Arbeitnow public paginated feed (no credential; live smoke-tested).
- Bundesagentur für Arbeit Jobsuche API adapter using `BUNDESAGENTUR_API_KEY` (the documented default is `jobboerse-jobsuche`).
- Optional Adzuna Germany adapter using `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`.
- Jobicy and Himalayas remote feeds, retaining only Germany/Europe/worldwide/unknown-eligibility records.
- Existing Greenhouse, Lever, and Ashby adapters, plus SmartRecruiters company postings and Personio XML career feeds.
- Authorized IMAP alert parsing for LinkedIn, Indeed, StepStone, and XING. This never logs in to those sites or scrapes private pages. Alerts without a public description are retained as `Description needed` and can be completed manually.

Recruitee, Workable, and Teamtailor are recognized by the board registry when a legitimate employer URL is encountered, but are not fetched globally without a documented company-specific feed configuration. EURES is intentionally disabled because no accessible, authorized public job-search API was identified for this application. No global LinkedIn/Indeed/StepStone/XING scraper is implemented.

Discovery is now backgrounded through `POST /refresh`, with progress at `/api/discovery/status/{run_id}`. The dashboard polls this endpoint and shows fetched, new, duplicate, filtered, matched, pending, and source-error counts. Source failures are isolated and persisted. SQLite schema changes are applied conservatively on startup for existing local databases.

Company-board discovery inspects employer URLs from imported records, recognizes supported ATS URL patterns, validates the board where a public endpoint exists, and stores valid/pending/inaccessible records in `company_boards`. It does not enumerate random identifiers. Manual board registry operations are available under `/api/boards` and `/api/boards/{id}/toggle`.

The default keyword set includes English and German project, product, business/operations, process engineering, innovation, technology, transformation, and change-management titles. All source enablement and optional credentials are in `.env.example`. Missing optional credentials disable that source without stopping startup; Gemini limits do not prevent jobs from being stored as pending.

Official source references: [Arbeitnow API](https://www.arbeitnow.com/api/job-board-api), [Bundesagentur Jobsuche API](https://jobsuche.api.bund.dev/), [Adzuna API](https://developer.adzuna.com/overview), [SmartRecruiters Posting API](https://developers.smartrecruiters.com/docs/endpoints), [Personio XML feed](https://developer.personio.de/docs/retrieving-open-job-positions), [Himalayas API](https://himalayas.app/api), and [Workable public careers/API guidance](https://help.workable.com/hc/en-us/articles/115012771647-Using-the-Workable-API-to-create-a-careers-page). Adzuna, Workable, Recruitee, and Teamtailor require credentials or company-specific authorization where their provider requires it; the app never substitutes a paid API silently.
