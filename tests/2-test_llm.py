import os
import pytest
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
