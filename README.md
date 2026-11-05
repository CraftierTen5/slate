# Slate

Placement preparation copilot.

## Structure

- `agents/` - agent logic: resume, job matching, tailoring, roadmap, mock interview, approval gate
- `backend/` - API over the agents, database, approval enforcement
- `web/` - website, responsive for phone browsers
- `cli/` - terminal interface, calls the same backend API
- `contracts/` - shared request/response formats
- `tests/` - integration and safety checks
- `docs/` - setup guide, architecture, demo flow

## Stack (proposed, not locked)

Python + LangGraph agents, FastAPI backend, PostgreSQL. Next.js + TypeScript web. Python Typer CLI. Confirm before building on these.

## Workflow

Initial project setup lands on `main` once. After that, every change is a branch, then a pull request; the repo owner reviews and merges.
