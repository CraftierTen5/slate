from .sample_data import INTERVIEW_QUESTIONS
from .gemini_interview import GeminiInterviewCoach


class InterviewStore:
    def __init__(self, coach=None):
        self._sessions = {}
        self._n = 0
        self.coach = coach or GeminiInterviewCoach()

    def start(self, target_role: str, past_feedback: list, resume=None) -> dict:
        self._n += 1
        sid = f"int_{self._n:03d}"
        qs = list(INTERVIEW_QUESTIONS.get(target_role, INTERVIEW_QUESTIONS["default"]))
        carried = [w for f in past_feedback for w in f.get("weakAreas", [])]
        # Preserve the existing cross-session memory behavior.
        if carried:
            qs.insert(0, f"Last time this was weak: {carried[-1]}. Try again.")
        first = self.coach.opening_question(target_role, resume, carried) if not carried else None
        first = first or qs[0]
        self._sessions[sid] = {"role": target_role, "questions": qs, "answers": [],
            "evaluations": [], "carried": carried, "resume": resume or {},
            "current_question": first, "question_index": 0, "followup_used": False,
            "finished": False}
        return {"sessionId": sid, "firstQuestion": first, "carriedFromEarlier": carried}

    def answer(self, sid: str, text: str) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            raise KeyError("session_not_found")
        if s["finished"]:
            raise ValueError("interview_already_finished")
        answer = (text or "").strip()
        if not answer:
            raise ValueError("answer_empty")
        question = s["current_question"]
        review = self.coach.review_answer(s["role"], question, answer, s["resume"],
                                          s["answers"], not s["followup_used"])
        if not review:
            words = len(answer.split())
            review = {"score": 2 if words < 12 else 3,
                "assessment": "Fallback assessment: length is only a basic signal. Add a concrete example and explain your reasoning.",
                "strengths": [], "improvements": ["Add specific reasoning or an example."],
                "follow_up_question": None}
        s["answers"].append({"question": question, "answer": answer})
        s["evaluations"].append(review)
        followup = review.get("follow_up_question") if not s["followup_used"] else None
        if followup:
            s["current_question"] = followup
            s["followup_used"] = True
            return {"done": False, "nextQuestion": followup, "evaluation": review, "isFollowUp": True}
        s["question_index"] += 1
        s["followup_used"] = False
        if s["question_index"] >= len(s["questions"]):
            s["finished"] = True
            return {"done": True, "nextQuestion": None, "evaluation": review, "isFollowUp": False}
        planned = s["questions"][s["question_index"]]
        next_q = self.coach.opening_question(s["role"], s["resume"],
                    ["Ask about this planned topic: " + planned,
                     "Prior answers: " + str(s["answers"])]) or planned
        s["current_question"] = next_q
        return {"done": False, "nextQuestion": next_q, "evaluation": review, "isFollowUp": False}

    def feedback(self, sid: str) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            raise KeyError("session_not_found")
        weak = []
        for item, review in zip(s["answers"], s["evaluations"]):
            if review.get("score", 3) <= 2 or review.get("improvements"):
                weak.append(item["question"])
        if not s["finished"]:
            weak.append("unanswered questions")
        scores = [x.get("score", 3) for x in s["evaluations"]]
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        strengths = list(dict.fromkeys(x for e in s["evaluations"] for x in e.get("strengths", [])))
        improvements = list(dict.fromkeys(x for e in s["evaluations"] for x in e.get("improvements", [])))
        fb = {"summary": f"{len(s['answers'])} answer(s) reviewed; average answer score {avg}/5.",
              "weakAreas": weak, "transcriptRef": sid, "averageScore": avg,
              "strengths": strengths[:8], "improvements": improvements[:8],
              "answerReviews": s["evaluations"]}
        s["feedback"] = fb
        return fb

    def past_feedback(self) -> list:
        return [s["feedback"] for s in self._sessions.values() if "feedback" in s]
