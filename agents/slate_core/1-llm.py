"""Optional LLM adapter for tailoring and interview feedback.

Not wired into tailor.py or interview.py yet: those stay deterministic by default.
Nothing here runs without a server-side key in the LLM_API_KEY env var; no key is
ever read from or written to the client, and tests use MockLLM only.

Swap points (documented in slate_core README): tailor.build_draft text generation
and interview question/feedback generation can take an LLMClient later without
changing the API contract shapes.
"""
import json
import os
import urllib.request

DEFAULT_MODEL = "gemini-3.8-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(Exception):
    pass


class LLMClient:
    """Provider-replaceable interface: one method, plain text in and out."""

    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class MockLLM(LLMClient):
    """Deterministic stand-in for tests and demos without a key."""

    def __init__(self, reply: str = "mock response"):
        self.reply = reply
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.reply


class GeminiLLM(LLMClient):
    """Gemini Developer API over stdlib urllib. Key comes from LLM_API_KEY."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str = None, timeout: int = 30):
        self.model = model
        self.api_key = api_key if api_key is not None else os.environ.get("LLM_API_KEY", "")
        self.timeout = timeout

    def _request_body(self, prompt: str) -> bytes:
        return json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise LLMError("LLM_API_KEY is not set on the server.")
        req = urllib.request.Request(
            API_BASE.format(model=self.model),
            data=self._request_body(prompt),
            headers={"content-type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            raise LLMError(f"LLM request failed: {e}")
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            raise LLMError("LLM response had no text.")


def build_tailor_prompt(parsed: dict, job: dict) -> str:
    """Prompt for a tailored resume draft and cover note. Callers must keep the
    existing claim check on whatever comes back - the LLM is not a fact check."""
    return (
        "Rewrite this resume for the job below. Rules: only claim skills, employers, "
        "education and numbers that appear in the original resume; do not invent anything. "
        "Return plain text with a 'RESUME' section and a 'COVER NOTE' section.\n\n"
        f"ORIGINAL RESUME:\n{json.dumps(parsed, indent=2)}\n\n"
        f"JOB:\n{json.dumps(job, indent=2)}"
    )


def build_feedback_prompt(questions: list, answers: list) -> str:
    """Prompt for interview feedback returning summary and weak areas."""
    qa = "\n".join(f"Q: {q}\nA: {a}" for q, a in zip(questions, answers))
    return (
        "You are an interview coach. Given this mock interview transcript, return "
        "plain text with a 'SUMMARY' section (2-3 sentences) and a 'WEAK AREAS' "
        "section (one per line).\n\n"
        f"{qa}"
    )
