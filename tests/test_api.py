"""HTTP-level tests. Need: pip install fastapi httpx pytest. Run: python -m pytest tests -q"""
import os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
pytest.importorskip("fastapi"); pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from slate_api.app import create_app
from slate_core import SlateService
from slate_core.tailor import check_claims

RESUME = "Asha Verma\nB.Tech Computer Science, IIITM Gwalior, 2027\nIntern at ExampleCo (3 months)\nSkills: Python, Git, Excel\n"

@pytest.fixture()
def c(): return TestClient(create_app(SlateService()))

def _rid(c): return c.post("/v1/resume", json={"text": RESUME}).json()["resumeId"]

def test_full_demo_flow(c):
    rid = _rid(c)
    jobs = c.get("/v1/jobs", params={"query": "analyst", "resumeId": rid}).json()["jobs"]
    assert jobs and jobs[0]["matchScore"] >= jobs[-1]["matchScore"]
    d = c.post("/v1/tailor", json={"resumeId": rid, "jobId": jobs[0]["jobId"]}).json()
    assert d["status"] == "draft"
    assert c.post("/v1/approvals", json={"draftId": d["draftId"], "decision": "approve"}).json()["status"] == "approved"
    assert "coverNote" in c.get(f"/v1/drafts/{d['draftId']}/export").json()
    assert c.post("/v1/roadmap", json={"resumeId": rid, "targetRole": "Data Analyst"}).json()["milestones"]
    sid = c.post("/v1/interview/mock", json={"targetRole": "Data Analyst"}).json()["sessionId"]
    c.post(f"/v1/interview/{sid}/answer", json={"text": "short"})
    fb = c.get(f"/v1/interview/{sid}/feedback").json()
    assert fb["transcriptRef"] == sid
    again = c.post("/v1/interview/mock", json={"targetRole": "Data Analyst"}).json()
    assert again["carriedFromEarlier"]  # memory across sessions

def test_gate_holds_when_client_bypasses_ui(c):
    """Direct API calls, no UI: unapproved, edited-after-approval and rejected drafts cannot be exported."""
    rid = _rid(c)
    d = c.post("/v1/tailor", json={"resumeId": rid, "jobId": "job_001"}).json()["draftId"]
    assert c.get(f"/v1/drafts/{d}/export").status_code == 403
    c.post("/v1/approvals", json={"draftId": d, "decision": "approve"})
    new = c.post(f"/v1/drafts/{d}/edit", json={"coverNote": "changed"}).json()["draftId"]
    assert new != d and c.get(f"/v1/drafts/{new}/export").status_code == 403
    d2 = c.post("/v1/tailor", json={"resumeId": rid, "jobId": "job_001"}).json()["draftId"]
    c.post("/v1/approvals", json={"draftId": d2, "decision": "reject"})
    assert c.post("/v1/approvals", json={"draftId": d2, "decision": "approve"}).status_code == 409
    assert c.get(f"/v1/drafts/{d2}/export").status_code == 403

def test_errors_use_contract_shape(c):
    for resp in (c.post("/v1/resume", json={"text": ""}), c.post("/v1/tailor", json={"resumeId": "x", "jobId": "y"}),
                 c.post("/v1/resume", json={}), c.post("/v1/approvals", json={"draftId": "d", "decision": "maybe"}),
                 c.get("/v1/interview/nope/feedback")):
        assert resp.status_code >= 400
        assert set(resp.json()["error"]) == {"code", "message"}

def test_empty_query_is_not_a_crash(c):
    assert c.get("/v1/jobs", params={"query": "zzzz"}).json() == {"jobs": []}

def test_claim_check_flags_unbacked_claims():
    parsed = {"skills": ["python"]}
    assert check_claims(parsed, ["python", "sql"]) == ["sql"]
