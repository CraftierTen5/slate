import os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
from slate_core.llm import (GeminiLLM, LLMError, MockLLM, build_feedback_prompt,
                            build_tailor_prompt)


def test_mock_records_prompt_and_replies():
    m = MockLLM("tailored!")
    assert m.generate("p1") == "tailored!"
    assert m.prompts == ["p1"]


def test_gemini_requires_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        GeminiLLM().generate("hi")


def test_gemini_request_shape():
    g = GeminiLLM(api_key="k")
    body = g._request_body("hello")
    import json
    assert json.loads(body) == {"contents": [{"parts": [{"text": "hello"}]}]}


def test_tailor_prompt_carries_resume_and_job():
    p = build_tailor_prompt({"name": "Asha", "skills": ["python"]},
                            {"title": "Data Analyst", "company": "ExampleCo"})
    assert "Asha" in p and "Data Analyst" in p and "do not invent" in p.lower()


def test_feedback_prompt_carries_transcript():
    p = build_feedback_prompt(["Why this role?"], ["Because I like data."])
    assert "Why this role?" in p and "Because I like data." in p


def test_groq_requires_key(monkeypatch):
    from slate_core.llm import GroqLLM
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        GroqLLM().generate("hi")


def test_groq_request_shape():
    import json
    from slate_core.llm import GroqLLM, GROQ_DEFAULT_MODEL
    g = GroqLLM(api_key="k")
    body = json.loads(g._request_body("hello"))
    assert body == {"model": GROQ_DEFAULT_MODEL,
                    "messages": [{"role": "user", "content": "hello"}]}


PARSED = {"name": "Asha", "skills": ["Python", "Git"],
          "experience": [{"title": "Intern", "org": "ExampleCo"}],
          "education": [{"degree": "B.Tech CS", "year": "2027"}]}
JOB = {"title": "Data Analyst", "company": "ExampleCo",
       "skills": ["Python", "SQL"]}


def test_llm_draft_shape_and_approval():
    from slate_core.llm import llm_tailored_draft
    m = MockLLM("RESUME\nAsha\nSkills: Python\n\nCOVER NOTE\nI know Python.")
    d = llm_tailored_draft(PARSED, JOB, m)
    for key in ("tailoredResume", "coverNote", "claims", "gaps",
                "flaggedClaims", "requiresApproval"):
        assert key in d
    assert d["requiresApproval"] is True
    assert d["claims"] == ["Python"]
    assert d["gaps"] == ["SQL"]
    assert d["flaggedClaims"] == []


def test_llm_draft_flags_invented_skill():
    """Regression for the Nov 8 live Groq test: the model suggested claiming
    experience the resume never stated. The gate must flag it and the draft
    must stay human-approval-only."""
    from slate_core.llm import llm_tailored_draft
    m = MockLLM("RESUME\nAsha\nStrong in Python and SQL.\n\nCOVER NOTE\nSQL expert.")
    d = llm_tailored_draft(PARSED, JOB, m)
    assert d["flaggedClaims"] == ["SQL"]
    assert d["requiresApproval"] is True
