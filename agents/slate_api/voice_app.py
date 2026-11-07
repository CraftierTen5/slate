"""Voice interview API adapter and enterprise assessment interface for Slate.

Extends the Slate API with zero-cost voice mock interview endpoints,
voice tone telemetry collection, and enterprise assessment room interface.
"""
import os, sys
from typing import Optional
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from slate_api.app import app, SlateError, STATUS
from slate_core.voice_interview import VoiceInterviewStore

voice_store = VoiceInterviewStore()

class VoiceMockIn(BaseModel):
    targetRole: str = "Data Analyst"

class VoiceToneIn(BaseModel):
    durationSec: Optional[float] = None
    wordsPerMinute: Optional[int] = None
    avgVolumeRms: Optional[float] = None
    fillerCount: Optional[int] = None
    fillersDetected: Optional[list] = None

class VoiceAnswerIn(BaseModel):
    text: str
    tone: Optional[VoiceToneIn] = None

voice_router = APIRouter(prefix="/v1/interview/voice")

@voice_router.post("/mock")
def mock_voice(b: VoiceMockIn):
    return voice_store.start(b.targetRole, voice_store.past_feedback())

@voice_router.post("/{sid}/answer")
def answer_voice(sid: str, b: VoiceAnswerIn):
    tone_dict = b.tone.model_dump(exclude_none=True) if b.tone else None
    try:
        return voice_store.answer(sid, b.text, tone_data=tone_dict)
    except KeyError:
        return JSONResponse({"error": {"code": "session_not_found", "message": "No voice interview session with that id."}}, status_code=404)

@voice_router.get("/{sid}/feedback")
def feedback_voice(sid: str):
    try:
        return voice_store.feedback(sid)
    except KeyError:
        return JSONResponse({"error": {"code": "session_not_found", "message": "No voice interview session with that id."}}, status_code=404)

# Mount the router on the FastAPI app
app.include_router(voice_router)

# Serve the enterprise voice interview room
voice_ui = os.path.join(os.path.dirname(__file__), "..", "..", "web", "voice_interview.html")

@app.get("/interview", include_in_schema=False)
def interview_page():
    if os.path.exists(voice_ui):
        return FileResponse(voice_ui)
    return JSONResponse({"message": "Voice interview UI not found"}, status_code=404)
