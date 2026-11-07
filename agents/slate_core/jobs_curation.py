"""Dedupe and freshness for job listings. Pure functions, source-independent.

Freshness vocabulary (deliberately precise):
    active            seen in the latest complete refresh and not past the stale cutoff
    stale             still listed, but older than the posted-age cutoff - age warning only
    no_longer_listed  absent after a successful COMPLETE refresh of its source;
                      means what it says, never "expired": the posting may have been
                      filled, paused, renamed or temporarily removed
    unknown           the last refresh failed or was partial - no evidence either way
    closed            source-confirmed closed, or an explicit application deadline
                      stated by the source has passed

Dedupe rule: a listing's identity is (source, sourceId). Two listings with the same
title, company and location can still be separate requisitions, so nothing is ever
merged automatically. Cross-source sameness is surfaced as an unverified hint only.
"""
import re
from datetime import datetime, timezone

ACTIVE = "active"
STALE = "stale"
NO_LONGER_LISTED = "no_longer_listed"
UNKNOWN = "unknown"
CLOSED = "closed"

# Refresh outcomes a source adapter can report for a stored listing.
PRESENT = "present"
MISSING_COMPLETE_REFRESH = "missing_after_complete_refresh"
FETCH_FAILED = "fetch_failed"
SOURCE_CLOSED = "source_closed"
DEADLINE_PASSED = "deadline_passed"

STALE_AFTER_DAYS = 30

_LOCATION_ALIASES = {
    "bangalore": "bengaluru",
    "gurgaon": "gurugram",
    "bombay": "mumbai",
}


def listing_key(listing):
    """Stable identity: source + the source's own requisition id."""
    return (listing["source"], listing["sourceId"])


def normalize_location(location):
    """Canonical lowercase city for filtering; aliases collapse common variants.
    'Remote' stays its own label - remote geography eligibility is unknown unless
    the posting says otherwise, so it is never rewritten to a place."""
    if not location:
        return ""
    first = location.split(",")[0].split(";")[0].strip().lower()
    return _LOCATION_ALIASES.get(first, first)


def deadline_passed(deadline, now):
    """True only when a source-stated application deadline is confidently past.

    `now` must be timezone-aware. Returns None (unknown) for a missing,
    unparseable, date-only or timezone-NAIVE deadline: callers must not mark a
    listing closed on unknown evidence. A naive timestamp carries no timezone,
    so interpreting it would be a guess - the safe answer is unknown.
    """
    if not deadline:
        return None
    try:
        then = datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
    except ValueError:
        return None
    if then.tzinfo is None:
        return None
    return now > then


def _age_days(iso_ts, now):
    try:
        then = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (now - then).days


def classify_freshness(listing, observed, now, stale_after_days=STALE_AFTER_DAYS):
    """Map a refresh observation to a freshness state. `listing` is the stored
    normalized listing, `now` a timezone-aware datetime for deterministic tests."""
    # DEADLINE_PASSED observations should come from deadline_passed() above so
    # timezone-naive or unparseable deadlines never reach here as "closed".
    if observed == SOURCE_CLOSED or observed == DEADLINE_PASSED:
        return CLOSED
    if observed == FETCH_FAILED:
        return UNKNOWN
    if observed == MISSING_COMPLETE_REFRESH:
        return NO_LONGER_LISTED
    if observed == PRESENT:
        age = _age_days(listing.get("updatedAt") or "", now)
        if age is not None and age > stale_after_days:
            return STALE
        return ACTIVE
    raise ValueError("unknown observation: %r" % (observed,))


def _canon(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def cross_source_hint(a, b):
    """Unverified sameness hint across sources, or None. Never merges, never
    drops a listing: callers keep both and may display the hint."""
    if listing_key(a) == listing_key(b):
        return None  # same requisition: dedupe by key, not a hint
    if (_canon(a["company"]) == _canon(b["company"])
            and _canon(a["title"]) == _canon(b["title"])
            and normalize_location(a["location"]) == normalize_location(b["location"])):
        return ("possible duplicate of %s/%s (unverified - separate requisitions "
                "can share title and location)" % (b["source"], b["sourceId"]))
    return None
