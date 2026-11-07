"""Voice-based mock interview and vocal tone analysis for Slate.

Zero-cost, completely local and deterministic. Evaluates candidate voice tone,
speaking pace (WPM), filler words, acoustic projection (RMS volume), and delivery confidence.
"""
import re
from .sample_data import INTERVIEW_QUESTIONS

COMMON_FILLERS = [
    "um", "uh", "er", "ah", "like", "you know", "basically", 
    "actually", "sort of", "kind of", "so yeah", "i mean"
]

def analyze_voice_tone(text: str, tone_data: dict = None) -> dict:
    """Analyze vocal tone, pacing, volume consistency, and filler words from candidate speech."""
    words = re.findall(r"\b[A-Za-z']+\b", (text or "").lower())
    total_words = len(words)

    # Detect filler words
    filler_matches = []
    text_lower = " " + (text or "").lower() + " "
    for f in COMMON_FILLERS:
        cnt = len(re.findall(r"(?<![a-z])" + re.escape(f) + r"(?![a-z])", text_lower))
        if cnt > 0:
            filler_matches.extend([f] * cnt)

    tone_data = tone_data or {}
    duration_sec = float(tone_data.get("durationSec") or (total_words / 2.2 if total_words else 1.0))
    wpm = tone_data.get("wordsPerMinute")
    if wpm is None:
        wpm = round((total_words / (duration_sec / 60))) if duration_sec > 0 else 0
    else:
        wpm = int(wpm)

    # Pacing analysis
    if wpm < 110:
        pacing_rating = "Hesitant / Slow"
        pacing_tip = "Pacing was somewhat slow. Aim for 125-155 WPM for a natural, executive cadence."
    elif wpm > 175:
        pacing_rating = "Fast / Rushed"
        pacing_tip = "Pacing was rushed. Slow down slightly to emphasize key points and give ideas room to breathe."
    else:
        pacing_rating = "Optimal & Confident"
        pacing_tip = "Great speaking cadence and balanced conversational pacing."

    # Acoustic volume & vocal projection rating
    avg_rms = tone_data.get("avgVolumeRms")
    if avg_rms is not None:
        avg_rms = float(avg_rms)
        if avg_rms < 0.10:
            projection_rating = "Soft / Mumbled"
            projection_tip = "Voice volume was quiet. Project more firmly into the microphone."
        elif avg_rms > 0.65:
            projection_rating = "Overly Loud / Clipping"
            projection_tip = "Audio levels were peaking; maintain a balanced distance from the mic."
        else:
            projection_rating = "Clear & Well-Projected"
            projection_tip = "Solid vocal projection and clear audio levels."
    else:
        projection_rating = "Clear"
        projection_tip = "Natural conversational volume."

    # Confidence scoring (scale 0-100)
    conf_score = 85
    if total_words < 12:
        conf_score -= 25
    if len(filler_matches) > 1:
        conf_score -= min(25, len(filler_matches) * 5)
    if pacing_rating != "Optimal & Confident":
        conf_score -= 10
    if avg_rms is not None and avg_rms < 0.10:
        conf_score -= 10
    conf_score = max(20, min(95, conf_score))

    if conf_score >= 80:
        tone_label = "Confident & Articulate"
    elif conf_score >= 60:
        tone_label = "Composed with Minor Hesitations"
    else:
        tone_label = "Hesitant / Needs Polish"

    return {
        "wordCount": total_words,
        "durationSec": round(duration_sec, 1),
        "wordsPerMinute": wpm,
        "pacingRating": pacing_rating,
        "pacingTip": pacing_tip,
        "projectionRating": projection_rating,
        "projectionTip": projection_tip,
        "fillerCount": len(filler_matches),
        "fillersDetected": sorted(list(set(filler_matches))),
        "confidenceScore": conf_score,
        "toneLabel": tone_label,
    }

class VoiceInterviewStore:
    """Manages voice-enabled interview sessions with acoustic telemetry and cross-session memory."""
    def __init__(self):
        self._sessions = {}
        self._n = 0

    def start(self, target_role: str, past_feedback: list = None) -> dict:
        self._n += 1
        sid = f"voice_int_{self._n:03d}"
        past_feedback = past_feedback or []
        qs = list(INTERVIEW_QUESTIONS.get(target_role, INTERVIEW_QUESTIONS["default"]))
        
        # Adaptive memory: carry forward prior weak areas
        carried = [w for f in past_feedback for w in f.get("weakAreas", [])]
        for w in reversed(carried):
            qs.insert(0, f"Last time this was flagged: {w}. Walk me through this again.")

        self._sessions[sid] = {
            "role": target_role,
            "mode": "voice",
            "questions": qs,
            "answers": [],
            "tones": [],
            "carried": carried,
        }
        return {
            "sessionId": sid,
            "firstQuestion": qs[0],
            "totalQuestions": len(qs),
            "carriedFromEarlier": carried,
            "mode": "voice",
        }

    def answer(self, sid: str, text: str, tone_data: dict = None) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            raise KeyError("session_not_found")
        s["answers"].append(text or "")
        s["tones"].append(tone_data or {})
        idx = len(s["answers"])
        done = idx >= len(s["questions"])
        return {
            "done": done,
            "nextQuestion": s["questions"][idx] if not done else None,
            "questionNumber": idx + 1 if not done else idx,
            "totalQuestions": len(s["questions"]),
        }

    def feedback(self, sid: str) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            raise KeyError("session_not_found")

        weak = []
        per_q_tones = []
        tones = s.get("tones", [])

        for i, (q, a) in enumerate(zip(s["questions"], s["answers"])):
            t_data = tones[i] if i < len(tones) else {}
            t_eval = analyze_voice_tone(a, t_data)
            per_q_tones.append({
                "question": q,
                "answer": a,
                "tone": t_eval
            })

            # Evaluate content depth
            if len(a.split()) < 12:
                clean_q = q.split(":")[0].replace("Last time this was flagged", "").strip() or q
                weak.append(clean_q)
            # Evaluate voice delivery
            elif t_eval["confidenceScore"] < 55 or t_eval["fillerCount"] >= 4:
                weak.append(f"delivery on '{q[:35]}...' ({t_eval['toneLabel']}, {t_eval['fillerCount']} fillers)")

        if len(s["answers"]) < len(s["questions"]):
            weak.append("unanswered questions")

        avg_conf = round(sum(p["tone"]["confidenceScore"] for p in per_q_tones) / len(per_q_tones)) if per_q_tones else 50
        avg_wpm = round(sum(p["tone"]["wordsPerMinute"] for p in per_q_tones) / len(per_q_tones)) if per_q_tones else 0
        tot_fillers = sum(p["tone"]["fillerCount"] for p in per_q_tones)
        all_fillers = sorted(list(set(f for p in per_q_tones for f in p["tone"]["fillersDetected"])))

        if avg_conf >= 80:
            overall_tone = "Confident & Articulate"
        elif avg_conf >= 60:
            overall_tone = "Composed with Minor Hesitations"
        else:
            overall_tone = "Hesitant / Needs Practice"

        tone_analysis = {
            "overallScore": avg_conf,
            "overallTone": overall_tone,
            "averageWpm": avg_wpm,
            "totalFillers": tot_fillers,
            "commonFillers": all_fillers,
            "breakdown": per_q_tones,
        }

        fb = {
            "summary": f"{len(s['answers'])} of {len(s['questions'])} answered; {len(weak)} weak area(s). Overall delivery: {overall_tone} ({avg_conf}/100).",
            "weakAreas": weak,
            "transcriptRef": sid,
            "toneAnalysis": tone_analysis,
        }
        s["feedback"] = fb
        return fb

    def past_feedback(self) -> list:
        return [s["feedback"] for s in self._sessions.values() if "feedback" in s]
