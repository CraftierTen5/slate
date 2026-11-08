"""Opt-in AI tailoring on top of SlateService. Off by default.

The deterministic tailor path stays the default everywhere. This subclass adds
one method, tailor_ai, which asks an LLM (Groq by default) for a draft and then
keeps every safeguard the deterministic path has, plus one more:

- the draft enters the SAME approval store in "draft" status; approval and
  export re-validate through the normal _decide / export_draft path
- flagged skills and rule violations travel with the response so the review
  UI can show them before a human decides
- requiresApproval is always true; nothing auto-approves

Nothing here runs without LLM_API_KEY set on the server. The API layer also
refuses the route when the key is missing, so the feature is doubly off by
default.
"""
from . import jobs as J
from .llm import GroqLLM, llm_tailored_draft
from .service import SlateError, SlateService


class AISlateService(SlateService):
    def __init__(self, store=None, llm_client=None):
        super().__init__(store)
        self._llm_client = llm_client  # tests inject MockLLM here

    def tailor_ai(self, resume_id, job_id, client=None) -> dict:
        parsed = self._resume(resume_id)
        job = J.get_job(job_id)
        if job is None:
            raise SlateError("job_not_found", "No job with that id.")
        client = client or self._llm_client or GroqLLM()
        d = llm_tailored_draft(parsed, job, client, resume_text=self._texts[resume_id])
        did = self.approvals.create_draft(
            resume_id, job_id,
            {"tailoredResume": d["tailoredResume"], "coverNote": d["coverNote"]})
        self._persist()
        return {"draftId": did, "tailoredResume": d["tailoredResume"],
                "coverNote": d["coverNote"], "status": "draft",
                "aiGenerated": True,
                "claimsChecked": d["claims"], "skillGaps": d["gaps"],
                "flaggedClaims": d["flaggedClaims"], "violations": d["violations"],
                "requiresApproval": True}
