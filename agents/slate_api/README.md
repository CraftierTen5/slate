# slate_api

FastAPI adapter over `slate_core`, implementing the routes in `contracts/api-contracts.md`
(`/v1/resume`, `/jobs`, `/tailor`, `/approvals`, `/roadmap`, `/interview/mock`, `/interview/{id}/feedback`)
plus three helpers the flow needs: `POST /v1/drafts/{id}/edit`, `GET /v1/drafts/{id}/export`,
`POST /v1/interview/{id}/answer`. Errors use the contract shape `{"error": {"code", "message"}}`.

Kept apart from `backend/` (the DB and server setup in PR #4). To combine later, mount the router
in `backend/main.py` or call `create_app()` there.

    pip install fastapi httpx pytest
    python -m pytest tests -q          # 14 tests
    uvicorn slate_api.app:app --app-dir agents

Honest limits:
- State (resumes, drafts, approvals, interviews) is in process memory. The approval gate is enforced
  in the service layer behind HTTP, so a direct API call cannot bypass it, but it resets on restart
  and is not yet backed by the database.
- Resume upload takes JSON `{"text": ...}`, not a PDF file.
- The claim check only verifies that skills claimed in the generated draft come from the parsed resume.
  Text a user edits in later is not re-checked.
- No auth (an open question in the contract).
