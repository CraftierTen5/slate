"""Parser vocabulary, independent of the demo job catalog.

Conservative literal phrases and spelling variants, not a semantic assessment.
Adding a skill here does not create a job, a learning plan or a verified claim.
"""
import re
import unicodedata

SKILL_ALIASES = {
    "python": (), "sql": (), "excel": ("microsoft excel",),
    "statistics": (), "fastapi": (), "postgresql": ("postgres",),
    "git": (), "javascript": (), "react": ("react.js", "reactjs"),
    "typescript": (), "css": (), "pytorch": (), "tableau": (),
    "java": (), "c++": (), "docker": (), "aws": ("amazon web services",),
    "figma": (),
    "communication": ("communications", "communication skills"),
    "customer service": ("customer support", "served customers"),
    "cash handling": ("handled cash", "cash register"),
    "numeracy": ("numeracy skills",),
    "teamwork": ("team work", "work as part of a team", "working as part of a team"),
    "organisation": ("organization", "organisational skills", "organizational skills"),
    "problem solving": ("solve problems", "solving problems"),
    "responsibility": ("take responsibility",),
    "coaching": ("assistant coach",),
    "leadership": (),
}


def normalized(text):
    text = unicodedata.normalize("NFKC", text or "").casefold()
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    # PDFs can line-wrap a multi-word skill or use a nonbreaking space/hyphen.
    return re.sub(r"\s+", " ", text)


def skill_evidence(text):
    """Return canonical skills and one literal matched phrase per skill.

    Never equate broad subjects with tools (maths != statistics, business != SQL).
    Evidence is a phrase match, not proof of proficiency or positive assertion.
    """
    low = normalized(text)
    found = []
    for skill, aliases in sorted(SKILL_ALIASES.items()):
        for phrase in (skill,) + aliases:
            pattern = r"(?<![\w+#])" + re.escape(phrase).replace(r"\ ", r"[\s-]+") + r"(?![\w+#])"
            match = re.search(pattern, low)
            if match:
                found.append({"skill": skill, "matchedText": match.group(0), "source": "known_phrase"})
                break
    return found


# These are explicit section labels, not a promise of language understanding.
_SKILL_HEADING = re.compile(
    r"^(?:key skills|technical skills|core skills|professional skills|skills|"
    r"competencies|compétences|habilidades|fähigkeiten|技能|कौशल)\s*[:：]?\s*(.*)$", re.I)
_SECTION_HEADING = re.compile(
    r"^(?:education|experience|work experience|employment|projects|qualifications|"
    r"certifications|interests(?:/hobbies)?|referees|references|availability|"
    r"career objective|summary|leadership roles|formation|expérience|educación|"
    r"experiencia|ausbildung|berufserfahrung|教育|工作经历|शिक्षा|अनुभव)\s*[:：]?\s*$", re.I)


def explicit_skill_evidence(text):
    """Keep concise, explicitly listed skill phrases even outside the vocabulary.

    No inference from prose/job titles. A long bullet is not turned into a skill.
    Supported input: a recognized skills heading followed by short list items,
    or an inline list after that heading. Unknown section formats stay unsupported.
    Values remain candidate skill mentions for human review, not verified facts.
    """
    out, seen, active = [], set(), False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            active = False
            continue
        heading = _SKILL_HEADING.fullmatch(line)
        if heading:
            active = True
            content = heading.group(1)
        elif _SECTION_HEADING.fullmatch(line):
            active = False
            continue
        elif active:
            # Wrapped narrative continuation lines are not standalone list items.
            if not re.match(r"^[•*\-–]\s+", line) and not re.search(r"[,;|•]", line):
                if _SECTION_HEADING.fullmatch(line): active = False
                continue
            content = re.sub(r"^[•*\-–]\s*", "", line)
            # An unknown heading ends the section rather than consuming its text.
            if content.endswith((":", "：")):
                active = False
                continue
        else:
            continue
        for part in re.split(r"[,;|•]", content):
            phrase = part.strip().strip(".")
            if not phrase or len(phrase) > 70 or len(phrase.split()) > 5:
                continue
            # Reject sentence-like claims, dates/contact values, and labels.
            if any(c in phrase for c in "@:/<>\\") or re.search(r"\b(?:I|my|when|through|demonstrated|seeking|proven)\b", phrase, re.I):
                continue
            if not any(c.isalpha() for c in phrase):
                continue
            matches = skill_evidence(phrase)
            # Known short aliases canonicalize only when they cover the whole item.
            exact = next((e for e in matches if e["matchedText"] == normalized(phrase)), None)
            if matches and not exact:
                continue  # avoid duplicating prose/qualifiers as a second skill
            skill = exact["skill"] if exact else normalized(phrase)
            if skill not in seen:
                out.append({"skill": skill, "matchedText": phrase, "source": "explicit_skill_list"})
                seen.add(skill)
            if len(out) >= 64:
                return out
    return out
