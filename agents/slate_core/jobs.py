from .sample_data import JOBS

def _norm(skill):
    return str(skill).strip().lower()

def skill_breakdown(resume_skills, job_skills):
    """Split the job's required skills into (matched, missing) against the resume.

    Comparison ignores case and surrounding whitespace on both sides. A skill the
    listing repeats counts once; blanks are ignored. Both lists keep the job's own
    wording and first-seen order. Same input, same output.
    """
    if isinstance(resume_skills, str):
        resume_skills = [resume_skills]
    have = {_norm(s) for s in (resume_skills or []) if _norm(s)}
    matched, missing, seen = [], [], set()
    for s in job_skills or []:
        key = _norm(s)
        if not key or key in seen:
            continue
        seen.add(key)
        (matched if key in have else missing).append(s.strip() if isinstance(s, str) else s)
    return matched, missing

def match_score(resume_skills, job_skills) -> float:
    """Share of the job's distinct required skills the resume has, 0-1, rounded.
    Computed from skill_breakdown so score and explanation always agree."""
    matched, missing = skill_breakdown(resume_skills, job_skills)
    total = len(matched) + len(missing)
    return round(len(matched) / total, 2) if total else 0.0

def match_reason(matched, missing) -> str:
    """One plain sentence explaining the score from the skill breakdown."""
    total = len(matched) + len(missing)
    if total == 0:
        return "This listing names no required skills, so there is nothing to match against."
    noun = "skill" if total == 1 else "skills"
    if not matched:
        return f"Matches none of the {total} required {noun}. Missing: {', '.join(missing)}."
    reason = f"Matches {len(matched)} of {total} required {noun}: {', '.join(matched)}."
    if missing:
        reason += f" Missing: {', '.join(missing)}."
    return reason

def search_jobs(query: str = "", location: str = "", resume_skills=None) -> list:
    q, loc = (query or "").lower().strip(), (location or "").lower().strip()
    out = []
    for j in JOBS:
        if q and q not in j["title"].lower() and not any(q in _norm(s) for s in j["skills"]):
            continue
        if loc and loc != j["location"].lower():
            continue
        matched, missing = skill_breakdown(resume_skills, j["skills"])
        out.append({"jobId": j["jobId"], "title": j["title"], "company": j["company"],
                    "location": j["location"], "matchScore": match_score(resume_skills or [], j["skills"]),
                    "matchedSkills": matched, "missingSkills": missing,
                    "reason": match_reason(matched, missing),
                    "deadline": j["deadline"], "url": j["url"]})
    return sorted(out, key=lambda x: (-x["matchScore"], x["jobId"]))

def get_job(job_id: str):
    return next((j for j in JOBS if j["jobId"] == job_id), None)
