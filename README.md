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

## Gemini and privacy

The official `google-genai` SDK is used. Model names are configurable and default to `gemini-2.5-flash-lite` for matching and `gemini-2.5-flash` for tailoring. Availability/free-tier quotas can change by region and account; verify current limits in Google's Gemini API documentation before use. The app never silently switches to a paid provider and stops after `MAX_LLM_CALLS_PER_RUN`. Retries use bounded exponential backoff and structured Pydantic validation. Obtain informed consent before sending resume data to Gemini; free-tier inputs may be used by Google to improve products according to Google's current terms/settings. Keys stay server-side.

## Tests and limitations

```bash
ruff check app tests
pytest
```

This MVP includes models for profiles, jobs, matches, resumes, applications, sources, settings, and discovery runs; public Greenhouse/Lever/Ashby adapters; deduplication; deterministic matching; upload extraction; safe LaTeX escaping; manual application statuses; and a Bootstrap dashboard. Tectonic is optional at runtime: without it, `.tex` remains downloadable and the UI reports that PDF compilation requires installation. Before public exposure, configure `APP_PASSWORD`, HTTPS, stronger session persistence, and a durable database. No private resume, database, API key, or production profile is committed.
