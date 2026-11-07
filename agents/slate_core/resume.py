import io
import re
from .sample_data import KNOWN_SKILLS

MAX_PDF_BYTES = 5 * 1024 * 1024

class ParseError(ValueError):
    pass

def parse_resume(text: str) -> dict:
    """Pull name, skills, education and experience from plain resume text."""
    if not isinstance(text, str) or len(text.strip()) < 20:
        raise ParseError("Resume text is empty or too short to parse.")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    name = lines[0] if len(lines[0].split()) <= 5 and "@" not in lines[0] else "Unknown"
    skills = find_skills(text)
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
    return {"name": name, "skills": skills, "education": education, "experience": experience}

def find_skills(text: str) -> list:
    """Known skills named in text, whole-word match, sorted."""
    low = (text or "").lower()
    return [s for s in KNOWN_SKILLS if re.search(r"(?<![a-z+])" + re.escape(s) + r"(?![a-z+])", low)]

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
