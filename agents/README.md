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
