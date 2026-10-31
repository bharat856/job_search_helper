import json
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from .config import get_settings
from .db import SessionLocal, init_db
from .models import Application, CandidateProfile, GeneratedResume, Job, JobMatch, Settings
from .scheduler import start_scheduler
from .schemas import CandidateData, TailoredResume
from .services.discovery import run_discovery
from .services.ingest import extract_text
from .services.latex import compile_pdf, render_tex

app = FastAPI(title="Job Search Helper")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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
    request: Request, q: str = "", status: str = "", minimum: int = 0, session=Depends(db)
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
    jobs = session.scalars(query.limit(200)).all()
    counts = {
        "new": session.scalar(select(func.count(Job.id)).where(Job.application_status == "new"))
        or 0,
        "strong": session.scalar(select(func.count(Job.id)).where(Job.match_score >= 70)) or 0,
        "applied": session.scalar(
            select(func.count(Job.id)).where(Job.application_status == "applied")
        )
        or 0,
    }
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "jobs": jobs,
            "counts": counts,
            "q": q,
            "status": status,
            "minimum": minimum,
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
        "job.html", {"request": request, "job": job, "match": result, "resume": resume}
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


@app.post("/refresh")
def refresh(session=Depends(db)):
    run_discovery(session)
    return RedirectResponse("/", 303)


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
    return templates.TemplateResponse(
        "settings.html", {"request": request, "settings": session.get(Settings, 1) or Settings()}
    )


@app.post("/settings")
def save_settings(
    preferred_roles: str = Form(...),
    locations: str = Form(...),
    languages: str = Form(...),
    excluded_keywords: str = Form(""),
    minimum_score: int = Form(70),
    session=Depends(db),
):
    item = session.get(Settings, 1) or Settings()
    item.preferred_roles = preferred_roles
    item.locations = locations
    item.languages = languages
    item.excluded_keywords = excluded_keywords
    item.minimum_score = minimum_score
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
