"""HTTP adapter over slate_core, following contracts/api-contracts.md.

Separate from backend/ on purpose (that folder holds the teammate's DB/server setup, PR #4).
To merge later: mount `router` in backend/main.py, or run this app on its own.
Run:  uvicorn slate_api.app:app --app-dir agents
"""
import os, sys
from typing import Optional
from fastapi import APIRouter, FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from slate_core import SlateService, SlateError  # noqa: E402
from slate_core.resume import ParseError, extract_pdf_text  # noqa: E402

STATUS = {"resume_not_found": 404, "job_not_found": 404, "draft_not_found": 404, "session_not_found": 404,
          "resume_unreadable": 422, "invalid_decision": 422, "role_unknown": 404, "mode_unsupported": 422,
          "draft_not_approved": 403, "draft_rejected": 409, "unsupported_claim": 422,
          "demo_reset_disabled": 403, "reset_not_confirmed": 422}
STATUS.setdefault("ai_not_configured", 503)  # appended, so sibling PRs editing the dict do not collide

class ResumeIn(BaseModel):
    text: str  # plain text for now; PDF upload is an open question in the contract

class TailorIn(BaseModel):
    resumeId: str
    jobId: str

class EditIn(BaseModel):
    tailoredResume: Optional[str] = None
    coverNote: Optional[str] = None

class RoadmapIn(BaseModel):
    resumeId: str
    targetRole: str

class MockIn(BaseModel):
    targetRole: str
    mode: str = "text"

class AnswerIn(BaseModel):
    text: str

class ApprovalIn(BaseModel):
    draftId: str
    decision: str

class ResetIn(BaseModel):
    confirm: str = ""

def create_app(service: Optional[SlateService] = None) -> FastAPI:
    svc = service or SlateService()
    r = APIRouter(prefix="/v1")

    @r.post("/resume")
    def resume(b: ResumeIn): return svc.upload_resume(b.text)

    @r.post("/resume/pdf")
    async def resume_pdf(file: UploadFile = File(...)):
        data = await file.read()
        try:
            text = extract_pdf_text(data)
        except ParseError as e:
            raise SlateError("resume_unreadable", str(e))
        return svc.upload_resume(text)

    @r.get("/jobs")
    def jobs(query: str = "", location: str = "", resumeId: Optional[str] = None):
        return svc.jobs(query, location, resumeId)

    @r.post("/tailor")
    def tailor(b: TailorIn): return svc.tailor(b.resumeId, b.jobId)

    @r.post("/tailor/ai")
    def tailor_ai(b: TailorIn):
        # Opt-in AI drafting: off unless the server has a key AND the service supports it.
        fn = getattr(svc, "tailor_ai", None)
        if fn is None or not os.getenv("LLM_API_KEY"):
            raise SlateError("ai_not_configured",
                             "AI tailoring is off on this server. Set LLM_API_KEY to enable it.")

Separate from backend/ on purpose (that folder holds the teammate's DB/server setup, PR #4).
To merge later: mount `router` in backend/main.py, or run this app on its own.
Run:  uvicorn slate_api.app:app --app-dir agents
"""
import os, sys
from typing import Optional
from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from slate_core import SlateService, SlateError  # noqa: E402

STATUS = {"resume_not_found": 404, "job_not_found": 404, "draft_not_found": 404, "session_not_found": 404,
          "resume_unreadable": 422, "invalid_decision": 422, "role_unknown": 404, "mode_unsupported": 422,
          "draft_not_approved": 403, "draft_rejected": 409, "unsupported_claim": 422}
STATUS.setdefault("ai_not_configured", 503)  # appended, so sibling PRs editing the dict do not collide

class ResumeIn(BaseModel):
    text: str  # plain text for now; PDF upload is an open question in the contract

class TailorIn(BaseModel):
    resumeId: str
    jobId: str

class EditIn(BaseModel):
    tailoredResume: Optional[str] = None
    coverNote: Optional[str] = None

class RoadmapIn(BaseModel):
    resumeId: str
    targetRole: str

class MockIn(BaseModel):
    targetRole: str
    mode: str = "text"

class AnswerIn(BaseModel):
    text: str

class ApprovalIn(BaseModel):
    draftId: str
    decision: str

def create_app(service: Optional[SlateService] = None) -> FastAPI:
    svc = service or SlateService()
    r = APIRouter(prefix="/v1")

    @r.post("/resume")
    def resume(b: ResumeIn): return svc.upload_resume(b.text)

    @r.get("/jobs")
    def jobs(query: str = "", location: str = "", resumeId: Optional[str] = None):
        return svc.jobs(query, location, resumeId)

    @r.post("/tailor")
    def tailor(b: TailorIn): return svc.tailor(b.resumeId, b.jobId)

    @r.post("/tailor/ai")
    def tailor_ai(b: TailorIn):
        # Opt-in AI drafting: off unless the server has a key AND the service supports it.
        fn = getattr(svc, "tailor_ai", None)
        if fn is None or not os.getenv("LLM_API_KEY"):
            raise SlateError("ai_not_configured",
                             "AI tailoring is off on this server. Set LLM_API_KEY to enable it.")
        return fn(b.resumeId, b.jobId)

    @r.post("/drafts/{draft_id}/edit")
    def edit(draft_id: str, b: EditIn):
        return svc.edit_draft(draft_id, **b.model_dump(exclude_none=True))

    @r.get("/drafts/{draft_id}/export")
    def export(draft_id: str): return svc.export_draft(draft_id)

    @r.post("/roadmap")
    def roadmap(b: RoadmapIn): return svc.roadmap(b.resumeId, b.targetRole)

    @r.post("/interview/mock")
    def mock(b: MockIn): return svc.start_interview(b.targetRole, b.mode)

    @r.post("/interview/{sid}/answer")
    def answer(sid: str, b: AnswerIn): return svc.answer_interview(sid, b.text)

    @r.get("/interview/{sid}/feedback")
    def feedback(sid: str): return svc.interview_feedback(sid)

    @r.post("/approvals")
    def approvals(b: ApprovalIn): return svc.decide(b.draftId, b.decision)

    app = FastAPI(title="Slate API (core adapter)")
    app.include_router(r)

    @app.exception_handler(SlateError)
    async def _slate(_: Request, e: SlateError):
        return JSONResponse(e.to_dict(), status_code=STATUS.get(e.code, 400))

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, e: RequestValidationError):
        return JSONResponse({"error": {"code": "bad_request", "message": "Request body or query is invalid."}}, status_code=422)

    web = os.path.join(os.path.dirname(__file__), "..", "..", "web", "index.html")
    web_ai = os.path.join(os.path.dirname(__file__), "..", "..", "web", "ai.html")

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(web) if os.path.exists(web) else JSONResponse({"message": "Slate API"})

    @app.get("/ai", include_in_schema=False)
    def ai_page():
        return FileResponse(web_ai) if os.path.exists(web_ai) else JSONResponse({"message": "AI demo page not found"})

    return app

def _default_service():
    from slate_core.ai_service import AISlateService  # strict superset of SlateService; AI route stays off without a key
    url = os.getenv("SLATE_STATE_URL")  # e.g. sqlite:///slate_state.db or the Postgres DATABASE_URL; unset = in memory
    if not url:
        return AISlateService()
    from slate_core.persistence import SqlSnapshot
    return AISlateService(SqlSnapshot(url))

app = create_app(_default_service())
