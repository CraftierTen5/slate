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

### Upload and local-state safety limits

POST/PUT/PATCH bodies are bounded before FastAPI's JSON/multipart parsing:
2 MB for JSON/other bodies; 5,000,000 bytes plus 64 KiB multipart overhead for
PDF uploads, with a 20-second total body-read deadline. The actual stream is
counted even when Content-Length is missing or dishonest. Oversized bodies
return a standard 413 error, slow bodies408. The PDF file itself is capped at
5,000,000 bytes,20 pages and200,000 extracted characters. Direct text parsing
has the same200,000-character cap. Failures do not create a new resume record.
These envelope limits can reject before authentication, by design; ordinary
allowed uploads still authenticate before PDF decoding/state access.

These are partial resource safeguards, not a PDF sandbox. PDF metadata/page-tree
loading and a single page's decompression/extraction still happen inside pypdf
before extracted-length checks. Hard CPU/memory isolation, connection/rate limits,
reverse-proxy request limits and an isolated parser worker remain future work.
Scanned-image OCR is not implemented. Do not expose local dev auth publicly.

`.local-state/`,SQLite database files and sidecars, and `uploads/` are ignored
by Git. This does not encrypt files, fix OS permissions, remove already tracked
files/history, or provide retention/account deletion/backups. The current branch
was checked for tracked runtime databases/uploads; none were found. No existing
state is deleted or rewritten by the ignore change. Keep local state private;
for an existing shared/tracked database, stop and review an explicit migration or
access change instead of blindly deleting files or rewriting history.
