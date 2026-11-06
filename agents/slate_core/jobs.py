from .sample_data import JOBS

def match_score(resume_skills, job_skills) -> float:
    """Share of the job's skills the resume has, 0-1, rounded. Same input, same output."""
    if not job_skills:
        return 0.0
    have = {s.lower() for s in resume_skills}
    return round(sum(1 for s in job_skills if s in have) / len(job_skills), 2)

def search_jobs(query: str = "", location: str = "", resume_skills=None) -> list:
    q, loc = (query or "").lower().strip(), (location or "").lower().strip()
    out = []
    for j in JOBS:
        if q and q not in j["title"].lower() and not any(q in s for s in j["skills"]):
            continue
        if loc and loc != j["location"].lower():
            continue
        out.append({"jobId": j["jobId"], "title": j["title"], "company": j["company"],
                    "location": j["location"], "matchScore": match_score(resume_skills or [], j["skills"]),
                    "deadline": j["deadline"], "url": j["url"]})
    return sorted(out, key=lambda x: (-x["matchScore"], x["jobId"]))

def get_job(job_id: str):
    return next((j for j in JOBS if j["jobId"] == job_id), None)
