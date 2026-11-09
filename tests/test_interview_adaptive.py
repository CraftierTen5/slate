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
    assert fb["weakAreas"] == ["Python projects"]


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


def test_legacy_saved_interview_session_is_upgraded():
    store = InterviewStore()
    store._sessions["int_old"] = {
        "role": "Data Analyst",
        "questions": ["Explain SQL joins.", "How do you clean data?"],
        "answers": ["short"], "carried": [],
    }
    result = store.answer("int_old", "I would inspect nulls, duplicates, and invalid types.")
    assert result["done"] is False
    ended = store.end("int_old")
    assert ended["ended"] is True
    feedback = store.feedback("int_old")
    assert feedback["answeredCount"] == 2
    assert feedback["coachMode"] == "deterministic_fallback"


def test_interview_continues_past_fallback_question_bank_until_explicit_end():
    store = InterviewStore()
    started = store.start("Data Analyst", [])
    session = store._sessions[started["sessionId"]]
    total = len(session["fallback_questions"]) + 3
    for index in range(total):
        result = store.answer(started["sessionId"], "I would investigate the problem, validate the data, and explain the outcome.")
        assert result["done"] is False
    assert store.feedback(started["sessionId"])["ended"] is False
    final = store.end(started["sessionId"])
    assert final["ended"] is True
    assert final["answeredCount"] == total
    try:
        store.answer(started["sessionId"], "one more answer")
        assert False, "ended interview must reject further answers"
    except ValueError as exc:
        assert str(exc) == "interview_ended"


def test_interviewer_can_chain_multiple_followups():
    class ProbingCoach:
        def __init__(self):
            self.count = 0

        def first_question(self, role, resume, past):
            return "Tell me about a project."

        def evaluate_answer(self, role, question, answer, resume, history, followup_used, delivery_metrics=None):
            self.count += 1
            return {
                "score": 3, "feedback": "Probe the detail.",
                "strengths": [], "improvements": [],
                "follow_up_question": f"Probe {self.count}?" if self.count < 3 else None,
                "next_question": "How would you validate the result?",
                "topic": "Project"
            }

    store = InterviewStore(coach=ProbingCoach())
    sid = store.start("Data Analyst", [])["sessionId"]
    one = store.answer(sid, "I built a dashboard.")
    two = store.answer(sid, "I used Python.")
    three = store.answer(sid, "I measured accuracy.")
    assert one["isFollowUp"] is True
    assert two["isFollowUp"] is True
    assert three["isFollowUp"] is False
    assert three["nextQuestion"] == "How would you validate the result?"


def test_delivery_metrics_get_a_separate_rule_based_score_without_gemini():
    store = InterviewStore()
    sid = store.start("Data Analyst", [], mode="voice")["sessionId"]
    metrics = {
        "durationSeconds": 42.0, "wordsPerMinute": 132,
        "pauseRatio": 0.22, "pauseCount": 3, "fillerCount": 1,
        "meanVolume": 0.08, "volumeVariation": 0.02
    }
    result = store.answer(sid, "I designed a clear dashboard and validated the source data.", metrics)
    assert result["evaluation"]["deliveryScore"] is not None
    assert "Rule-based estimate" in result["evaluation"]["deliveryFeedback"]
    assert 1 <= result["evaluation"]["deliveryScore"] <= 5
    report = store.end(sid)
    assert report["averageDeliveryScore"] == result["evaluation"]["deliveryScore"]
