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


def _role_questions(role):
    """Resolve common role-name variants without silently treating HR as a tech role."""
    normalized = re.sub(r"[^a-z0-9]+", " ", str(role or "").lower()).strip()
    if normalized in {"hr", "human relations", "human resource", "human resources",
                      "hr generalist", "hr executive", "human resource management"}:
        return list(INTERVIEW_QUESTIONS["Human Resources"])
    for key, questions in INTERVIEW_QUESTIONS.items():
        if key == "default":
            continue
        if re.sub(r"[^a-z0-9]+", " ", key.lower()).strip() == normalized:
            return list(questions)
    return list(INTERVIEW_QUESTIONS["default"])


def _question_seen(candidate, asked):
    """Reject exact repeats and near-identical wording from a model or fallback."""
    words = set(re.findall(r"[a-z0-9]+", str(candidate or "").lower()))
    if not words:
        return True
    for previous in asked:
        prior = set(re.findall(r"[a-z0-9]+", str(previous or "").lower()))
        if words == prior:
            return True
        if len(words & prior) / max(1, len(words | prior)) >= 0.82:
            return True
    return False


def _fallback_next_question(session):
    """Select an unused prompt; after the bank, vary the scenario rather than loop."""
    asked = session.get("questions", [])
    bank = session.get("fallback_questions") or INTERVIEW_QUESTIONS["default"]
    for question in bank:
        if not _question_seen(question, asked):
            return question
    role = session.get("role", "this role")
    angles = [
        "Consider the same responsibility when you have very limited time.",
        "Now consider a case where the people involved strongly disagree.",
        "How would your approach change if the first solution did not work?",
        "What would you do if important information was missing?",
        "How would you handle this if the decision affected several stakeholders?",
        "What would you measure afterwards to check whether your approach worked?",
        "How would you explain your decision to someone who disagreed with it?",
        "What risks would you look for before taking action?",
    ]
    index = max(0, len(asked) - len(bank))
    base = bank[index % len(bank)]
    angle = angles[index % len(angles)]
    candidate = f"{angle} {base}"
    # This suffix guarantees a distinct prompt even after all angle/base pairs.
    generation = index // len(angles) + 1
    if generation > 1:
        candidate = f"{candidate} (alternative scenario {generation})"
    return candidate


class GeminiInterviewCoach:
    """Uses the existing LLMClient interface; the API key stays server-side."""

    def __init__(self, client=None):
        if client is None:
            from .llm import GeminiLLM
            client = GeminiLLM()
        self.client = client

    def first_question(self, role, resume_context, past_feedback):
        prompt = (
            "Act as a skilled human hiring interviewer who understands the actual work of the target role. "
            "Ask exactly one concise, natural, role-specific opening question. "
            "Do not use generic software-project questions unless the target role is a software/technical role. "
            "For HR or human-relations roles, focus on recruitment, employee relations, conflict handling, "
            "confidentiality, onboarding, policy, performance processes, fairness and stakeholder communication. "
            "Use resume facts only when relevant; never assume experience that is not listed. "
            "If prior weak areas exist, revisit one naturally. Return ONLY JSON: "
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
            "You are a thoughtful, role-specialist human interviewer reviewing one candidate answer. "
            "Evaluate whether the answer addresses the exact question and demonstrates sound judgement for the TARGET ROLE. "
            "Do not use a generic rubric across unrelated professions. For HR/human-relations roles, assess fairness, "
            "confidentiality, listening, policy awareness, documentation, practical judgement, employee impact and "
            "appropriate escalation; do not reward irrelevant technical-project detail. "
            "Do not invent candidate achievements or treat resume claims as verified. "
            "Give a 1-5 score and feedback tied to specific details in the answer. "
            "Improvements MUST be concrete: name what was missing, why it matters in this role, and what detail/action "
            "the candidate should add. Avoid vague advice such as 'make the impact explicit' unless you say what impact "
            "to quantify or explain. "
            "Ask a follow-up only when it naturally arises from something the candidate actually said or omitted. "
            "A follow-up must refer to a specific detail, ambiguity, decision or consequence in their answer; "
            "never ask an unrelated stock question or repeat an earlier question. You may chain follow-ups, but "
            "do not probe merely for the sake of it. If no meaningful probe remains, set follow_up_question to null. "
            "Always propose a distinct next main question that has not appeared in the transcript. "
            "Evaluate voice delivery separately from content when metrics are supplied. "
            "Do not infer personality, emotion, honesty, or suitability from voice. "
            "Assess only observable mechanics such as pace, pauses, filler words, "
            "volume consistency, and pitch variation. Return ONLY JSON with keys: "
            "score, feedback, strengths, improvements, follow_up_question, "
            "next_question, topic, delivery_score, delivery_feedback, "
            "delivery_strengths, delivery_improvements. "
            "Use arrays for strengths/improvements; strings for other text.\n\n"
            f"TARGET ROLE: {role}\n"
            f"RESUME FACTS: {json.dumps(resume_context or {}, ensure_ascii=False)}\n"
            f"RECENT TRANSCRIPT: {json.dumps(history[-12:], ensure_ascii=False)}\n"
            f"QUESTIONS ALREADY ASKED (do not repeat or paraphrase): {json.dumps([x.get('question', '') for x in history], ensure_ascii=False)}\n"
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
    def _fallback_review(role, question, answer, allow_followup=True):
        """Transparent offline review with role-aware prompts and actionable coaching."""
        words = len(answer.split())
        low_q, low_a = question.lower(), answer.lower()
        score = 1 if words < 12 else 2 if words < 25 else 3 if words < 55 else 4
        is_hr = any(term in str(role).lower() for term in ("human", "hr", "people", "personnel"))
        if is_hr:
            if any(term in low_q for term in ("confidential", "sensitive", "complaint", "unfair treatment")):
                focus = "Explain how you would listen without promising absolute secrecy, record facts objectively, limit access to the information, and escalate under the organisation's process."
                probe = "You mentioned handling the concern. What would you tell the employee about confidentiality, and who would need to be involved if the allegation required formal action?"
            elif any(term in low_q for term in ("hiring", "recruit", "candidate", "vacancy", "interview")):
                focus = "Name the job-related selection criteria, how you would align the hiring manager, and how you would keep candidate evaluation consistent."
                probe = "What specific criteria would you agree with the hiring manager, and how would you make sure every candidate is assessed against the same standard?"
            elif any(term in low_q for term in ("conflict", "disagreement", "upset", "manager", "employee")):
                focus = "Describe how you would hear each perspective separately, check facts rather than take sides, agree next steps, and follow up."
                probe = "What would you do if the two people gave you conflicting accounts, and how would you decide what to do next?"
            elif any(term in low_q for term in ("onboarding", "new hire")):
                focus = "Set out the immediate support you would provide, who owns each onboarding task, and how you would check the new hire is settling in."
                probe = "How would you check after the first week that the new hire understands their responsibilities and has the support they need?"
            else:
                focus = "Explain the first action you would take, the policy or evidence you would consult, who you would involve, and how you would follow up."
                probe = "What would be your first practical step, and what information would you need before deciding how to proceed?"
        else:
            focus = "Connect your approach to the role: explain the steps you took, the reason for choosing them, and the evidence or outcome you used to judge success."
            probe = "What was the most important decision you made, and what evidence showed whether it worked?"
        if words < 25:
            feedback = "There is not yet enough detail to assess your judgement. The answer needs a clearer sequence of actions and a reason for those actions."
            improvements = [focus, "Add one specific example or realistic step-by-step scenario rather than describing your approach in general terms."]
        elif words < 55:
            feedback = "You have started to address the question, but the answer needs more role-specific reasoning and a clearer explanation of how you would handle the situation."
            improvements = [focus]
        else:
            feedback = "The answer has enough detail for an initial review. Strengthen it by making the decision process and follow-through explicit."
            improvements = [focus]
        followup = probe if allow_followup and words < 85 else None
        return {"score": score, "feedback": feedback, "strengths": [],
                "improvements": improvements, "follow_up_question": followup,
                "next_question": None, "topic": str(question)[:120]}

    def start(self, target_role: str, past_feedback: list,
              resume_context=None, mode="text") -> dict:
        self._n += 1
        sid = f"int_{self._n:03d}"
        qs = _role_questions(target_role)
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
            review = self._fallback_review(
                s["role"], question, answer,
                allow_followup=(s.get("followup_count", 0) == 0))
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

        asked_questions = [item.get("question", "") for item in s["transcript"]]
        followup = review.get("follow_up_question")
        if (isinstance(followup, str) and followup.strip()
                and not _question_seen(followup, asked_questions)):
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
        if (not isinstance(next_question, str) or not next_question.strip()
                or _question_seen(next_question, asked_questions)):
            next_question = _fallback_next_question(s)
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
