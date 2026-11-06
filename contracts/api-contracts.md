# Shared API Contracts (DRAFT)

Status: draft proposal for team review. Not approved, not implemented. Stack-neutral on purpose - describes data shapes, not frameworks.

The website and the CLI both talk to the backend through these shapes, so we define them once here. Change a contract only through a PR that updates its consumers.

## Conventions

- JSON bodies, camelCase field names.
- All routes are versioned under `/v1`.
- Errors use one shape everywhere:

```json
{ "error": { "code": "resume_not_found", "message": "No resume with that id." } }
```

- Auth is an open question (see below). Until decided, requests are local-only sample data.

## Endpoints

### 1. Resume

`POST /v1/resume` - upload and parse a resume.

Response:

```json
{
  "resumeId": "res_123",
  "parsed": {
    "name": "A Kumar",
    "skills": ["python", "sql"],
    "education": [{ "degree": "B.Tech", "institute": "IIITM", "year": 2027 }],
    "experience": [{ "title": "Intern", "org": "ExampleCo", "months": 3 }]
  }
}
```

### 2. Job matches

`GET /v1/jobs?query=analyst&location=indore`

```json
{
  "jobs": [{
    "jobId": "job_456",
    "title": "Data Analyst",
    "company": "ExampleCo",
    "location": "Indore",
    "matchScore": 0.82,
    "deadline": "2026-11-30",
    "url": "https://..."
  }]
}
```

`matchScore` is 0-1, computed by the matching agent. Sample listings are fine until a real jobs source is chosen.

### 3. Tailoring

`POST /v1/tailor` with `{ "resumeId": "res_123", "jobId": "job_456" }`

```json
{
  "draftId": "draft_789",
  "tailoredResume": "...",
  "coverNote": "...",
  "status": "draft"
}
```

A tailor result is always a draft. Nothing leaves the system without the approval flow below.

### 4. Roadmap

`POST /v1/roadmap` with `{ "resumeId": "res_123", "targetRole": "Data Analyst" }`

```json
{
  "milestones": [{
    "title": "SQL fundamentals",
    "why": "Gap for target role",
    "resources": ["..."],
    "etaWeeks": 2
  }]
}
```

### 5. Mock interview

`POST /v1/interview/mock` with `{ "targetRole": "Data Analyst", "mode": "text" }` starts a session and returns `{ "sessionId": "int_101" }`.

`GET /v1/interview/{sessionId}/feedback`

```json
{
  "summary": "...",
  "weakAreas": ["system design basics"],
  "transcriptRef": "int_101"
}
```

Interview memory must persist: a later session can reference earlier feedback through `transcriptRef`.

### 6. Approval gate

`POST /v1/approvals` with `{ "draftId": "draft_789", "decision": "approve" }` (or `"reject"`).

Rules:
- Only an approved draft can be used outside the app.
- If a draft is edited after approval, the old approval is invalid. Editing creates a new `draftId` that needs its own approval.
- Approvals are enforced by the backend, never by hiding buttons in a client.

## Open questions

- Auth: how do web and cli identify the user to the backend? (token header is the likely answer, undecided)
- Pagination for `/v1/jobs` once a real source exists.
- File upload format for resumes (PDF only, or DOCX too).
