"""Fernseher-Browser werden von der Startadresse automatisch auf die Fernseher-Seite geleitet."""
import pytest

TVS = [
    "Mozilla/5.0 (Linux; NetCast; U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.79 Safari/537.36 SmartTV",
    "Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.79 Safari/537.36 WebAppManager",
    "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/537.36 (KHTML, like Gecko) 76.0.3809.146/6.0 TV Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; SHIELD Android TV Build/RQ1A) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 9; AFTMM Build/PS7233) AppleWebKit/537.36 Silk/120.1 like Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/114 Safari/537.36 CrKey/1.56.500000",
]
GEWOEHNLICH = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
]


@pytest.mark.parametrize("ua", TVS)
def test_fernseher_werden_umgeleitet(app_laden, ua):
    w, client, _ = app_laden()
    r = client().get("/", headers={"User-Agent": ua}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/tv/"


@pytest.mark.parametrize("ua", GEWOEHNLICH)
def test_normale_browser_bekommen_die_app(app_laden, ua):
    w, client, _ = app_laden()
    r = client().get("/", headers={"User-Agent": ua}, follow_redirects=False)
    assert r.status_code == 200 and "Immich Showcase" in r.text


def test_ui_parameter_haelt_die_app_am_fernseher(app_laden):
    w, client, _ = app_laden()
    r = client().get("/?ui=1", headers={"User-Agent": TVS[0]}, follow_redirects=False)
    assert r.status_code == 200 and "Immich Showcase" in r.text
