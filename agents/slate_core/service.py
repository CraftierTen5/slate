"""Facade returning the contract shapes (contracts/api-contracts.md), errors in one shape."""
from . import jobs as J
from .resume import parse_resume, ParseError
from .tailor import build_draft, check_claims
from .roadmap import build_roadmap
from .approvals import ApprovalStore
from .interview import InterviewStore

class SlateError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message

    def to_dict(self):
        return {"error": {"code": self.code, "message": self.message}}

class SlateService:
    def __init__(self):
        self._resumes = {}
        self.approvals = ApprovalStore()
        self.interviews = InterviewStore()

    def _resume(self, rid):
        r = self._resumes.get(rid)
        if r is None:
            raise SlateError("resume_not_found", "No resume with that id.")
        return r

    def upload_resume(self, text) -> dict:
        try:
            parsed = parse_resume(text)
        except ParseError as e:
            raise SlateError("resume_unreadable", str(e))
        rid = f"res_{len(self._resumes) + 1:03d}"
        self._resumes[rid] = parsed
        return {"resumeId": rid, "parsed": parsed}

    def jobs(self, query="", location="", resume_id=None) -> dict:
        skills = self._resume(resume_id)["skills"] if resume_id else []
        return {"jobs": J.search_jobs(query, location, skills)}

    def tailor(self, resume_id, job_id) -> dict:
        parsed = self._resume(resume_id)
        job = J.get_job(job_id)
        if job is None:
            raise SlateError("job_not_found", "No job with that id.")
        d = build_draft(parsed, job)
        bad = check_claims(parsed, d["claims"])
        if bad:  # should not happen; guard anyway
            raise SlateError("unsupported_claim", f"Draft claims skills not on the resume: {bad}")
        did = self.approvals.create_draft(resume_id, job_id, {"tailoredResume": d["tailoredResume"], "coverNote": d["coverNote"]})
        return {"draftId": did, "tailoredResume": d["tailoredResume"], "coverNote": d["coverNote"],
                "status": "draft", "claimsChecked": d["claims"], "skillGaps": d["gaps"]}

    def edit_draft(self, draft_id, **updates) -> dict:
        try:
            new_id = self.approvals.edit(draft_id, updates)
        except KeyError:
            raise SlateError("draft_not_found", "No draft with that id.")
        return {"draftId": new_id, "status": "draft"}

    def decide(self, draft_id, decision) -> dict:
        try:
            status = self.approvals.decide(draft_id, decision)
        except KeyError:
            raise SlateError("draft_not_found", "No draft with that id.")
        except ValueError:
            raise SlateError("invalid_decision", "decision must be 'approve' or 'reject'.")
        except PermissionError:
            raise SlateError("draft_rejected", "A rejected draft cannot be reused. Create a new draft.")
        return {"draftId": draft_id, "status": status}

    def export_draft(self, draft_id) -> dict:
        try:
            return self.approvals.export(draft_id)
        except KeyError:
            raise SlateError("draft_not_found", "No draft with that id.")
        except PermissionError:
            raise SlateError("draft_not_approved", "Only an approved draft can be used outside the app.")

    def roadmap(self, resume_id, target_role) -> dict:
        ms = build_roadmap(self._resume(resume_id), target_role or "")
        if not ms:
            raise SlateError("role_unknown", "No sample listings for that role yet.")
        return {"milestones": ms}

    def start_interview(self, target_role, mode="text") -> dict:
        if mode != "text":
            raise SlateError("mode_unsupported", "Only text mode in the MVP.")
        return self.interviews.start(target_role, self.interviews.past_feedback())

    def answer_interview(self, session_id, text) -> dict:
        try:
            return self.interviews.answer(session_id, text)
        except KeyError:
            raise SlateError("session_not_found", "No interview session with that id.")

    def interview_feedback(self, session_id) -> dict:
        try:
            return self.interviews.feedback(session_id)
        except KeyError:
            raise SlateError("session_not_found", "No interview session with that id.")
