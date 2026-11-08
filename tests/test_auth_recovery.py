"""Guards for sign-in recovery after rejected/expired tokens on both pages."""
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('page',['index.html','ai.html'])
def test_401_rebuilds_login_controls_without_replaying_mutations(page):
    s=(ROOT/'web'/page).read_text()
    assert 'if(r.status===401){await recoverSignIn()}' in s
    assert 'authRecovery=initAuth().finally(' in s
    assert 'Your saved data is unchanged.' in s
    assert 'if(window.google?.accounts?.id){renderGoogle()}' in s
    assert 'google.accounts.id.disableAutoSelect()' in s
    assert 'script.id="google-identity-script"' in s

def test_pdf_upload_recovers_login_too():
    s=(ROOT/'web'/'index.html').read_text()
    assert 'if(res.status===401){await recoverSignIn()}' in s
