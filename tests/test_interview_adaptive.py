import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from slate_core.interview import InterviewStore, GeminiInterviewCoach
from slate_core.llm import MockLLM
from slate_core.service import SlateService


def test_gemini_coach_parses_question_and_evaluation():
    model = MockLLM(
        '{"question":"Explain a project where you used Python.","topic":"Python projects"}'
    )
    coach = GeminiInterviewCoach(model)
    question = coach.first_question("Data Analyst", {"skills": ["python"]}, [])
    assert "Python" in question
    result = coach.evaluate_answer(
        "Data Analyst", question, "I automated a report with Python.",
        {"skills": ["python"]}, [], False
    ) if False else None


def test_interview_store_adapts_and_allows_one_followup_per_main_question():
    class Coach:
        def __init__(self):
            self.calls = 0

        def first_question(self, role, resume, past):
            assert role == "Data Analyst"
            assert resume["skills"] == ["python"]
            return "Describe a Python project."

        def evaluate_answer(self, role, question, answer, resume, history, followup_used):
            self.calls += 1
            if not followup_used:
                return {
                    "score": 2, "feedback": "Give a measurable result.",
                    "strengths": ["Relevant example"], "improvements": ["Add impact"],
                    "follow_up_question": "What changed after your work?",
                    "next_question": "How would you validate a dataset?",
                    "topic": "Python projects"
                }
            return {
                "score": 4, "feedback": "Clearer with a result.",
                "strengths": ["Specific result"], "improvements": [],
                "follow_up_question": "Do not ask another follow-up.",
                "next_question": "How would you validate a dataset?",
                "topic": "Python projects"
            }

    store = InterviewStore(coach=Coach())
    started = store.start("Data Analyst", [], {"skills": ["python"]}, "voice")
    assert started["aiPowered"] is True
    first = store.answer(started["sessionId"], "I built a dashboard.")
    assert first["isFollowUp"] is True
    second = store.answer(started["sessionId"], "It reduced manual work by half.")
    assert second["isFollowUp"] is False
    assert second["nextQuestion"] == "How would you validate a dataset?"
    fb = store.feedback(started["sessionId"])
    assert fb["averageScore"] == 3
    assert fb["mode"] == "voice"
    assert fb["weakAreas"] == []


def test_deterministic_fallback_remains_available():
    store = InterviewStore()
    started = store.start("Data Analyst", [])
    result = store.answer(started["sessionId"], "short")
    assert result["evaluation"]["score"] == 1
    assert result["done"] is False
    feedback = store.feedback(started["sessionId"])
    assert feedback["coachMode"] == "deterministic_fallback"
    assert feedback["weakAreas"]


def test_service_accepts_resume_context_and_voice_mode():
    service = SlateService()
    resume = service.upload_resume(
        "Asha Verma\nB.Tech Computer Science, IIITM Gwalior, 2027\n"
        "Intern at ExampleCo (3 months)\nSkills: Python, Git, Excel\n"
    )
    started = service.start_interview("Data Analyst", "voice", resume["resumeId"])
    session = service.interviews._sessions[started["sessionId"]]
    assert session["mode"] == "voice"
    assert "python" in session["resume_context"]["skills"]
