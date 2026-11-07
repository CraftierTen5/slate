"""Voice-based mock interview, vocal tone analysis, and answer correctness verification for Slate.

Zero-cost, completely local and deterministic. Evaluates candidate voice tone,
speaking pace (WPM), filler words, acoustic projection (RMS volume), delivery confidence,
and substantive technical correctness and relevance to the question.
"""
import re
from .sample_data import INTERVIEW_QUESTIONS

COMMON_FILLERS = [
    "um", "uh", "er", "ah", "like", "you know", "basically", 
    "actually", "sort of", "kind of", "so yeah", "i mean"
]

QUESTION_CRITERIA = {
    # Data Analyst questions
    "sql query": {
        "topics": [
            "sql", "query", "select", "join", "group by", "where", "having", 
            "sum", "count", "avg", "table", "database", "orders", "customers", 
            "revenue", "filter", "aggregate", "metric", "window", "cte"
        ],
        "min_matches": 2,
        "hint": "Address specific SQL clauses (SELECT, JOIN, GROUP BY, WHERE) and how they answered the business metric or query."
    },
    "bad data": {
        "topics": [
            "null", "missing", "duplicate", "duplicates", "outlier", "outliers", 
            "schema", "datatype", "type", "anomaly", "validation", "clean", 
            "pandas", "isna", "drop_duplicates", "distribution", "check", "format", "range"
        ],
        "min_matches": 2,
        "hint": "Discuss data profiling techniques like identifying nulls/missing values, duplicate records, outliers, and schema validation."
    },
    "mean and median": {
        "topics": [
            "mean", "median", "average", "outlier", "outliers", "skew", 
            "skewed", "extreme", "distribution", "salary", "income", "middle", "symmetric"
        ],
        "min_matches": 2,
        "hint": "Explain how extreme outliers skew the mean while the median remains robust to skewed distributions (e.g. income/salaries)."
    },
    # General / Engineering questions
    "project": {
        "topics": [
            "project", "built", "created", "designed", "implemented", "architecture", 
            "database", "api", "frontend", "backend", "users", "stack", "react", 
            "python", "fastapi", "tradeoff", "change", "refactor", "scale", "performance", "improve"
        ],
        "min_matches": 2,
        "hint": "Detail the architecture, your specific contribution, key trade-offs, and concrete technical improvements you'd make in retrospect."
    },
    "stuck": {
        "topics": [
            "bug", "error", "stuck", "problem", "issue", "debug", "debugging", 
            "logs", "documentation", "reproduce", "test", "root cause", "solution", "fixed", "learned"
        ],
        "min_matches": 2,
        "hint": "Walk through your structured debugging methodology: reading logs, isolating reproducing steps, consulting docs, or identifying root cause."
    },
    "why this role": {
        "topics": [
            "role", "company", "career", "interest", "passion", "skills", 
            "growth", "opportunity", "impact", "align", "mission", "contribute"
        ],
        "min_matches": 2,
        "hint": "Connect your technical skills and career goals directly to the company's mission and role requirements."
    }
}

def verify_answer_correctness(question: str, answer: str) -> dict:
    """Evaluate whether candidate's answer is relevant, accurate, and substantively addresses the question."""
    ans_low = (answer or "").lower().strip()
    words = re.findall(r"\b[a-z0-9_']+\b", ans_low)
    total_words = len(words)

    if total_words < 8:
        return {
            "isValid": False,
            "status": "Incomplete / Too Brief",
            "score": 25,
            "feedback": "Answer was too brief to evaluate technical competence.",
            "weaknessFlag": f"shallow answer on '{question[:30]}...'"
        }

    q_low = (question or "").lower()
    matched_criteria = None
    for pattern, crit in QUESTION_CRITERIA.items():
        if pattern in q_low:
            matched_criteria = crit
            break

    if matched_criteria:
        topics = matched_criteria["topics"]
        found = [t for t in topics if re.search(r"\b" + re.escape(t) + r"\b", ans_low)]
        match_count = len(found)
        required = matched_criteria["min_matches"]

        if match_count == 0:
            return {
                "isValid": False,
                "status": "Irrelevant / Off-Topic",
                "score": 20,
                "feedback": f"Your response did not address the topic of the question. {matched_criteria['hint']}",
                "weaknessFlag": f"off-topic answer on '{question[:30]}...'"
            }
        elif match_count < required:
            return {
                "isValid": False,
                "status": "Partially Relevant / Lacks Depth",
                "score": 50,
                "feedback": f"Mentioned {', '.join(found[:2])}, but missed key technical concepts. {matched_criteria['hint']}",
                "weaknessFlag": f"missing depth on '{question[:30]}...'"
            }
        else:
            score = min(95, 65 + match_count * 6)
            return {
                "isValid": True,
                "status": "Accurate & Relevant",
                "score": score,
                "feedback": f"Good answer addressing key domain concepts ({', '.join(found[:4])}).",
                "weaknessFlag": None
            }

    # Generic check for questions without hardcoded criteria:
    # Ensure answer shares semantic relevance with non-trivial question terms
    q_words = set(re.findall(r"\b[a-z]{4,}\b", q_low)) - {
        "walk", "through", "explain", "describe", "about", "what", "when", 
        "which", "would", "your", "this", "time", "last", "flagged", "again"
    }
    overlap = [w for w in q_words if w in ans_low]
    if len(q_words) >= 2 and len(overlap) == 0 and total_words > 10:
        return {
            "isValid": False,
            "status": "Irrelevant / Off-Topic",
            "score": 35,
            "feedback": "Response did not directly address the core terms in the prompt. Align your answer more directly to the question.",
            "weaknessFlag": f"off-topic answer on '{question[:30]}...'"
        }

    return {
        "isValid": True,
        "status": "Relevant",
        "score": 75,
        "feedback": "Response is relevant to the question topic.",
        "weaknessFlag": None
    }


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
    """Manages voice-enabled interview sessions with acoustic telemetry, correctness verification, and memory."""
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
            c_eval = verify_answer_correctness(q, a)

            per_q_tones.append({
                "question": q,
                "answer": a,
                "tone": t_eval,
                "correctness": c_eval
            })

            # Check technical correctness & relevance
            if not c_eval["isValid"] and c_eval.get("weaknessFlag"):
                weak.append(c_eval["weaknessFlag"])
            # Check delivery / fillers
            elif t_eval["confidenceScore"] < 55 or t_eval["fillerCount"] >= 4:
                weak.append(f"vocal delivery on '{q[:30]}...' ({t_eval['toneLabel']}, {t_eval['fillerCount']} fillers)")

        if len(s["answers"]) < len(s["questions"]):
            weak.append("unanswered questions")

        avg_conf = round(sum(p["tone"]["confidenceScore"] for p in per_q_tones) / len(per_q_tones)) if per_q_tones else 50
        avg_wpm = round(sum(p["tone"]["wordsPerMinute"] for p in per_q_tones) / len(per_q_tones)) if per_q_tones else 0
        avg_accuracy = round(sum(p["correctness"]["score"] for p in per_q_tones) / len(per_q_tones)) if per_q_tones else 50
        tot_fillers = sum(p["tone"]["fillerCount"] for p in per_q_tones)
        all_fillers = sorted(list(set(f for p in per_q_tones for f in p["tone"]["fillersDetected"])))

        # Composite overall score taking both content correctness and delivery into account
        overall_score = round(avg_accuracy * 0.65 + avg_conf * 0.35)

        if overall_score >= 80:
            overall_rating = "Strong / Recommended Hire"
        elif overall_score >= 60:
            overall_rating = "Satisfactory with Areas to Improve"
        else:
            overall_rating = "Needs Preparation / Critical Gaps"

        tone_analysis = {
            "overallScore": overall_score,
            "overallRating": overall_rating,
            "contentAccuracyScore": avg_accuracy,
            "vocalConfidenceScore": avg_conf,
            "averageWpm": avg_wpm,
            "totalFillers": tot_fillers,
            "commonFillers": all_fillers,
            "breakdown": per_q_tones,
        }

        fb = {
            "summary": f"{len(s['answers'])} of {len(s['questions'])} answered; {len(weak)} weak area(s). Overall rating: {overall_rating} ({overall_score}/100).",
            "weakAreas": weak,
            "transcriptRef": sid,
            "toneAnalysis": tone_analysis,
        }
        s["feedback"] = fb
        return fb

    def past_feedback(self) -> list:
        return [s["feedback"] for s in self._sessions.values() if "feedback" in s]
