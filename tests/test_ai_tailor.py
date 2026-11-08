"""HTTP-level tests for the opt-in AI tailoring path."""
import os, sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
from fastapi.testclient import TestClient  # noqa: E402
from slate_api.app import create_app  # noqa: E402
from slate_core import SlateService  # noqa: E402
from slate_core.ai_service import AISlateService  # noqa: E402
from slate_core.llm import MockLLM  # noqa: E402

RESUME = ("Asha Verma\nB.Tech Computer Science, IIITM Gwalior, 2027\n"
          "Intern at ExampleCo (3 months)\nSkills: Python, Git, Excel\n")


def _client(monkeypatch, key, service):
    if key is None:
        monkeypatch.delenv("LLM_API_KEY", raising=False)
    else:
        monkeypatch.setenv("LLM_API_KEY", key)
    return TestClient(create_app(service))


def test_ai_tailor_off_without_key(monkeypatch):
    c = _client(monkeypatch, None, AISlateService(llm_client=MockLLM()))
    rid = c.post("/v1/resume", json={"text": RESUME}).json()["resumeId"]
    r = c.post("/v1/tailor/ai", json={"resumeId": rid, "jobId": "job_001"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "ai_not_configured"


def test_ai_tailor_off_on_plain_service(monkeypatch):
    c = _client(monkeypatch, "dummy-key", SlateService())
    rid = c.post("/v1/resume", json={"text": RESUME}).json()["resumeId"]
    r = c.post("/v1/tailor/ai", json={"resumeId": rid, "jobId": "job_001"})
    assert r.status_code == 503


def test_ai_tailor_full_review_flow(monkeypatch):
    reply = ("RESUME\nAsha Verma\nSkills: Python, Git. Strong with SQL.\n\n"
             "COVER NOTE\nI improved efficiency by 40% at ExampleCo.")
    c = _client(monkeypatch, "dummy-key", AISlateService(llm_client=MockLLM(reply)))
    rid = c.post("/v1/resume", json={"text": RESUME}).json()["resumeId"]
    r = c.post("/v1/tailor/ai", json={"resumeId": rid, "jobId": "job_001"})
    assert r.status_code == 200
    d = r.json()
    assert d["aiGenerated"] is True and d["requiresApproval"] is True
    assert d["status"] == "draft"
    # the gate surfaces both the unsupported skill and the invented metric
    assert any("sql" in s.lower() for s in d["flaggedClaims"] + d["violations"])
    assert any("40%" in v for v in d["violations"])
    # approval is re-validated by the normal path: a violating draft cannot
    # be approved as-is, so the human decision is structural, not cosmetic
    r2 = c.post("/v1/approvals", json={"draftId": d["draftId"], "decision": "approve"})
    assert r2.status_code == 422
    assert r2.json()["error"]["code"] == "unsupported_claim"


def test_ai_tailor_clean_draft_can_be_approved(monkeypatch):
    reply = ("RESUME\nAsha Verma\nSkills: Python, Git, Excel.\n\n"
             "COVER NOTE\nI know Python and Git from my internship.")
    c = _client(monkeypatch, "dummy-key", AISlateService(llm_client=MockLLM(reply)))
    rid = c.post("/v1/resume", json={"text": RESUME}).json()["resumeId"]
    d = c.post("/v1/tailor/ai", json={"resumeId": rid, "jobId": "job_001"}).json()
    assert d["flaggedClaims"] == [] and d["violations"] == []
    r2 = c.post("/v1/approvals", json={"draftId": d["draftId"], "decision": "approve"})
    assert r2.status_code == 200 and r2.json()["status"] == "approved"
