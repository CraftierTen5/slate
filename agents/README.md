# agents

Agent logic lives here: resume, job matching, tailoring, roadmap, mock interview, approval gate. Proposed: Python + LangGraph. One module per agent; prompts, tools, and workflows kept separate. Structure only - no code yet.

### Resume extraction limits

Skill extraction is independent of the five sample job requirements. It combines
bounded literal skill/alias matches with concise, explicitly labeled skills lists.
Unknown listed phrases are kept as candidates, not silently discarded because a
job fixture does not use them. `skillEvidence` records the phrase and extraction
path; `parseWarnings` makes review necessary. This is not a semantic proficiency
assessment. Supported section labels include a few non-English variants; this
is not general multilingual resume understanding or translation.

Narrative-only unknown skills, scanned-image PDF OCR, robust multi-column order,
general school/degree normalization and non-tech work-history extraction are not
solved. Explicit parenthesized `(Tip: ...)` template instructions are excluded
from resume parsing, but never from draft claim checking. The claim checker still
cannot validate arbitrary open-vocabulary claims or paraphrases semantically.

Job scores remain exact skill overlap against five analyst/tech sample fixtures,
not resume quality, employability, or a career recommendation. No new retail jobs
were invented to make a score look better. Data Analyst remains a fixed demo
roadmap, not an inferred target role. Existing saved parses are immutable snapshots:
re-upload/reparse to use updated extraction, without silently changing old drafts.

Negative, aspirational and explicitly instructional English contexts are flagged in
`uncertainSkills`, not counted as skill evidence without review. A separate
positive mention can support the same candidate. Context rules are conservative,
not general semantic negation detection in every language. This filter applies
only when parsing a resume; draft claim checks still detect all known mentions.

### Review/correct skill candidates

The classic page lets a signed-in user edit a short skill list and explicitly
confirm it. Saving calls `POST /v1/resume/{rid}/skills/review` with `skills` and
strict boolean `confirm:true`. This creates a new resume ID. Source phrase
records remain distinct from user-provided additions; none is independently
verified competence. Additions are explicit self-reported statements in a labeled
source addendum for this new version, never silently attributed to the PDF.
Original text and prior parsed versions remain intact. Existing approved drafts
bound to the corrected parent or its ancestor versions are reset to draft; rejected drafts and
other users/resume IDs are untouched. New drafts require their own approval.
The same claim and AI evidence checks still run. A self-reported skill does not
establish employment, qualifications, durations, metrics or professional ability.

Literal education/work-history section previews now distinguish recognized
source sections needing review from unrecognized sections. Empty structured
arrays do not mean the person has no qualifications or experience. These previews
are bounded excerpts, not complete document reconstruction; general multi-column
and qualification normalization remain unfinished. Stored review snapshots and
metadata survive the existing per-user persistence path, subject to its current
single-process and privacy limitations. No public sharing is performed.

### Reopen saved versions

Classic UI can load the signed-in user's newest100resume summaries and reopen
a selected immutable version after reload or restart. Per-user DB state must be
configured for restart durability; in-memory mode remains ephemeral. Reopening
shows original uploaded text separately from reviewed self-reported skill data,
not a fabricated edited PDF. It does not reparse or approve drafts. Source-bound
job/draft/roadmap results are cleared when switching versions, and stale delayed
job/draft responses are discarded. This is not full draft/history/account-data
management or pagination; retention/delete/export policy remains future work.

### Browser session-state checks

Classic and AI pages clear private source/draft/approval display when sign-in
expires or a new sign-in is accepted. They discard late successes, HTTP errors,
401s and network errors from an earlier token/source epoch. Reauthentication
never automatically replays a mutation. An already-submitted server operation
may still complete for the original account; UI cancellation is not rollback.
This does not add token revocation, server sessions or protect against XSS.

Optional synthetic browser check: install Playwright and Chromium in a local
test environment, then run `python scripts/check_session_ui.py`. Use
`CHROME_PATH` for a different Chromium binary and `API_PYTHON` if the app's
Python environment is different. It starts a temporary dev-auth server and
SQLite DB, tests both pages against eight delayed account-switch cases, and
calls no models/providers. This is not enabled in CI.

### Concurrent snapshot writes

Authenticated SQL-backed requests use atomic document compare-and-set when
saving. If another process changed the same user's snapshot since it was
loaded, the losing request returns409`state_conflict`, without overwriting the
winner. Reopen the latest version before deliberately retrying. Automatic retry
is avoided because a request may already have called a model. A conflict can
therefore consume a model request without saving its output.

This requires no schema migration. The comparison uses the exact stored JSON,
not a reserialized approximation. It is document-value conflict detection,
not an event/revision ledger. SQLite multiprocess insert/update races, stale
approval after review, deletion, and per-user independence have local tests.
Postgres was not run. Whole-document rewriting and database lock timeouts remain
limits; SQL operational failures are not automatically retried. The memory
store is still single-process/ephemeral, and legacy `SqlSnapshot` and direct
unconditional `SqlUserStore.save` are not the authenticated concurrency path.

### PDF route execution

PDF decoding runs in FastAPI's synchronous endpoint worker pool, including the
blocking per-user state lock and bounded file read. The previous async route
could hold that lock while yielding for a spooled-file read: a second request
could then block the event loop waiting for the same lock. A timed subprocess
regression covers two same-user PDF calls and event-loop progress. This does
not sandbox pypdf CPU/memory use or add request-body/page caps by itself; see
separate upload hardening PR29. On combining branches, preserve the synchronous
`file.file.read(5_000_001)` route and PR29's other upload/decoder limits.

### No URL-triggered mutations

The AI page no longer has `#demo`, `#demo-approve` or `#demo-reject`
automation. Opening a URL must not parse private text, call a model, or make a
candidate decision. Use the visible controls deliberately. The optional browser
script checks all three fragments in an already signed-in context and verifies
no POST requests occur. This is not general CSRF/XSS protection or proof that
every decision originated with a human.
