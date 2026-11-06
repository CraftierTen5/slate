from .sample_data import INTERVIEW_QUESTIONS

class InterviewStore:
    def __init__(self):
        self._sessions = {}
        self._n = 0

    def start(self, target_role: str, past_feedback: list) -> dict:
        self._n += 1
        sid = f"int_{self._n:03d}"
        qs = list(INTERVIEW_QUESTIONS.get(target_role, INTERVIEW_QUESTIONS["default"]))
        # memory: revisit weak areas from earlier sessions first
        for w in reversed([w for f in past_feedback for w in f["weakAreas"]]):
            qs.insert(0, f"Last time this was weak: {w}. Try again.")
        self._sessions[sid] = {"role": target_role, "questions": qs, "answers": [], "carried": [w for f in past_feedback for w in f["weakAreas"]]}
        return {"sessionId": sid, "firstQuestion": qs[0], "carriedFromEarlier": self._sessions[sid]["carried"]}

    def answer(self, sid: str, text: str) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            raise KeyError("session_not_found")
        s["answers"].append(text)
        i = len(s["answers"])
        return {"done": i >= len(s["questions"]), "nextQuestion": s["questions"][i] if i < len(s["questions"]) else None}

    def feedback(self, sid: str) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            raise KeyError("session_not_found")
        weak = []
        for q, a in zip(s["questions"], s["answers"]):
            if len(a.split()) < 12:  # thin answer: simple, explainable rule
                weak.append(q.split(":")[0].replace("Last time this was weak", "").strip() or q)
        if len(s["answers"]) < len(s["questions"]):
            weak.append("unanswered questions")
        fb = {"summary": f"{len(s['answers'])} of {len(s['questions'])} answered; {len(weak)} weak area(s).",
              "weakAreas": weak, "transcriptRef": sid}
        s["feedback"] = fb
        return fb

    def past_feedback(self) -> list:
        return [s["feedback"] for s in self._sessions.values() if "feedback" in s]
