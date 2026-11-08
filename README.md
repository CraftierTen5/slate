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

## Adaptive mock interview (Gemini)

The mock interview supports resume-aware opening questions, answer evaluation, and one focused follow-up when an answer needs clarification. Feedback includes a 1–5 score, assessment, strengths, improvement points, and areas to revisit. Earlier weak areas are carried into later sessions.

Gemini is optional. Set `GEMINI_API_KEY` in the backend environment and optionally set `GEMINI_MODEL` (defaults to `gemini-3.6-flash`). Install dependencies from `backend/requirements.txt`. Never put the key in browser code or commit a real key. Without a key, or if the provider is unavailable, the deterministic interview question bank and fallback feedback remain available.

The interview UI offers text and voice modes. Voice mode uses browser speech recognition for candidate input and browser speech synthesis for spoken questions; browser support varies, and text input remains available as a fallback.
