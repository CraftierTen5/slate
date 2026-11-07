# Running the MVP demo locally

Needs Python 3.10+. From the repo root:

    python3 -m venv .venv && . .venv/bin/activate
    pip install fastapi uvicorn httpx pytest sqlalchemy python-multipart pypdf
    python -m pytest tests -q                                   # 30 tests at time of writing
    SLATE_STATE_URL=sqlite:///slate_state.db uvicorn slate_api.app:app --app-dir agents --port 8000

Open http://localhost:8000. The page walks the flow: paste resume text or upload a PDF, job matches, tailored draft,
approve, export, roadmap, mock interview. Leave `SLATE_STATE_URL` unset to keep everything in memory.

## Which PR provides what

| PR | Provides |
| --- | --- |
| #5 | `agents/slate_core`: logic (stdlib only) and its tests |
| #6 | `agents/slate_api`: FastAPI `/v1` routes |
| #7 | server-side claim validation (rule based) |
| this PR | snapshot persistence (SQLAlchemy), `web/index.html`, this page |
| #4 and #8 | Akarsh's Postgres docker + base server, and the DATABASE_URL leak fix. Separate app in `backend/`, not required for the demo above |

This branch is stacked on #7, so it contains #5, #6 and #7. Merge in order 5, 6, 7, then this one.

## Persistence, honestly

`SLATE_STATE_URL` takes any SQLAlchemy URL. The whole state is stored as one JSON row and rewritten
after each change. Tested on SQLite (state survives a restart, including approvals and interview
memory). Pointing it at the Postgres from #4 should work but was not run. One process only; not safe
for concurrent writers.

## Limits

No auth. No PDF upload (paste text). Sample jobs only. The claim check is rule based and catches
unsupported skills, inflated years/months, unlisted percentages, GPA values and degrees; it does not
catch paraphrase or invented employers or projects. Interview feedback is a word-count rule.
Nothing is deployed.
