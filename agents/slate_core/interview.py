"""Adaptive mock interviews with a deterministic fallback.

The store is deliberately provider-agnostic. Authenticated serving attaches a
GeminiInterviewCoach; framework-free tests and offline demos keep the fallback.
Only serializable session data is persisted.
"""
import json
import re

from .sample_data import INTERVIEW_QUESTIONS


def _json_object(raw):
    """Accept JSON returned bare or inside a Markdown code fence."""
    text = str(raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("The interview model did not return a JSON object.")
    value = json.loads(text[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("The interview model returned an invalid object.")
    return value


def _strings(value, limit=5):
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:240] for item in value
            if isinstance(item, (str, int, float)) and str(item).strip()][:limit]


class GeminiInterviewCoach:
    """Uses the existing LLMClient interface; the API key stays server-side."""

    def __init__(self, client=None):
        if client is None:
            from .llm import GeminiLLM
            client = GeminiLLM()
        self.client = client

    def first_question(self, role, resume_context, past_feedback):
        prompt = (
            "Act as a skilled, fair hiring interviewer. Start a realistic mock "
            "interview for the target role. Ask exactly one concise, open-ended "
            "question. Personalize it using only the supplied resume facts; do "
            "not assume experience that is not listed. If prior weak areas exist, "
            "revisit one naturally. Return ONLY JSON: "
            '{"question":"...","topic":"..."}.\n\n'
            f"TARGET ROLE: {role}\n"
            f"RESUME FACTS (may be empty): {json.dumps(resume_context or {}, ensure_ascii=False)}\n"
            f"PRIOR WEAK AREAS: {json.dumps(past_feedback, ensure_ascii=False)}"
        )
        data = _json_object(self.client.generate(prompt))
        question = data.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("The interview model did not provide a question.")
        return question.strip()[:1000]

    def evaluate_answer(self, role, question, answer, resume_context,
                        history, followup_used, delivery_metrics=None):
        prompt = (
            "You are a rigorous but constructive interviewer evaluating one "
            "candidate answer. Judge relevance, correctness, reasoning, "
            "specificity, evidence/examples, and communication—not word count "
            "alone. Do not invent candidate achievements or treat resume claims "
            "as independently verified. Give a score from 1 (poor) to 5 "
            "(excellent), concise actionable feedback, strengths and improvements. "
            "If the answer is unclear, incomplete, contradictory, or lacks "
            "evidence, set follow_up_question to one targeted probe. You may "
            "continue probing a follow-up answer when useful; do not impose a "
            "one-follow-up limit. Otherwise set it to null. "
            "You may ask a targeted follow-up to any answer, including an answer "
            "to a previous follow-up, when a human interviewer would probe further. "
            "Do not force a follow-up when the answer is complete. Always provide "
            "the next distinct main interview question as a fallback. Evaluate "
            "delivery separately from content when delivery metrics are supplied. "
            "Do not infer personality, emotion, honesty, or suitability from voice. "
            "Assess only observable mechanics such as pace, pauses, filler words, "
            "volume consistency, and pitch variation. Return ONLY JSON with keys: "
            "score, feedback, strengths, improvements, follow_up_question, "
            "next_question, topic, delivery_score, delivery_feedback, "
            "delivery_strengths, delivery_improvements. "
            "Use arrays for strengths/improvements; strings for other text.\n\n"
            f"TARGET ROLE: {role}\n"
            f"RESUME FACTS: {json.dumps(resume_context or {}, ensure_ascii=False)}\n"
            f"RECENT TRANSCRIPT: {json.dumps(history[-8:], ensure_ascii=False)}\n"
            f"CURRENT QUESTION: {question}\n"
            f"CANDIDATE ANSWER: {answer}\n"
            f"FOLLOW-UP ALREADY USED FOR THIS QUESTION: {str(bool(followup_used)).lower()}\n"
            f"VOICE DELIVERY METRICS (null if unavailable): {json.dumps(delivery_metrics, ensure_ascii=False)}"
        )
        data = _json_object(self.client.generate(prompt))
        try:
            score = int(data.get("score", 3))
        except (TypeError, ValueError):
            score = 3
        score = max(1, min(5, score))
        try:
            delivery_score = int(data.get("delivery_score", 3)) if delivery_metrics else None
        except (TypeError, ValueError):
            delivery_score = 3 if delivery_metrics else None
        if delivery_score is not None:
            delivery_score = max(1, min(5, delivery_score))
        followup = data.get("follow_up_question")
        next_question = data.get("next_question")
        return {
            "score": score,
            "feedback": str(data.get("feedback") or "Answer evaluated.").strip()[:1200],
            "strengths": _strings(data.get("strengths")),
            "improvements": _strings(data.get("improvements")),
            "follow_up_question": followup.strip()[:1000] if isinstance(followup, str) and followup.strip() else None,
            "next_question": next_question.strip()[:1000] if isinstance(next_question, str) and next_question.strip() else None,
            "topic": str(data.get("topic") or "").strip()[:120],
            "delivery_score": delivery_score,
            "delivery_feedback": str(data.get("delivery_feedback") or "").strip()[:1000] if delivery_metrics else "",
            "delivery_strengths": _strings(data.get("delivery_strengths")) if delivery_metrics else [],
            "delivery_improvements": _strings(data.get("delivery_improvements")) if delivery_metrics else [],
        }


class InterviewStore:
    def __init__(self, coach=None):
        self._sessions = {}
        self._n = 0
        self.coach = coach

    @staticmethod
    def _clean_delivery_metrics(value):
        if not isinstance(value, dict):
            return None
        bounds = {
            "durationSeconds": (0, 600), "wordsPerMinute": (0, 600),
            "pauseRatio": (0, 1), "pauseCount": (0, 500),
            "fillerCount": (0, 200), "meanVolume": (0, 1),
            "volumeVariation": (0, 1), "medianPitchHz": (50, 500),
            "pitchRangeHz": (0, 500),
        }
        cleaned = {}
        for key, (low, high) in bounds.items():
            raw = value.get(key)
            if raw is None:
                continue
            try:
                number = float(raw)
            except (TypeError, ValueError):
                continue
            if number == number:
                cleaned[key] = round(max(low, min(high, number)), 3)
        return cleaned or None

    @staticmethod
    def _fallback_review(answer):
        words = len(answer.split())
        score = 1 if words < 12 else 2 if words < 20 else 3 if words < 40 else 4
        if score == 1:
            feedback = "The answer is too brief to demonstrate your reasoning. Add a direct explanation and a concrete example."
            improvements = ["Explain your reasoning", "Add a specific example or result"]
        elif score == 2:
            feedback = "Some detail is present, but the answer needs clearer reasoning and supporting evidence."
            improvements = ["Explain the steps you took", "Include a concrete outcome"]
        else:
            feedback = "The answer has enough detail for a basic review. Check that it directly addresses the question and supports claims with evidence."
            improvements = ["Make the result or impact explicit"]
        return {"score": score, "feedback": feedback, "strengths": [],
                "improvements": improvements, "follow_up_question": None,
                "next_question": None, "topic": ""}

    def start(self, target_role: str, past_feedback: list,
              resume_context=None, mode="text") -> dict:
        self._n += 1
        sid = f"int_{self._n:03d}"
        qs = list(INTERVIEW_QUESTIONS.get(target_role, INTERVIEW_QUESTIONS["default"]))
        carried = list(dict.fromkeys(w for f in past_feedback for w in f.get("weakAreas", [])))
        for w in reversed(carried):
            qs.insert(0, f"Last time this was weak: {w}. Try again.")
        first = qs[0]
        ai_powered = False
        if self.coach is not None:
            try:
                first = self.coach.first_question(target_role, resume_context, carried)
                ai_powered = True
            except Exception:
                pass
        self._sessions[sid] = {
            "role": target_role, "mode": mode, "questions": [first],
            "fallback_questions": qs, "main_index": 0,
            "current_question": first, "current_is_followup": False,
            "followup_used": False, "followup_count": 0,
            "answers": [], "transcript": [], "reviews": [],
            "carried": carried, "resume_context": resume_context or {},
            "ai_powered": ai_powered, "model_turns": 1 if ai_powered else 0,
            "fallback_turns": 0, "done": False, "ended": False,
        }
        return {"sessionId": sid, "firstQuestion": first,
                "carriedFromEarlier": carried, "mode": mode,
                "aiPowered": ai_powered,
                "coachMode": "gemini" if ai_powered else "deterministic_fallback"}

    def _upgrade_legacy_session(self, session):
        """Upgrade sessions persisted by the pre-adaptive interview store in place."""
        if "current_question" in session:
            return
        questions = list(session.get("questions", []))
        answers = list(session.get("answers", []))
        reviews, transcript = [], []
        for question, answer in zip(questions, answers):
            review = self._fallback_review(answer)
            topic = question.split(":")[0].replace("Last time this was weak", "").strip()
            review["topic"] = topic or question[:120]
            review["question"] = question
            review["isFollowUp"] = False
            reviews.append(review)
            transcript.append({"question": question, "answer": answer, "isFollowUp": False})
        session.update({
            "fallback_questions": questions,
            "main_index": len(answers),
            "max_main_questions": len(questions),
            "current_question": questions[len(answers)] if len(answers) < len(questions) else None,
            "followup_used": False, "transcript": transcript, "reviews": reviews,
            "resume_context": {}, "mode": "text", "ai_powered": False,
            "model_turns": 0, "fallback_turns": len(answers),
            "done": len(answers) >= len(questions),
        })

    def answer(self, sid: str, text: str, delivery_metrics=None) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            raise KeyError("session_not_found")
        self._upgrade_legacy_session(s)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("answer_empty")
        if s.get("ended"):
            raise ValueError("interview_ended")

        question = s["current_question"]
        answer = text.strip()[:20000]
        metrics = self._clean_delivery_metrics(delivery_metrics)
        review = None
        if self.coach is not None:
            try:
                try:
                    review = self.coach.evaluate_answer(
                        s["role"], question, answer, s["resume_context"],
                        s["transcript"], s.get("followup_count", 0) > 0, metrics)
                except TypeError:
                    # Backward compatibility for injected coaches using the old interface.
                    review = self.coach.evaluate_answer(
                        s["role"], question, answer, s["resume_context"],
                        s["transcript"], s.get("followup_count", 0) > 0)
                if not isinstance(review, dict):
                    review = None
            except Exception:
                review = None
        if review is None:
            review = self._fallback_review(answer)
            if metrics:
                wpm = float(metrics.get("wordsPerMinute", 0) or 0)
                pause_ratio = float(metrics.get("pauseRatio", 0) or 0)
                fillers = int(metrics.get("fillerCount", 0) or 0)
                words = max(1, len(answer.split()))
                delivery_score = 3
                if 100 <= wpm <= 170:
                    delivery_score += 1
                elif wpm < 70 or wpm > 210:
                    delivery_score -= 1
                if fillers / words > 0.06:
                    delivery_score -= 1
                if pause_ratio > 0.55 or pause_ratio < 0.03:
                    delivery_score -= 1
                review.update({
                    "delivery_score": max(1, min(5, delivery_score)),
                    "delivery_feedback": "Rule-based estimate from pace, pauses, filler-word frequency and volume activity. Treat this as coaching guidance, not a personality or confidence assessment.",
                    "delivery_strengths": [],
                    "delivery_improvements": ["Aim for a steady, conversational pace" if wpm < 100 or wpm > 170 else "Maintain this speaking pace",
                                              "Reduce repeated filler words" if fillers / words > 0.06 else "Keep filler words limited"],
                })
            s["fallback_turns"] += 1
        else:
            s["model_turns"] += 1
            s["ai_powered"] = True

        is_followup = bool(s.get("current_is_followup"))
        normalized = {
            "score": max(1, min(5, int(review.get("score", 3)))),
            "feedback": str(review.get("feedback") or "").strip(),
            "strengths": _strings(review.get("strengths")),
            "improvements": _strings(review.get("improvements")),
            "topic": str(review.get("topic") or "").strip()[:120],
            "deliveryScore": review.get("delivery_score"),
            "deliveryFeedback": str(review.get("delivery_feedback") or "").strip(),
            "deliveryStrengths": _strings(review.get("delivery_strengths")),
            "deliveryImprovements": _strings(review.get("delivery_improvements")),
            "deliveryMetrics": metrics,
        }
        s["transcript"].append({"question": question, "answer": answer,
                                "isFollowUp": is_followup,
                                "deliveryMetrics": metrics})
        s["answers"].append(answer)
        s["reviews"].append({**normalized, "question": question,
                             "isFollowUp": is_followup})

        followup = review.get("follow_up_question")
        if isinstance(followup, str) and followup.strip():
            s["followup_used"] = True
            s["followup_count"] = s.get("followup_count", 0) + 1
            s["current_question"] = followup.strip()[:1000]
            s["current_is_followup"] = True
            s["questions"].append(s["current_question"])
            return {"done": False, "nextQuestion": s["current_question"],
                    "isFollowUp": True, "evaluation": normalized,
                    "aiPowered": s["ai_powered"]}

        s["main_index"] += 1
        s["followup_used"] = False
        s["followup_count"] = 0
        s["current_is_followup"] = False
        next_question = review.get("next_question")
        if not isinstance(next_question, str) or not next_question.strip() or next_question.strip() == question:
            fallback = s["fallback_questions"]
            next_question = fallback[s["main_index"] % len(fallback)]
        s["current_question"] = next_question.strip()[:1000]
        s["questions"].append(s["current_question"])
        return {"done": False, "nextQuestion": s["current_question"],
                "isFollowUp": False, "evaluation": normalized,
                "aiPowered": s["ai_powered"]}

    def end(self, sid: str) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            raise KeyError("session_not_found")
        self._upgrade_legacy_session(s)
        s["ended"] = True
        s["done"] = True
        return self.feedback(sid)

    def feedback(self, sid: str) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            raise KeyError("session_not_found")
        self._upgrade_legacy_session(s)
        reviews = s.get("reviews", [])
        weak = []
        strengths, improvements = [], []
        for item in reviews:
            topic = item.get("topic") or item["question"].split(":")[0]
            if item.get("score", 3) <= 2:
                weak.append(topic.strip() or item["question"])
            strengths.extend(item.get("strengths", []))
            improvements.extend(item.get("improvements", []))
        if not s.get("ended") and len(s["answers"]) < len(s["questions"]):
            weak.append("interview still in progress")
        scores = [r["score"] for r in reviews]
        average = round(sum(scores) / len(scores), 1) if scores else 0
        delivery_scores = [r["deliveryScore"] for r in reviews
                           if isinstance(r.get("deliveryScore"), (int, float))]
        average_delivery = (round(sum(delivery_scores) / len(delivery_scores), 1)
                            if delivery_scores else None)
        mode = ("gemini" if s["ai_powered"] and not s["fallback_turns"] else
                "mixed" if s["ai_powered"] else "deterministic_fallback")
        fb = {
            "summary": f"{len(s['answers'])} answer(s) recorded; average answer score {average}/5.",
            "weakAreas": list(dict.fromkeys(weak)),
            "transcriptRef": sid,
            "averageScore": average,
            "averageDeliveryScore": average_delivery,
            "strengths": list(dict.fromkeys(strengths))[:8],
            "improvements": list(dict.fromkeys(improvements))[:8],
            "answerReviews": reviews,
            "answeredCount": len(s["answers"]),
            "mode": s.get("mode", "text"),
            "aiPowered": bool(s["ai_powered"]),
            "coachMode": mode,
            "ended": bool(s.get("ended")),
        }
        s["feedback"] = fb
        return fb

    def past_feedback(self) -> list:
        return [s["feedback"] for s in self._sessions.values() if "feedback" in s]
