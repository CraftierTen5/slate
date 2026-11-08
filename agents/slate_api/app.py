"""HTTP adapter over slate_core, following contracts/api-contracts.md.

Separate from backend/ on purpose (that folder holds the teammate's DB/server setup, PR #4).
To merge later: mount `router` in backend/main.py, or run this app on its own.

Two constructions share ONE route table (no drift between them):
- create_authenticated_app(auth, user_store): the app uvicorn serves. Every /v1
  data call needs a bearer token; the verified user id scopes a fresh per-user
  service per request, so no state is shared between users or requests.
- create_app(service): test fixture mode, single tenant, no auth. Used by the
  unit tests; never wired to the module-level served app.

Run (local dev):  SLATE_DEV_AUTH=1 SLATE_STATE_URL=sqlite:///slate_state.db \
                    uvicorn slate_api.app:app --app-dir agents
Run (Google):     GOOGLE_CLIENT_ID=... SLATE_STATE_URL=<postgres url with TLS> ...
"""
import os, sys
from contextlib import nullcontext
from typing import Optional
from fastapi import APIRouter, FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from slate_core import SlateService, SlateError  # noqa: E402
from slate_core.resume import ParseError, extract_pdf_text  # noqa: E402
from slate_core.auth import AuthError  # noqa: E402

STATUS = {"resume_not_found": 404, "job_not_found": 404, "draft_not_found": 404, "session_not_found": 404,
          "resume_unreadable": 422, "invalid_decision": 422, "role_unknown": 404, "mode_unsupported": 422,
          "draft_not_approved": 403, "draft_rejected": 409, "unsupported_claim": 422,
          "demo_reset_disabled": 403, "reset_not_confirmed": 422}
STATUS.setdefault("ai_not_configured", 503)  # appended, so sibling PRs editing the dict do not collide
STATUS.setdefault("unauthenticated", 401)
STATUS.setdefault("invalid_token", 401)
STATUS.setdefault("auth_not_configured", 503)

class ResumeIn(BaseModel):
    text: str = Field(max_length=200_000)  # plain text for now; PDF upload is an open question in the contract

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

def _mount(r: APIRouter, get_svc):
    """The one route table. get_svc(request) -> SlateService decides whose data
    the call touches; the authenticated app derives it from the bearer token."""

    @r.post("/resume")
    def resume(request: Request, b: ResumeIn):
        with get_svc(request) as svc: return svc.upload_resume(b.text)

    @r.post("/resume/pdf")
    async def resume_pdf(request: Request, file: UploadFile = File(...)):
        with get_svc(request) as svc:  # authenticate BEFORE touching the upload
            data = await file.read()
            if len(data) > 5_000_000:
                raise SlateError("resume_unreadable", "PDF is too large (5 MB max).")
            try:
                text = extract_pdf_text(data)
            except ParseError as e:
                raise SlateError("resume_unreadable", str(e))
            return svc.upload_resume(text)

    @r.get("/jobs")
    def jobs(request: Request, query: str = "", location: str = "", resumeId: Optional[str] = None):
        with get_svc(request) as svc: return svc.jobs(query, location, resumeId)

    @r.post("/tailor")
    def tailor(request: Request, b: TailorIn):
        with get_svc(request) as svc: return svc.tailor(b.resumeId, b.jobId)

    @r.post("/tailor/ai")
    def tailor_ai(request: Request, b: TailorIn):
        # Opt-in AI drafting: off unless the server has a key AND the service supports it.
        with get_svc(request) as svc:  # authenticate first
            fn = getattr(svc, "tailor_ai", None)
            if fn is None or not os.getenv("LLM_API_KEY"):
                raise SlateError("ai_not_configured",
                                 "AI tailoring is off on this server. Set LLM_API_KEY to enable it.")
            return fn(b.resumeId, b.jobId)

    @r.post("/drafts/{draft_id}/edit")
    def edit(request: Request, draft_id: str, b: EditIn):
        with get_svc(request) as svc: return svc.edit_draft(draft_id, **b.model_dump(exclude_none=True))

    @r.get("/drafts/{draft_id}/export")
    def export(request: Request, draft_id: str):
        with get_svc(request) as svc: return svc.export_draft(draft_id)

    @r.post("/roadmap")
    def roadmap(request: Request, b: RoadmapIn):
        with get_svc(request) as svc: return svc.roadmap(b.resumeId, b.targetRole)

    @r.post("/interview/mock")
    def mock(request: Request, b: MockIn):
        with get_svc(request) as svc: return svc.start_interview(b.targetRole, b.mode)

    @r.post("/interview/{sid}/answer")
    def answer(request: Request, sid: str, b: AnswerIn):
        with get_svc(request) as svc: return svc.answer_interview(sid, b.text)

    @r.get("/interview/{sid}/feedback")
    def feedback(request: Request, sid: str):
        with get_svc(request) as svc: return svc.interview_feedback(sid)

    @r.post("/approvals")
    def approvals(request: Request, b: ApprovalIn):
        with get_svc(request) as svc: return svc.decide(b.draftId, b.decision)

    @r.post("/demo/reset")
    def demo_reset(request: Request, b: ResetIn):
        # Off unless the local demo server opts in: SLATE_DEMO_RESET=1 uvicorn ...
        # In the authenticated app this wipes ONLY the caller's own data.
        if os.getenv("SLATE_DEMO_RESET") != "1":
            raise SlateError("demo_reset_disabled",
                             "Demo reset is off. Start the local demo with SLATE_DEMO_RESET=1 to enable it.")
        with get_svc(request) as svc: return svc.reset_demo(b.confirm)

def _shell(r: APIRouter) -> FastAPI:
    app = FastAPI(title="Slate API (core adapter)")
    app.include_router(r)

    @app.exception_handler(SlateError)
    async def _slate(_: Request, e: SlateError):
        return JSONResponse(e.to_dict(), status_code=STATUS.get(e.code, 400))

    @app.exception_handler(AuthError)
    async def _auth(_: Request, e: AuthError):
        return JSONResponse({"error": {"code": e.code, "message": e.message}},
                            status_code=STATUS.get(e.code, 401))

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

def create_app(service: Optional[SlateService] = None) -> FastAPI:
    """Test-fixture mode: single tenant, no auth. The served app never uses this."""
    svc = service or SlateService()
    r = APIRouter(prefix="/v1")
    _mount(r, lambda request: nullcontext(svc))
    return _shell(r)

def create_authenticated_app(auth, user_store, llm_client=None) -> FastAPI:
    """The production construction: bearer token -> verified user -> that user's
    service, built fresh per request from the per-user store. A user id is never
    read from the request; demo reset wipes only the caller's own data."""
    from contextlib import contextmanager
    from slate_core.ai_service import AISlateService
    from slate_core.user_store import UserSnapshot, locked

    @contextmanager
    def get_svc(request: Request):
        if auth is None:
            raise SlateError("auth_not_configured",
                             "Sign-in is not configured on this server. Set GOOGLE_CLIENT_ID "
                             "(or SUPABASE_URL + SUPABASE_ANON_KEY), or SLATE_DEV_AUTH=1 for local dev.")
        user = auth.authenticate(request.headers.get("authorization"))
        with locked(user.id):  # serializes a user's own concurrent requests; see user_store.locked
            yield AISlateService(UserSnapshot(user_store, user.id), llm_client=llm_client)

    r = APIRouter(prefix="/v1")

    @r.get("/config")
    def config():
        """What the login UI needs. Client ids / anon keys are public by design;
        this endpoint exposes no user data and needs no token."""
        gid = os.getenv("GOOGLE_CLIENT_ID")
        surl, skey = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY")
        if gid:
            return {"mode": "google", "googleClientId": gid}
        if surl and skey:
            return {"mode": "supabase", "supabaseUrl": surl, "supabaseAnonKey": skey}
        if os.getenv("SLATE_DEV_AUTH") == "1":
            return {"mode": "dev"}
        return {"mode": "unconfigured"}

    _mount(r, get_svc)
    return _shell(r)

def _build_auth():
    """Exactly one provider. A real provider always wins over the dev flag, so a
    misconfigured deployment cannot silently fall into dev sign-in."""
    from slate_core.auth import DevAuth, GoogleAuth, SupabaseAuth
    gid = os.getenv("GOOGLE_CLIENT_ID")
    surl, skey = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY")
    if gid:
        return GoogleAuth(gid)
    if surl and skey:
        return SupabaseAuth(surl, skey)
    if os.getenv("SLATE_DEV_AUTH") == "1":
        return DevAuth()
    return None  # app still imports/serves pages; /v1 data calls answer 503

def _build_store():
    from slate_core.user_store import MemUserStore, SqlUserStore
    url = os.getenv("SLATE_STATE_URL")  # postgres (TLS) in production; sqlite locally; unset = ephemeral
    return SqlUserStore(url) if url else MemUserStore()

app = create_authenticated_app(_build_auth(), _build_store())
