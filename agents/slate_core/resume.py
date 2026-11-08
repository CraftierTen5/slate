import io
import re
from .skills import skill_evidence, explicit_skill_evidence

MAX_PDF_BYTES = 5 * 1024 * 1024

class ParseError(ValueError):
    pass

def parse_resume(text: str) -> dict:
    """Pull name, skills, education and experience from plain resume text."""
    if not isinstance(text, str) or len(text.strip()) < 20:
        raise ParseError("Resume text is empty or too short to parse.")
    text = _without_template_tips(text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        raise ParseError("No resume content remains after removing template guidance.")
    name = lines[0] if len(lines[0].split()) <= 5 and "@" not in lines[0] else "Unknown"
    evidence = skill_evidence(text)
    seen = {item["skill"] for item in evidence}
    evidence += [item for item in explicit_skill_evidence(text) if item["skill"] not in seen]
    evidence.sort(key=lambda item: item["skill"])
    skills = [item["skill"] for item in evidence]
    education, experience = [], []
    for l in lines:
        m = re.search(r"(b\.?tech|m\.?tech|bca|mca|b\.?sc|m\.?sc|bachelor|master)[^,\n]*", l, re.I)
        if m:
            y = re.search(r"(20\d\d)", l)
            education.append({"degree": m.group(1).upper().replace("..", "."), "institute": _after(l, ","),
                              "year": int(y.group(1)) if y else None})
        m = re.search(r"(intern|developer|analyst|engineer)\b.*?(?:at|,|-)\s*([A-Za-z0-9 &.]+?)\s*(?:\((\d+)\s*months?\)|$)", l, re.I)
        if m and not re.search(r"b\.?tech|bachelor", l, re.I):
            experience.append({"title": m.group(1).title(), "org": m.group(2).strip(),
                               "months": int(m.group(3)) if m.group(3) else None})
    return {"name": name, "skills": skills, "education": education, "experience": experience,
            "skillEvidence": evidence,
            "parseWarnings": ["Skill candidates from phrase matches and explicit lists, not verified proficiency or a complete resume assessment. "
                              "Review the detected skills; education and work-history extraction are limited."]}

def find_skills(text: str) -> list:
    """Canonical skill mentions, including supported spelling/phrase aliases.

    Shared with claim checking. Do NOT strip template guidance here: a draft
    cannot hide a new skill from the claim gate by wrapping it in '(Tip: ...)'.
    """
    return [item["skill"] for item in skill_evidence(text)]


def _without_template_tips(text):
    """Ignore explicitly marked parenthesized resume-template instructions only.

    Handle line wraps and nested parentheses without swallowing later sections
    when an unclosed note occurs. Do not remove arbitrary parenthetical facts.
    """
    pattern = re.compile(r"\(\s*tip\s*:", re.I)
    pos, chunks = 0, []
    for match in pattern.finditer(text):
        if match.start() < pos:
            continue
        depth, end = 1, match.end()
        while end < len(text) and depth:
            if text[end] == "(": depth += 1
            elif text[end] == ")": depth -= 1
            end += 1
        if depth:  # malformed guidance: keep it rather than lose resume content
            continue
        chunks.append(text[pos:match.start()]); chunks.append("\n")
        pos = end
    chunks.append(text[pos:])
    return "".join(chunks)


def _after(line: str, sep: str) -> str:
    return line.split(sep, 1)[1].strip().rstrip(".") if sep in line else ""


def extract_pdf_text(data: bytes) -> str:
    """Pull selectable text out of PDF bytes. Scanned images and broken files raise ParseError."""
    if not data or len(data) > MAX_PDF_BYTES:
        raise ParseError("PDF is empty or larger than 5 MB.")
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ParseError("PDF support (pypdf) is not installed on this server.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ParseError("That PDF is password-protected; export it without a password and retry.")
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except ParseError:
        raise
    except Exception:
        raise ParseError("Could not read that file as a PDF.")
    if len(text.strip()) < 20:
        raise ParseError("No selectable text found in that PDF (a scanned image will not work).")
    return text
