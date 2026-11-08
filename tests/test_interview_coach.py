import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
from slate_core.interview import InterviewStore


class FakeCoach:
    def __init__(self):
        self.calls = 0

    def opening_question(self, role, resume, context=None):
        return "Tell me about a project from your resume."

    def review_answer(self, role, question, answer, resume, history, followup_allowed):
        self.calls += 1
        return {
            "score": 4,
            "assessment": "Good reasoning; add a measurable result.",
            "strengths": ["Clear explanation"],
            "improvements": ["Add measurable evidence."],
            "follow_up_question": "What trade-off did you consider?" if followup_allowed else None,
        }


def test_interview_adapts_and_limits_followups():
    coach = FakeCoach()
    store = InterviewStore(coach=coach)
    started = store.start("Data Analyst", [], {"skills": ["python"]})
    assert started["firstQuestion"] == "Tell me about a project from your resume."

    first = store.answer(started["sessionId"], "I built a dashboard.")
    assert first["isFollowUp"] is True
    assert first["nextQuestion"] == "What trade-off did you consider?"

    second = store.answer(started["sessionId"], "I chose a simpler chart.")
    assert second["isFollowUp"] is False
    assert second["nextQuestion"] is not None

    feedback = store.feedback(started["sessionId"])
    assert feedback["averageScore"] == 4
    assert feedback["answerReviews"][0]["strengths"] == ["Clear explanation"]


def test_no_key_fallback_keeps_existing_interview_flow():
    store = InterviewStore()
    started = store.start("Data Analyst", [])
    assert started["firstQuestion"]
    result = store.answer(started["sessionId"], "A short answer")
    assert result["evaluation"]["score"] == 2
    assert result["nextQuestion"]
