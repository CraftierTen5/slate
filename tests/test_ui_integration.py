"""Static guards for the small auth/jobs/roadmap UI integration."""
from pathlib import Path
HTML = (Path(__file__).resolve().parents[1] / 'web' / 'index.html').read_text()

def test_freshness_discloses_fixture_meaning_beside_state():
    assert 'Demo fixture: ${esc(x.freshness||"unknown")} (not live-verified)' in HTML

def test_match_reason_and_job_id_are_escaped():
    assert '${esc(x.reason||"")}' in HTML
    assert 'data-j="${esc(x.jobId)}"' in HTML

def test_roadmap_resources_remain_https_links():
    assert 'm.resources.map(resLink)' in HTML
    assert 'rel="noopener noreferrer"' in HTML
    assert r'/^https:\/\//' in HTML

def test_auth_still_covers_json_and_pdf_requests():
    assert 'h["authorization"]="Bearer "+token()' in HTML
    assert 'ph["authorization"]="Bearer "+token()' in HTML
