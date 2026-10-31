from pydantic import BaseModel, Field


class GeminiTestRequest(BaseModel):
    model: str = Field(min_length=1, max_length=120)


class CandidateData(BaseModel):
    personal_details: dict = Field(default_factory=dict)
    education: list[dict] = Field(default_factory=list)
    employment_history: list[dict] = Field(default_factory=list)
    verified_skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    original_bullets: list[dict] = Field(default_factory=list)


class MatchingSkill(BaseModel):
    skill: str
    evidence: str


class CriterionScore(BaseModel):
    criterion: str
    score: float = Field(ge=0, le=100)


class MatchResult(BaseModel):
    matching_skills: list[MatchingSkill] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
    relevant_experience: list[str] = Field(default_factory=list)
    hard_requirement_conflicts: list[str] = Field(default_factory=list)
    explanation: str = ""
    criterion_scores: list[CriterionScore] = Field(default_factory=list)
    overall_score: float = Field(ge=0, le=100)
    recommendation: str = "review"


class TailoredResume(BaseModel):
    tailored_summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    verification_flags: list[str] = Field(default_factory=list)
