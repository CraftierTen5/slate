"""Tailoring with a claim check: every skill the draft claims must come from the parsed resume."""

def build_draft(parsed: dict, job: dict) -> dict:
    have = set(parsed["skills"])
    matched = [s for s in job["skills"] if s in have]
    missing = [s for s in job["skills"] if s not in have]
    name = parsed["name"]
    resume = [f"{name}", f"Target role: {job['title']} at {job['company']}", "",
              "Relevant skills: " + (", ".join(matched) if matched else "none listed yet")]
    for e in parsed["experience"]:
        resume.append(f"Experience: {e['title']}, {e['org']}")
    for e in parsed["education"]:
        resume.append(f"Education: {e['degree']}" + (f" ({e['year']})" if e["year"] else ""))
    note = (f"Hello {job['company']} team, I am applying for the {job['title']} role. "
            + (f"My background includes {', '.join(matched)}. " if matched else "")
            + "I would be glad to share more about my projects.")
    return {"tailoredResume": "\n".join(resume), "coverNote": note, "claims": matched, "gaps": missing}

def check_claims(parsed: dict, claims: list) -> list:
    """Return claims that are NOT backed by the resume."""
    have = set(parsed["skills"])
    return [c for c in claims if c not in have]
