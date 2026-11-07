"""Voice-based mock interview, vocal tone analysis, answer correctness verification,
dynamic enterprise question sampling, and adaptive human-like follow-ups for Slate.

Zero-cost, completely local and deterministic. Evaluates candidate voice tone,
speaking pace (WPM), filler words, acoustic projection (RMS volume), delivery confidence,
and substantive technical correctness and relevance to the question, with interactive follow-up probing.
"""
import re
import random
from .sample_data import INTERVIEW_QUESTIONS as BASE_QUESTIONS

COMMON_FILLERS = [
    "um", "uh", "er", "ah", "like", "you know", "basically", 
    "actually", "sort of", "kind of", "so yeah", "i mean"
]

# Comprehensive Enterprise Question Bank across roles & categories
EXPANDED_QUESTION_BANK = {
    "Data Analyst": [
        "Walk me through a SQL query you wrote to answer a complex business question.",
        "How would you check a dataset for anomalies, nulls, and bad data before analysing it?",
        "Explain the difference between mean and median and give an example of when each misleads.",
        "How do you decide between an inner join, a left join, and a full outer join when combining transactional tables?",
        "If a critical business KPI like daily active users dropped by fifteen percent overnight, how would you investigate the root cause?",
        "Explain the difference between correlation and causation with a real-world data analysis scenario.",
        "When working with skewed data distributions, how do you handle extreme outliers in reporting and modeling?",
        "How do you structure an executive dashboard so leadership can make immediate, actionable decisions?"
    ],
    "Backend Developer": [
        "How do you structure database queries and indexing to prevent API latency bottlenecks under high traffic?",
        "Explain how you handle authentication, authorization, and secure session management in a modern REST API.",
        "Walk me through how you design an idempotent endpoint, particularly for payment or order processing.",
        "How do you approach error handling, logging, and observability when debugging production backend services?",
        "What strategies do you use for database connection pooling, transactions, and preventing race conditions?",
        "Explain your strategy for caching with Redis, including cache invalidation and cache stampede prevention."
    ],
    "Frontend Developer": [
        "How do you optimize state management, component re-renders, and bundle sizes in a large React application?",
        "How do you handle responsive design and layout stability across diverse mobile and desktop screen sizes?",
        "Explain how you ensure web accessibility, keyboard navigation, and semantic HTML in complex UI components.",
        "How do you handle asynchronous data fetching, error boundaries, and loading states in client-side applications?",
        "What strategies do you use for caching API responses and managing client-side offline capabilities?"
    ],
    "default": [
        "Tell me about a complex project you built, the technical trade-offs you made, and what you would change today.",
        "Describe a time you encountered a critical production bug or blocker and how you diagnosed and fixed it.",
        "Tell me about a time you had a technical disagreement with a teammate and how you resolved it constructively.",
        "Why this role and how does it fit into your engineering growth trajectory?"
    ]
}

QUESTION_CRITERIA = {
    "sql": {
        "topics": [
            "sql", "query", "select", "join", "group by", "where", "having", 
            "sum", "count", "avg", "table", "database", "orders", "customers", 
            "revenue", "filter", "aggregate", "metric", "window", "cte", "index"
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
    "join": {
        "topics": [
            "inner", "left", "outer", "full", "right", "match", "keys", "table", "null", "rows", "unmatched"
        ],
        "min_matches": 2,
        "hint": "Explain how inner joins retain only matches whereas left/outer joins preserve non-matching rows with nulls."
    },
    "dropped": {
        "topics": [
            "investigate", "segment", "funnel", "breakdown", "platform", "version", "logs", "metrics", "cohort", "tracking"
        ],
        "min_matches": 2,
        "hint": "Outline a root-cause breakdown by segmenting across devices, release versions, user cohorts, and tracking telemetry."
    },
    "indexing": {
        "topics": [
            "index", "b-tree", "query", "execution plan", "explain", "scan", "latency", "composite", "bottleneck"
        ],
        "min_matches": 2,
        "hint": "Discuss execution plans, index lookups, composite indexing on filter/join columns, and reducing full table scans."
    },
    "authentication": {
        "topics": [
            "jwt", "token", "oauth", "session", "bearer", "hash", "bcrypt", "rbac", "role", "header", "https", "refresh"
        ],
        "min_matches": 2,
        "hint": "Discuss JWT tokens, secure HTTP-only cookies, OAuth2, role-based authorization, and password hashing."
    },
    "idempotent": {
        "topics": [
            "idempotency", "key", "token", "retry", "uuid", "transaction", "header", "duplicate", "payment"
        ],
        "min_matches": 2,
        "hint": "Explain using unique idempotency keys in request headers and atomic database transactions to safely retry operations."
    },
    "react": {
        "topics": [
            "memo", "usecallback", "usememo", "state", "context", "redux", "bundle", "code-splitting", "lazy", "render"
        ],
        "min_matches": 2,
        "hint": "Discuss component memoization, selective state placement, lazy loading, and avoiding unnecessary re-renders."
    },
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

    # Generic check for questions without hardcoded criteria
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


def generate_followup_question(question: str, answer: str, correctness_eval: dict) -> str:
    """Generate an adaptive interviewer follow-up question based on candidate's answer."""
    ans_low = (answer or "").lower()
    q_low = (question or "").lower()

    # 1. If off-topic or shallow, politely challenge candidate to provide specific technical substance
    if not correctness_eval["isValid"]:
        if "incomplete" in correctness_eval["status"].lower():
            return "Could you elaborate a bit more on that? Walk me through a concrete technical example from your actual experience."
        else:
            return f"Understood, but let's connect that back to the core question: {correctness_eval['feedback']} How would you address that specifically?"

    # 2. Topic-specific technical deep dives based on candidate's specific terms
    if "sql" in q_low:
        if "join" in ans_low or "group" in ans_low:
            return "Good. If that joined table grew to fifty million records, how would you optimize the indexing and query execution to prevent bottlenecks?"
        elif "window" in ans_low or "cte" in ans_low:
            return "Nice use of window functions or CTEs. What are the memory or execution plan trade-offs when using CTEs versus subqueries or temporary tables?"
        else:
            return "How would you handle edge cases like null values or missing customer records in that query without skewing the aggregate totals?"

    if "bad data" in q_low or "dataset" in q_low or "anomalies" in q_low:
        if "outlier" in ans_low or "skew" in ans_low:
            return "When you detect those outliers, what criteria do you use to decide whether to drop them, cap them, or apply a mathematical transformation?"
        elif "null" in ans_low or "missing" in ans_low:
            return "When imputing missing values, how do you decide between forward-fill, mean or median imputation, or flagging them as a separate category?"
        else:
            return "How would you automate those data validation checks so anomalies are caught in a data pipeline before reaching production dashboards?"

    if "mean" in q_low and "median" in q_low:
        if "salary" in ans_low or "income" in ans_low or "outlier" in ans_low:
            return "Exactly. Can you describe a real-world business scenario where relying only on the median might also mislead leadership by masking total volume?"
        else:
            return "Could you give a concrete business metric where you would deliberately present both the mean and the median to stakeholders?"

    if "join" in q_low:
        return "What are the performance implications of joining on non-indexed text columns versus integer foreign keys?"

    if "dropped" in q_low or "kpi" in q_low:
        return "If you discovered the drop was concentrated entirely on Android devices, what would be your immediate next debugging step?"

    if "indexing" in q_low or "latency" in q_low:
        return "What are the trade-offs of adding too many indexes on a write-heavy database table?"

    if "authentication" in q_low or "authorization" in q_low:
        return "How do you handle JWT revocation or logout securely before the token reaches its expiration timestamp?"

    if "project" in q_low:
        if "database" in ans_low or "api" in ans_low or "architecture" in ans_low:
            return "What was the most difficult production bottleneck or bug you encountered in that project, and how did you diagnose and resolve it?"
        else:
            return "If you had two more weeks to work on that architecture, what is the single biggest technical refactor or improvement you would prioritize?"

    if "stuck" in q_low:
        return "What did that experience teach you about designing systems or testing upfront to prevent similar blockers from recurring?"

    if "why this role" in q_low:
        return "How do you see this role aligning with the specific technical skills and impact you want to achieve over the next year?"

    # Contextual keywords in answer
    if "test" in ans_low or "testing" in ans_low:
        return "What was your automated testing strategy to make sure edge cases and regressions were caught?"
    elif "user" in ans_low or "client" in ans_low:
        return "How did feedback or latency requirements from real users influence how you architected that solution?"

    return "That's insightful. Could you walk me through one specific edge case or challenge you had to solve while implementing that?"


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
    """Manages voice-enabled interview sessions with dynamic question sampling, follow-ups, and memory."""
    def __init__(self):
        self._sessions = {}
        self._n = 0
        self._recent_questions = []

    def start(self, target_role: str, past_feedback: list = None, question_count: int = 3) -> dict:
        self._n += 1
        sid = f"voice_int_{self._n:03d}"
        past_feedback = past_feedback or []

        # Get pool of questions for role
        role_pool = EXPANDED_QUESTION_BANK.get(target_role) or EXPANDED_QUESTION_BANK["default"]
        
        # Adaptive memory: carry forward prior weak areas first
        carried = [w for f in past_feedback for w in f.get("weakAreas", [])]
        selected_questions = []
        for w in reversed(carried):
            selected_questions.insert(0, f"Last time this was flagged: {w}. Walk me through this again.")

        # Dynamically sample remaining questions to avoid repetitiveness
        needed = max(1, question_count - len(selected_questions))
        available = [q for q in role_pool if q not in self._recent_questions and q not in selected_questions]
        if len(available) < needed:
            available = [q for q in role_pool if q not in selected_questions] or role_pool

        sampled = random.sample(available, min(needed, len(available)))
        selected_questions.extend(sampled)

        # Track recent questions to rotate on future sessions
        for q in sampled:
            self._recent_questions.append(q)
        if len(self._recent_questions) > 10:
            self._recent_questions = self._recent_questions[-10:]

        self._sessions[sid] = {
            "role": target_role,
            "mode": "voice",
            "coreQuestions": selected_questions,
            "currentCoreIndex": 0,
            "inFollowup": False,
            "currentPrompt": selected_questions[0],
            "dialogue": [],
            "carried": carried,
        }
        return {
            "sessionId": sid,
            "firstQuestion": selected_questions[0],
            "totalQuestions": len(selected_questions),
            "carriedFromEarlier": carried,
            "mode": "voice",
            "isFollowup": False,
        }

    def answer(self, sid: str, text: str, tone_data: dict = None) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            raise KeyError("session_not_found")

        q_text = s["currentPrompt"]
        t_eval = analyze_voice_tone(text, tone_data)
        c_eval = verify_answer_correctness(q_text, text)

        is_followup = s["inFollowup"]
        s["dialogue"].append({
            "question": q_text,
            "answer": text,
            "tone": t_eval,
            "correctness": c_eval,
            "isFollowup": is_followup,
            "coreIndex": s["currentCoreIndex"]
        })

        if not is_followup:
            followup = generate_followup_question(q_text, text, c_eval)
            s["inFollowup"] = True
            s["currentPrompt"] = followup
            return {
                "done": False,
                "isFollowup": True,
                "nextQuestion": followup,
                "interviewerTransition": "Thanks. Let me ask a follow-up on that:",
                "questionNumber": s["currentCoreIndex"] + 1,
                "totalQuestions": len(s["coreQuestions"]),
            }
        else:
            s["inFollowup"] = False
            s["currentCoreIndex"] += 1
            if s["currentCoreIndex"] < len(s["coreQuestions"]):
                next_q = s["coreQuestions"][s["currentCoreIndex"]]
                s["currentPrompt"] = next_q
                return {
                    "done": False,
                    "isFollowup": False,
                    "nextQuestion": next_q,
                    "interviewerTransition": "Thank you. Let's move on to the next topic:",
                    "questionNumber": s["currentCoreIndex"] + 1,
                    "totalQuestions": len(s["coreQuestions"]),
                }
            else:
                return {
                    "done": True,
                    "isFollowup": False,
                    "nextQuestion": None,
                    "questionNumber": len(s["coreQuestions"]),
                    "totalQuestions": len(s["coreQuestions"]),
                }

    def feedback(self, sid: str) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            raise KeyError("session_not_found")

        weak = []
        dialogue = s.get("dialogue", [])

        for item in dialogue:
            c = item["correctness"]
            t = item["tone"]
            q = item["question"]

            if not c["isValid"] and c.get("weaknessFlag"):
                weak.append(c["weaknessFlag"])
            elif t["confidenceScore"] < 55 or t["fillerCount"] >= 4:
                weak.append(f"vocal delivery on '{q[:30]}...' ({t['toneLabel']}, {t['fillerCount']} fillers)")

        if s["currentCoreIndex"] < len(s["coreQuestions"]):
            weak.append("unanswered interview questions")

        avg_conf = round(sum(p["tone"]["confidenceScore"] for p in dialogue) / len(dialogue)) if dialogue else 50
        avg_wpm = round(sum(p["tone"]["wordsPerMinute"] for p in dialogue) / len(dialogue)) if dialogue else 0
        avg_accuracy = round(sum(p["correctness"]["score"] for p in dialogue) / len(dialogue)) if dialogue else 50
        tot_fillers = sum(p["tone"]["fillerCount"] for p in dialogue)
        all_fillers = sorted(list(set(f for p in dialogue for f in p["tone"]["fillersDetected"])))

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
            "breakdown": dialogue,
        }

        fb = {
            "summary": f"{len(dialogue)} responses across {len(s['coreQuestions'])} interview topics; {len(weak)} weak area(s). Overall rating: {overall_rating} ({overall_score}/100).",
            "weakAreas": weak,
            "transcriptRef": sid,
            "toneAnalysis": tone_analysis,
        }
        s["feedback"] = fb
        return fb

    def past_feedback(self) -> list:
        return [s["feedback"] for s in self._sessions.values() if "feedback" in s]
