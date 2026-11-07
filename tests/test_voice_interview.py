"""Tests for voice-based mock interview, vocal tone detection, answer correctness, and interactive follow-ups."""
import os, sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from slate_core.voice_interview import VoiceInterviewStore, analyze_voice_tone, verify_answer_correctness
from slate_api.voice_app import app

@pytest.fixture
def client():
    return TestClient(app)

def test_analyze_voice_tone_optimal():
    text = "In my previous project I designed a normalized SQL database and built automated indexing."
    tone = analyze_voice_tone(text, {"durationSec": 6.0, "wordsPerMinute": 140, "avgVolumeRms": 0.3})
    assert tone["wordsPerMinute"] == 140
    assert tone["fillerCount"] == 0
    assert tone["pacingRating"] == "Optimal & Confident"
    assert tone["projectionRating"] == "Clear & Well-Projected"
    assert tone["confidenceScore"] >= 80
    assert tone["toneLabel"] == "Confident & Articulate"

def test_analyze_voice_tone_fillers_and_slow():
    text = "Um basically uh I think like it was um sort of difficult."
    tone = analyze_voice_tone(text, {"durationSec": 15.0, "wordsPerMinute": 50, "avgVolumeRms": 0.05})
    assert tone["fillerCount"] >= 3
    assert "um" in tone["fillersDetected"]
    assert tone["pacingRating"] == "Hesitant / Slow"
    assert tone["projectionRating"] == "Soft / Mumbled"
    assert tone["confidenceScore"] < 60

def test_verify_answer_correctness_relevant_vs_irrelevant():
    q = "Walk me through a SQL query you wrote to answer a business question."
    
    # 1. Totally irrelevant answer (talking about food/movies)
    bad_ans = "I really love eating pizza with extra cheese on weekends while watching comedy films."
    eval_bad = verify_answer_correctness(q, bad_ans)
    assert not eval_bad["isValid"]
    assert "Irrelevant" in eval_bad["status"]
    assert eval_bad["weaknessFlag"] is not None

    # 2. Accurate, relevant technical answer
    good_ans = "I wrote a query with SELECT customer_id, SUM(amount) FROM orders JOIN payments ON orders.id = payments.order_id GROUP BY customer_id."
    eval_good = verify_answer_correctness(q, good_ans)
    assert eval_good["isValid"]
    assert "Accurate" in eval_good["status"]
    assert eval_good["weaknessFlag"] is None

def test_interactive_followup_question_flow():
    store = VoiceInterviewStore()
    s = store.start("Data Analyst")
    sid = s["sessionId"]
    assert s["firstQuestion"]
    assert s["totalQuestions"] >= 3

    # Candidate answers first question
    q1 = s["firstQuestion"]
    r1 = store.answer(sid, "In this task I joined customer records and calculated statistical aggregations grouped by month.",
                      {"durationSec": 8.0, "wordsPerMinute": 135})
    # Must generate an adaptive follow-up
    assert not r1["done"]
    assert r1["isFollowup"] is True
    assert r1["nextQuestion"]

    # Candidate answers follow-up
    r2 = store.answer(sid, "I added composite indexes and validated summary metrics to prevent bottlenecks.",
                      {"durationSec": 6.0, "wordsPerMinute": 140})
    # Must now advance to next question
    assert not r2["done"]
    assert r2["isFollowup"] is False
    assert r2["nextQuestion"] != q1

def test_voice_interview_store_flags_irrelevant_answers_as_weak_areas():
    store = VoiceInterviewStore()
    s1 = store.start("Data Analyst")
    sid = s1["sessionId"]

    # Provide completely irrelevant answer
    store.answer(sid, "I enjoy playing football in the evening with my university friends.",
                 {"durationSec": 10.0, "wordsPerMinute": 130, "avgVolumeRms": 0.35})
    
    # Provide relevant answer
    store.answer(sid, "I check for null values, duplicates, and outlier ranges using pandas.",
                 {"durationSec": 8.0, "wordsPerMinute": 135})

    # Provide short/shallow answer
    store.answer(sid, "short", {"durationSec": 2.0, "wordsPerMinute": 40})

    fb = store.feedback(sid)
    assert fb["transcriptRef"] == sid
    # Irrelevant or shallow answers must be flagged in weakAreas!
    assert len(fb["weakAreas"]) >= 1
    assert fb["toneAnalysis"]["contentAccuracyScore"] < 75

    # Adaptive memory test: next session must carry the flagged weak areas
    s2 = store.start("Data Analyst", store.past_feedback())
    assert s2["carriedFromEarlier"]

def test_voice_api_http_endpoints_and_tts(client):
    # 1. Start voice session
    r1 = client.post("/v1/interview/voice/mock", json={"targetRole": "Data Analyst"})
    assert r1.status_code == 200
    data = r1.json()
    sid = data["sessionId"]
    assert "firstQuestion" in data

    # 2. Answer question with acoustic tone telemetry
    r2 = client.post(f"/v1/interview/voice/{sid}/answer", json={
        "text": "I created optimized indexing on high traffic foreign keys.",
        "tone": {"durationSec": 5.5, "wordsPerMinute": 140, "avgVolumeRms": 0.28}
    })
    assert r2.status_code == 200
    assert "isFollowup" in r2.json()

    # 3. Get feedback
    r3 = client.get(f"/v1/interview/voice/{sid}/feedback")
    assert r3.status_code == 200
    fb = r3.json()
    assert "toneAnalysis" in fb
    assert fb["toneAnalysis"]["overallRating"]

    # 4. Error case: invalid session
    r4 = client.get("/v1/interview/voice/invalid_id/feedback")
    assert r4.status_code == 404

    # 5. UI endpoint
    r5 = client.get("/interview")
    assert r5.status_code == 200
    assert "Slate" in r5.text

    # 6. Natural Neural TTS endpoint
    r6 = client.get("/v1/interview/voice/tts", params={"text": "Hello candidate", "voice": "guy"})
    assert r6.status_code == 200
    assert r6.headers["content-type"] == "audio/mpeg"
    assert len(r6.content) > 1000
