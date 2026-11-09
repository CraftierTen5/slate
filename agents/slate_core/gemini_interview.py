"""Gemini-powered interview coach. Falls back cleanly when no key/SDK is available."""
import json
import os


class GeminiInterviewCoach:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        self._client = None

    def _ask(self, prompt):
        if not self.api_key:
            return None
        try:
            from google import genai
            if self._client is None:
                self._client = genai.Client(api_key=self.api_key)
            result = self._client.interactions.create(model=self.model, input=prompt)
            raw = getattr(result, "output_text", None)
            if not raw:
                return None
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            # A provider outage, invalid key, SDK mismatch, or malformed response
            # must never prevent a candidate from completing an interview.
            return None

    def opening_question(self, role, resume, past_feedback):
        prompt = (
            "You are Slate, a realistic, fair technical/career interviewer. "
            "Create one concise, natural opening interview question tailored to the candidate. "
            "Use only evidence in the resume; do not assume skills or experience. "
            "Avoid generic questions if a specific project or skill is available. "
            "Return JSON only: {\"question\": string}.\n"
            + json.dumps({"target_role": role, "resume": resume or {},
                          "previous_weak_areas": past_feedback}, ensure_ascii=False)
        )
        data = self._ask(prompt)
        return (data or {}).get("question")

    def review_answer(self, role, question, answer, resume, history, followup_allowed):
        prompt = (
            "You are Slate, a rigorous but conversational mock interviewer. Evaluate the candidate's "
            "answer for correctness, relevance, depth, evidence/examples, and communication. "
            "Do not reward length over substance. Do not invent facts about the candidate. "
            "If the answer is materially incomplete or contains a misconception, ask at most one "
            "focused follow-up; otherwise set follow_up_question to null. Avoid giving away the answer. "
            "Return valid JSON only with keys: score (integer 1-5), assessment (one concise paragraph), "
            "strengths (array of strings), improvements (array of strings), follow_up_question (string or null).\n"
            + json.dumps({"role": role, "question": question, "answer": answer,
                          "candidate_resume": resume or {}, "prior_turns": history,
                          "followup_allowed": followup_allowed}, ensure_ascii=False)
        )
        data = self._ask(prompt)
        if not data:
            return None
        try:
            score = max(1, min(5, int(data.get("score", 3))))
            return {"score": score, "assessment": str(data.get("assessment", ""))[:1200],
                    "strengths": [str(x)[:200] for x in data.get("strengths", [])[:5]],
                    "improvements": [str(x)[:200] for x in data.get("improvements", [])[:5]],
                    "follow_up_question": str(data["follow_up_question"])[:500]
                    if data.get("follow_up_question") else None}
        except (TypeError, ValueError, AttributeError):
            return None
