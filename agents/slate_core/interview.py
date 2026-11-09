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
                        history, followup_used):
        prompt = (
            "You are a rigorous but constructive interviewer evaluating one "
            "candidate answer. Judge relevance, correctness, reasoning, "
            "specificity, evidence/examples, and communication—not word count "
            "alone. Do not invent candidate achievements or treat resume claims "
            "as independently verified. Give a score from 1 (poor) to 5 "
            "(excellent), concise actionable feedback, strengths and improvements. "
            "If the answer is unclear, incomplete, or lacks evidence and no "
            "follow-up has yet been asked for this main question, set "
            "follow_up_question to one targeted probe. Otherwise set it to null. "
            "Always provide the next distinct main interview question. Return "
            "ONLY JSON with keys: score, feedback, strengths, improvements, "
            "follow_up_question, next_question, topic. "
            "Use arrays for strengths/improvements; strings for other text.\n\n"
            f"TARGET ROLE: {role}\n"
            f"RESUME FACTS: {json.dumps(resume_context or {}, ensure_ascii=False)}\n"
            f"RECENT TRANSCRIPT: {json.dumps(history[-8:], ensure_ascii=False)}\n"
            f"CURRENT QUESTION: {question}\n"
            f"CANDIDATE ANSWER: {answer}\n"
            f"FOLLOW-UP ALREADY USED FOR THIS QUESTION: {str(bool(followup_used)).lower()}"
        )
        data = _json_object(self.client.generate(prompt))
        try:
            score = int(data.get("score", 3))
        except (TypeError, ValueError):
            score = 3
        score = max(1, min(5, score))
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
        }


class InterviewStore:
    def __init__(self, coach=None):
        self._sessions = {}
        self._n = 0
        self.coach = coach

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
        # Preserve the old, explainable offline behavior and make prior weak
        # areas explicit when no model is configured or available.
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
            "max_main_questions": max(1, len(qs)), "current_question": first,
            "followup_used": False, "answers": [], "transcript": [],
            "reviews": [], "carried": carried, "resume_context": resume_context or {},
            "ai_powered": ai_powered, "model_turns": 1 if ai_powered else 0,
            "fallback_turns": 0,
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

    def answer(self, sid: str, text: str) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            raise KeyError("session_not_found")
        self._upgrade_legacy_session(s)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("answer_empty")
        if s.get("done"):
            raise ValueError("interview_complete")

        question = s["current_question"]
        answer = text.strip()[:20000]
        review = None
        if self.coach is not None:
            try:
                review = self.coach.evaluate_answer(
                    s["role"], question, answer, s["resume_context"],
                    s["transcript"], s["followup_used"])
                if not isinstance(review, dict):
                    review = None
            except Exception:
                review = None
        if review is None:
            review = self._fallback_review(answer)
            s["fallback_turns"] += 1
        else:
            s["model_turns"] += 1
            s["ai_powered"] = True

        is_followup = bool(s["followup_used"])
        normalized = {
            "score": max(1, min(5, int(review.get("score", 3)))),
            "feedback": str(review.get("feedback") or "").strip(),
            "strengths": _strings(review.get("strengths")),
            "improvements": _strings(review.get("improvements")),
            "topic": str(review.get("topic") or "").strip()[:120],
        }
        s["transcript"].append({"question": question, "answer": answer,
                                "isFollowUp": is_followup})
        s["answers"].append(answer)
        s["reviews"].append({**normalized, "question": question,
                             "isFollowUp": is_followup})

        followup = review.get("follow_up_question")
        if (not is_followup and isinstance(followup, str)
                and followup.strip()):
            s["followup_used"] = True
            s["current_question"] = followup.strip()[:1000]
            s["questions"].append(s["current_question"])
            return {"done": False, "nextQuestion": s["current_question"],
                    "isFollowUp": True, "evaluation": normalized,
                    "aiPowered": s["ai_powered"]}

        s["main_index"] += 1
        s["followup_used"] = False
        if s["main_index"] >= s["max_main_questions"]:
            s["done"] = True
            return {"done": True, "nextQuestion": None,
                    "isFollowUp": False, "evaluation": normalized,
                    "aiPowered": s["ai_powered"]}

        next_question = review.get("next_question")
        if not isinstance(next_question, str) or not next_question.strip() or next_question.strip() == question:
            next_question = s["fallback_questions"][s["main_index"]]
        s["current_question"] = next_question.strip()[:1000]
        s["questions"].append(s["current_question"])
        return {"done": False, "nextQuestion": s["current_question"],
                "isFollowUp": False, "evaluation": normalized,
                "aiPowered": s["ai_powered"]}

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
        if len(s["answers"]) < len(s["questions"]) and not s.get("done"):
            weak.append("unanswered questions")
        scores = [r["score"] for r in reviews]
        average = round(sum(scores) / len(scores), 1) if scores else 0
        mode = ("gemini" if s["ai_powered"] and not s["fallback_turns"] else
                "mixed" if s["ai_powered"] else "deterministic_fallback")
        fb = {
            "summary": f"{len(s['answers'])} answer(s) recorded; average answer score {average}/5.",
            "weakAreas": list(dict.fromkeys(weak)),
            "transcriptRef": sid,
            "averageScore": average,
            "strengths": list(dict.fromkeys(strengths))[:8],
            "improvements": list(dict.fromkeys(improvements))[:8],
            "answerReviews": reviews,
            "answeredCount": len(s["answers"]),
            "mode": s.get("mode", "text"),
            "aiPowered": bool(s["ai_powered"]),
            "coachMode": mode,
        }
        s["feedback"] = fb
        return fb

    def past_feedback(self) -> list:
        return [s["feedback"] for s in self._sessions.values() if "feedback" in s]
