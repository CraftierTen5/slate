"""Tests for voice-based mock interview and voice tone detection."""
import os, sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from slate_core.voice_interview import VoiceInterviewStore, analyze_voice_tone
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

def test_voice_interview_store_flow_and_memory():
    store = VoiceInterviewStore()
    s1 = store.start("Data Analyst")
    assert s1["mode"] == "voice"
    assert s1["totalQuestions"] >= 3
    sid = s1["sessionId"]

    # Answer questions with tone data
    res1 = store.answer(sid, "I used PostgreSQL with window functions to calculate 30-day moving averages.",
                        {"durationSec": 10.0, "wordsPerMinute": 130, "avgVolumeRms": 0.35})
    assert not res1["done"]
    assert res1["questionNumber"] == 2

    # Provide short answer to trigger weak area
    store.answer(sid, "short", {"durationSec": 2.0, "wordsPerMinute": 30})
    store.answer(sid, "I handled data cleaning using pandas and regex checks.", {"durationSec": 8.0, "wordsPerMinute": 135})

    fb = store.feedback(sid)
    assert fb["transcriptRef"] == sid
    assert fb["weakAreas"]
    assert fb["toneAnalysis"]["overallScore"] > 0
    assert "breakdown" in fb["toneAnalysis"]

    # Adaptive memory test: next session carries the weak area
    s2 = store.start("Data Analyst", store.past_feedback())
    assert s2["carriedFromEarlier"]
    assert "Last time this was flagged" in s2["firstQuestion"]

def test_voice_api_http_endpoints(client):
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

    # 3. Get feedback
    r3 = client.get(f"/v1/interview/voice/{sid}/feedback")
    assert r3.status_code == 200
    fb = r3.json()
    assert "toneAnalysis" in fb
    assert fb["toneAnalysis"]["overallTone"]

    # 4. Error case: invalid session
    r4 = client.get("/v1/interview/voice/invalid_id/feedback")
    assert r4.status_code == 404

    # 5. UI endpoint
    r5 = client.get("/interview")
    assert r5.status_code == 200
    assert "Slate" in r5.text
