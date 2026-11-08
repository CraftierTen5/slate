"""Facade returning the contract shapes (contracts/api-contracts.md), errors in one shape."""
from . import jobs as J
from .resume import parse_resume, ParseError
from .tailor import build_draft
from .roadmap import build_roadmap
from .approvals import ApprovalStore
from .interview import InterviewStore
from .claims import validate

class SlateError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message

    def to_dict(self):
        return {"error": {"code": self.code, "message": self.message}}

class SlateService:
    def __init__(self, store=None):
        self._resumes = {}
        self._texts = {}
        self.approvals = ApprovalStore()
        self.interviews = InterviewStore()
        self._store = store
        if store is not None:
            st = store.load()
            if st:
                self._resumes, self._texts = st["resumes"], st["texts"]
                self.approvals._drafts, self.approvals._n = st["drafts"], st["draftN"]
                self.interviews._sessions, self.interviews._n = st["sessions"], st["sessionN"]

    def reset_demo(self, confirm: str) -> dict:
        """Demo helper, gated by the API layer: wipe resumes and drafts so the demo can restart.

        Interview sessions belong to the interview feature and are intentionally kept."""
        if confirm != "reset":
            raise SlateError("reset_not_confirmed", 'Send {"confirm": "reset"} to wipe the demo data.')
        self._resumes, self._texts = {}, {}
        self.approvals._drafts, self.approvals._n = {}, 0
        self._persist()
        return {"reset": True}

    def _persist(self):
        if self._store is not None:
            self._store.save({"resumes": self._resumes, "texts": self._texts,
                              "drafts": self.approvals._drafts, "draftN": self.approvals._n,
                              "sessions": self.interviews._sessions, "sessionN": self.interviews._n})

    def _resume(self, rid):
        r = self._resumes.get(rid)
        if r is None:
            raise SlateError("resume_not_found", "No resume with that id.")
        return r

    def _violations(self, resume_id, content) -> list:
        return validate(self._resume(resume_id), self._texts[resume_id],
                        content.get("tailoredResume", ""), content.get("coverNote", ""))

    def _check_draft(self, draft_id):
        d = self.approvals.get(draft_id)
        if d is None:
            raise SlateError("draft_not_found", "No draft with that id.")
        bad = self._violations(d["resumeId"], d["content"])
        if bad:
            raise SlateError("unsupported_claim", "Draft makes claims the resume does not support: " + "; ".join(bad))
        return d

    def _upload_resume(self, text) -> dict:
        try:
            parsed = parse_resume(text)
        except ParseError as e:
            raise SlateError("resume_unreadable", str(e))
        rid = f"res_{len(self._resumes) + 1:03d}"
        self._resumes[rid] = parsed
        self._texts[rid] = text
        return {"resumeId": rid, "parsed": parsed}

    def jobs(self, query="", location="", resume_id=None) -> dict:
        skills = self._resume(resume_id)["skills"] if resume_id else []
        return {"jobs": J.search_jobs(query, location, skills)}

    def _tailor(self, resume_id, job_id) -> dict:
        parsed = self._resume(resume_id)
        job = J.get_job(job_id)
        if job is None:
            raise SlateError("job_not_found", "No job with that id.")
        d = build_draft(parsed, job)
        bad = self._violations(resume_id, d)
        if bad:  # generated drafts must pass the same check as edited ones
            raise SlateError("unsupported_claim", "Generated draft failed claim check: " + "; ".join(bad))
        did = self.approvals.create_draft(resume_id, job_id, {"tailoredResume": d["tailoredResume"], "coverNote": d["coverNote"]})
        return {"draftId": did, "tailoredResume": d["tailoredResume"], "coverNote": d["coverNote"],
                "status": "draft", "claimsChecked": d["claims"], "skillGaps": d["gaps"]}

    def _edit_draft(self, draft_id, **updates) -> dict:
        old = self.approvals.get(draft_id)
        if old is None:
            raise SlateError("draft_not_found", "No draft with that id.")
        bad = self._violations(old["resumeId"], {**old["content"], **updates})
        if bad:  # fail closed: no new draft is created
            raise SlateError("unsupported_claim", "Edit rejected, claims the resume does not support: " + "; ".join(bad))
        try:
            new_id = self.approvals.edit(draft_id, updates)
        except KeyError:
            raise SlateError("draft_not_found", "No draft with that id.")
        return {"draftId": new_id, "status": "draft"}

    def _decide(self, draft_id, decision) -> dict:
        if decision == "approve":
            self._check_draft(draft_id)  # re-validate at approval time
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
            content = self.approvals.export(draft_id)
            self._check_draft(draft_id)  # re-validate at export time
            return content
        except KeyError:
            raise SlateError("draft_not_found", "No draft with that id.")
        except PermissionError:
            raise SlateError("draft_not_approved", "Only an approved draft can be used outside the app.")

    def roadmap(self, resume_id, target_role) -> dict:
        ms = build_roadmap(self._resume(resume_id), target_role or "")
        if not ms:
            raise SlateError("role_unknown", "No sample listings for that role yet.")
        return {"milestones": ms}

    def _start_interview(self, target_role, mode="text") -> dict:
        if mode != "text":
            raise SlateError("mode_unsupported", "Only text mode in the MVP.")
        return self.interviews.start(target_role, self.interviews.past_feedback())

    def _answer_interview(self, session_id, text) -> dict:
        try:
            return self.interviews.answer(session_id, text)
        except KeyError:
            raise SlateError("session_not_found", "No interview session with that id.")

    def _interview_feedback(self, session_id) -> dict:
        try:
            return self.interviews.feedback(session_id)
        except KeyError:
            raise SlateError("session_not_found", "No interview session with that id.")

    def upload_resume(self, *a, **k):
        r = self._upload_resume(*a, **k)
        self._persist()
        return r

    def tailor(self, *a, **k):
        r = self._tailor(*a, **k)
        self._persist()
        return r

    def edit_draft(self, *a, **k):
        r = self._edit_draft(*a, **k)
        self._persist()
        return r

    def decide(self, *a, **k):
        r = self._decide(*a, **k)
        self._persist()
        return r

    def start_interview(self, *a, **k):
        r = self._start_interview(*a, **k)
        self._persist()
        return r

    def answer_interview(self, *a, **k):
        r = self._answer_interview(*a, **k)
        self._persist()
        return r

    def interview_feedback(self, *a, **k):
        r = self._interview_feedback(*a, **k)
        self._persist()
        return r
