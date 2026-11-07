# cli

Command-line client for Slate. It calls the same `/v1` API as the website - no Slate logic lives here,
so CLI and website stay in parity by construction. Python 3.10+, stdlib only.

Start the API first (see docs/demo.md), then from the repo root:

    python cli/slate.py parse path/to/resume.txt      # or a .pdf
    python cli/slate.py jobs --resume-id res_001
    python cli/slate.py tailor --resume-id res_001 --job-id job_002
    python cli/slate.py approve --draft-id draft_001  # or: reject
    python cli/slate.py export --draft-id draft_001   # approved drafts only
    python cli/slate.py roadmap --resume-id res_001 --target-role "Data Analyst"
    python cli/slate.py interview --target-role "Data Analyst"

Server default is http://127.0.0.1:8000; override with `--server URL` or `SLATE_API_URL`.
Same demo limits as the website: sample jobs, rule-based checks (not fact checking), no login.
