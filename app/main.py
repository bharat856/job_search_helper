import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from .config import get_settings
from .db import SessionLocal, init_db
from .models import Application, CandidateProfile, GeneratedResume, Job, JobMatch, Settings
from .scheduler import start_scheduler
from .schemas import CandidateData, GeminiTestRequest, TailoredResume
from .services.discovery import run_discovery
from .services.gemini import GeminiConnectionError, GeminiService
from .services.ingest import extract_text
from .services.job_format import format_job_description
from .services.latex import compile_pdf, render_tex
from .sources.email_alerts import test_connection

app = FastAPI(title="Job Search Helper")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
discovery_lock = threading.Lock()


@app.on_event("startup")
def startup():
    init_db()
    app.state.scheduler = start_scheduler()


def db():
    with SessionLocal() as session:
        yield session


def guard(request: Request):
    s = get_settings()
    if s.local_only and s.app_password and request.cookies.get("session") != secrets.token_hex(16):
        # Local-only is the default; password auth is opt-in and uses a simple session cookie.
        if request.url.path not in ("/login",):
            raise HTTPException(401, "Authentication required")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return HTMLResponse(
        '<form method="post"><input name="password" type="password"><button>Log in</button></form>'
    )


@app.post("/login")
def login(password: str = Form(...)):
    if not get_settings().app_password or password != get_settings().app_password:
        raise HTTPException(401, "Invalid password")
    response = RedirectResponse("/", 303)
    response.set_cookie("session", secrets.token_hex(16), httponly=True)
    return response


@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    q: str = "",
    status: str = "",
    minimum: int = 0,
    city: str = "",
    source: str = "",
    days: int = 0,
    session=Depends(db),
):
    query = select(Job).order_by(Job.match_score.desc().nullslast(), Job.last_seen.desc())
    if q:
        query = query.where(
            (Job.title.ilike(f"%{q}%"))
            | (Job.company.ilike(f"%{q}%"))
            | (Job.description.ilike(f"%{q}%"))
        )
    if status:
        query = query.where(Job.application_status == status)
    if minimum:
        query = query.where(Job.match_score >= minimum)
    if city:
        query = query.where(Job.city.ilike(f"%{city}%"))
    if source:
        query = query.where(Job.source == source)
    if days:
        from datetime import timedelta

        query = query.where(Job.first_seen >= datetime.now(timezone.utc) - timedelta(days=days))
    jobs = session.scalars(query.limit(200)).all()
    counts = {
        "new": session.scalar(select(func.count(Job.id)).where(Job.application_status == "new"))
        or 0,
        "strong": session.scalar(select(func.count(Job.id)).where(Job.match_score >= 70)) or 0,
        "applied": session.scalar(
            select(func.count(Job.id)).where(Job.application_status == "applied")
        )
        or 0,
        "applied_today": session.scalar(
            select(func.count(Application.id)).where(
                Application.applied_date == datetime.now(timezone.utc).date()
            )
        )
        or 0,
        "rejected": session.scalar(
            select(func.count(Job.id)).where(Job.application_status == "rejected")
        )
        or 0,
    }
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "jobs": jobs,
            "counts": counts,
            "q": q,
            "status": status,
            "minimum": minimum,
            "city": city,
            "source": source,
            "days": days,
        },
    )


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int, session=Depends(db)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404)
    match = session.scalar(select(JobMatch).where(JobMatch.job_id == job_id))
    result = json.loads(match.result_json) if match else {}
    resume = session.scalar(
        select(GeneratedResume)
        .where(GeneratedResume.job_id == job_id)
        .order_by(GeneratedResume.version.desc())
    )
    return templates.TemplateResponse(
        request=request,
        name="job.html",
        context={
            "request": request,
            "job": job,
            "match": result,
            "resume": resume,
            "description_sections": format_job_description(job.description),
            "encouragement": encouragement_for(result, job),
        },
    )


def encouragement_for(match: dict, job: Job) -> str:
    score = float(match.get("overall_score", job.match_score or 0) or 0)
    skills = len(match.get("matching_skills", []) or [])
    if score >= 70:
        return (
            f"You have a promising starting point here: your profile lines up with {skills} "
            f"relevant skill{'s' if skills != 1 else ''}. Do not worry about being perfect—"
            "review the evidence, tailor honestly, and take the next small step."
        )
    if score:
        return (
            "This score is only a heuristic, not a judgment of your potential. Do not worry "
            "if every requirement is not a match; look at the transferable experience and "
            "decide whether this role is worth exploring."
        )
    return (
        "Do not worry if this job is not scored yet. A missing score is a signal to review "
        "the description, not a statement about your ability."
    )


@app.post("/jobs/{job_id}/status")
def update_status(job_id: int, status: str = Form(...), notes: str = Form(""), session=Depends(db)):
    job = session.get(Job, job_id)
    if not job or status not in {"new", "interested", "rejected", "applied", "interview", "offer"}:
        raise HTTPException(400)
    job.application_status = status
    application = session.scalar(
        select(Application).where(Application.job_id == job_id)
    ) or Application(job_id=job_id)
    application.status = status
    application.notes = notes
    if status == "applied" and application.applied_date is None:
        application.applied_date = datetime.now(timezone.utc).date()
    session.add(application)
    session.commit()
    return RedirectResponse(f"/jobs/{job_id}", 303)


@app.post("/jobs/{job_id}/generate")
def generate_resume(job_id: int, session=Depends(db)):
    job = session.get(Job, job_id)
    profile = session.scalar(
        select(CandidateProfile)
        .where(CandidateProfile.approved)
        .order_by(CandidateProfile.version.desc())
    )
    if not job or not profile:
        raise HTTPException(400, "Approve a candidate profile first")
    data = CandidateData.model_validate(json.loads(profile.data_json))
    tailored = TailoredResume(
        tailored_summary="Tailored summary based on verified profile facts",
        skills=data.verified_skills,
        experience=data.employment_history,
        projects=data.projects,
    )
    app_settings = session.get(Settings, 1) or Settings()
    if get_settings().gemini_api_key:
        prompt = (
            "Create a factual tailored resume structure from the verified candidate profile "
            "and job. "
            "Use only supplied facts; do not invent employers, dates, metrics, skills, "
            "or achievements. "
            f"JOB:\n{job.description[:12000]}\nPROFILE:\n{profile.data_json[:12000]}"
        )
        try:
            tailored = GeminiService().structured(
                prompt,
                TailoredResume,
                model=app_settings.gemini_tailor_model or get_settings().gemini_tailor_model,
            )
        except RuntimeError:
            pass
    tex = render_tex({**data.model_dump(), **tailored.model_dump()})
    output = Path("storage/generated") / f"job-{job_id}-v1"
    pdf = None
    try:
        pdf = str(compile_pdf(tex, output))
    except RuntimeError:
        pass
    resume = GeneratedResume(
        job_id=job_id,
        version=1,
        content_json=tailored.model_dump_json(),
        tex_content=tex,
        pdf_path=pdf,
        verified=not tailored.verification_flags,
    )
    session.add(resume)
    session.commit()
    return RedirectResponse(f"/jobs/{job_id}", 303)


def _discovery_worker(run_id: int):
    with SessionLocal() as session:
        from .models import DiscoveryRun

        run = session.get(DiscoveryRun, run_id)
        profile = session.scalar(
            select(CandidateProfile)
            .where(CandidateProfile.approved)
            .order_by(CandidateProfile.version.desc())
        )
        run_discovery(session, profile=profile, run=run)
    discovery_lock.release()


@app.post("/refresh")
def refresh():
    if not discovery_lock.acquire(blocking=False):
        raise HTTPException(409, "A discovery run is already in progress")
    with SessionLocal() as session:
        run = __import__("app.models", fromlist=["DiscoveryRun"]).DiscoveryRun()
        session.add(run)
        session.commit()
        run_id = run.id
    thread = threading.Thread(target=_discovery_worker, args=(run_id,), daemon=True)
    thread.start()
    return {"run_id": run_id, "status": "running"}


@app.get("/api/discovery/status/{run_id}")
def discovery_status(run_id: int, session=Depends(db)):
    from .models import DiscoveryRun, DiscoverySourceError

    run = session.get(DiscoveryRun, run_id)
    if not run:
        raise HTTPException(404)
    errors = session.scalars(
        select(DiscoverySourceError).where(DiscoverySourceError.run_id == run_id)
    ).all()
    return {
        "id": run.id,
        "status": run.status,
        "current_source": run.current_source,
        "fetched": run.fetched_count,
        "new": run.new_count,
        "duplicates": run.duplicate_count,
        "filtered": run.filtered_count,
        "matched": run.matched_count,
        "pending": run.pending_count,
        "errors": [{"source": x.source, "message": x.message} for x in errors],
    }


@app.get("/resumes/{resume_id}/tex")
def download_tex(resume_id: int, session=Depends(db)):
    resume = session.get(GeneratedResume, resume_id)
    if not resume:
        raise HTTPException(404)
    path = Path("storage/generated") / f"resume-{resume_id}.tex"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(resume.tex_content)
    return FileResponse(path, media_type="application/x-tex", filename="tailored-resume.tex")


@app.get("/resumes/{resume_id}/pdf")
def download_pdf(resume_id: int, session=Depends(db)):
    resume = session.get(GeneratedResume, resume_id)
    if not resume or not resume.pdf_path or not Path(resume.pdf_path).is_file():
        raise HTTPException(404, "PDF not compiled; install Tectonic")
    return FileResponse(
        resume.pdf_path, media_type="application/pdf", filename="tailored-resume.pdf"
    )


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, session=Depends(db)):
    app_settings = session.get(Settings, 1) or Settings()
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "request": request,
            "settings": app_settings,
            "gemini_defaults": get_settings(),
            "boards": session.query(
                __import__("app.models", fromlist=["CompanyBoard"]).CompanyBoard
            ).all(),
        },
    )


@app.post("/api/gemini/test")
def gemini_test(payload: GeminiTestRequest = Body(...)):
    try:
        return GeminiService().test_connection(payload.model)
    except GeminiConnectionError as exc:
        status = {"authentication": 401, "model_not_found": 404, "quota": 429}.get(exc.code, 502)
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@app.post("/settings/imap-test")
def imap_test():
    settings = get_settings()
    ok, message = test_connection(
        settings.imap_host, settings.imap_username, settings.imap_password, settings.imap_port
    )
    return {"ok": ok, "message": message}


@app.post("/api/boards")
def add_board(
    company: str = Form(...),
    provider: str = Form(...),
    identifier: str = Form(...),
    session=Depends(db),
):
    from .services.board_registry import register_from_url

    board = register_from_url(session, f"https://{identifier}", company, "manual")
    if not board:
        from .models import CompanyBoard

        board = CompanyBoard(
            company=company,
            provider=provider,
            identifier=identifier,
            discovery_source="manual",
            validation_status="pending",
        )
        session.add(board)
    session.commit()
    return {"id": board.id, "validation_status": board.validation_status}


@app.post("/api/boards/{board_id}/toggle")
def toggle_board(board_id: int, enabled: bool = Form(...), session=Depends(db)):
    from .models import CompanyBoard

    board = session.get(CompanyBoard, board_id)
    if not board:
        raise HTTPException(404)
    board.enabled = enabled
    session.commit()
    return {"id": board.id, "enabled": board.enabled}


@app.post("/settings")
def save_settings(
    preferred_roles: str = Form(...),
    locations: str = Form(...),
    languages: str = Form(...),
    excluded_keywords: str = Form(""),
    minimum_score: int = Form(70),
    gemini_match_model: str = Form("gemini-3.5-flash-lite"),
    gemini_tailor_model: str = Form("gemini-3.5-flash-lite"),
    session=Depends(db),
):
    item = session.get(Settings, 1) or Settings()
    item.preferred_roles = preferred_roles
    item.locations = locations
    item.languages = languages
    item.excluded_keywords = excluded_keywords
    item.minimum_score = minimum_score
    item.gemini_match_model = gemini_match_model.strip() or get_settings().gemini_model
    item.gemini_tailor_model = gemini_tailor_model.strip() or get_settings().gemini_tailor_model
    session.add(item)
    session.commit()
    return RedirectResponse("/settings", 303)


@app.post("/profile/upload")
async def upload_profile(file: UploadFile = File(...), session=Depends(db)):
    if Path(file.filename or "").suffix.lower() not in {".pdf", ".docx", ".tex"}:
        raise HTTPException(400, "PDF, DOCX, or TEX only")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large")
    path = Path("storage/uploads") / (Path(file.filename).name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    extract_text(path)
    profile = CandidateProfile(
        version=(session.scalar(select(func.max(CandidateProfile.version))) or 0) + 1,
        source_filename=path.name,
        data_json=CandidateData().model_dump_json(),
    )
    # Raw text remains local for review; no external call is made automatically.
    session.add(profile)
    session.commit()
    return RedirectResponse("/settings", 303)


@app.post("/profile/{profile_id}/approve")
def approve_profile(profile_id: int, data_json: str = Form(...), session=Depends(db)):
    profile = session.get(CandidateProfile, profile_id)
    if not profile:
        raise HTTPException(404)
    profile.data_json = CandidateData.model_validate_json(data_json).model_dump_json()
    profile.approved = True
    session.commit()
    return RedirectResponse("/settings", 303)


@app.post("/resumes/{resume_id}/edit")
def edit_resume(resume_id: int, tex_content: str = Form(...), session=Depends(db)):
    resume = session.get(GeneratedResume, resume_id)
    if not resume:
        raise HTTPException(404)
    resume.tex_content = tex_content
    resume.pdf_path = None
    resume.verified = False
    session.commit()
    return RedirectResponse(f"/jobs/{resume.job_id}", 303)
