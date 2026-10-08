"""Einstellungen in der App (statt .env): Speichern, Vorrang vor den Umgebungsvariablen, Geheimnisse werden nie ausgeliefert."""
import json
import os

import conftest

H = {"X-Rahmen": "1"}
LAN = {"RAHMEN_WEB_LAN": "192.168.1.0/24", "RAHMEN_WEB_RAHMEN_ZIELE": "rahmen=Bilderrahmen", "RAHMEN_WEB_RAHMEN_SEK": "8"}


def test_standardwerte_aus_der_app_gelten_fuer_alle_rahmen(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    assert c.get("/api/config?ziel=rahmen").json()["rahmen_sek"] == 8
    r = c.put("/api/einstellungen", json={"sek": 20, "fuellung_rahmen": "zuschnitt", "anzeige": ["ort", "datum"], "tv_url": "tv.example.com/"}, headers=H).json()
    assert r["ok"] and r["einstellungen"]["sek"] == 20 and r["einstellungen"]["standard"]["sek"] == 8
    cfg = c.get("/api/config?ziel=rahmen").json()
    assert cfg["rahmen_sek"] == 20 and cfg["rahmen_fuellung"] == "zuschnitt" and cfg["rahmen_anzeige"] == ["datum", "ort"] and cfg["tv_url"] == "tv.example.com"
    c.put("/api/verwaltung/geraete/rahmen", json={"sek": 5}, headers=H)                         # Einstellung am Geraet schlaegt die allgemeine
    assert c.get("/api/config?ziel=rahmen").json()["rahmen_sek"] == 5
    assert json.load(open(w.EINST_FILE))["sek"] == 20 and oct(os.stat(w.EINST_FILE).st_mode)[-3:] == "600"
    c.put("/api/einstellungen", json={"sek": ""}, headers=H)
    c.put("/api/verwaltung/geraete/rahmen", json={"sek": ""}, headers=H)
    assert c.get("/api/config?ziel=rahmen").json()["rahmen_sek"] == 8                           # leer = Umgebung


def test_pruefungen(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    for bad in ({"sek": "x"}, {"fuellung_tv": "bunt"}, {"anzeige": ["wetter"]}, {"alarm_min": "abc"}, {"tv_url": "böse url"}, {"wetter": {"lat": 99, "lon": 0}},
                {"kalender_url": "ftp://x"}, {"pushover": {"user": "zukurz", "token": "auch"}}):
        assert c.put("/api/einstellungen", json=bad, headers=H).status_code == 400, bad
    assert client().put("/api/einstellungen", json={"sek": 9}).status_code in (400, 401, 403)     # ohne X-Rahmen


def test_wetter_und_kalender_aus_der_app(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    c = client()
    assert w.zusatz_liste() == []
    c.put("/api/einstellungen", json={"wetter": {"lat": 52.52, "lon": 13.4, "name": "Berlin"}, "kalender_url": "https://example.com/cal.ics"}, headers=H)
    assert w.zusatz_liste() == ["wetter", "kalender"] and c.get("/api/config").json()["rahmen_zusatz"] == ["wetter", "kalender"]
    a = c.get("/api/einstellungen").json()
    assert a["kalender_gesetzt"] is True and "example.com" not in json.dumps(a)                 # der Kalender-Link ist geheim
    monkeypatch.setattr(w, "http_text", lambda url, *a, **k: '{"current": {"temperature_2m": 14.4, "weather_code": 0}}')
    assert "14 °C" in c.post("/api/einstellungen/test", json={"was": "wetter"}, headers=H).json()["nachricht"]
    c.put("/api/einstellungen", json={"kalender_url": None, "wetter": None}, headers=H)
    assert w.zusatz_liste() == []


def test_pushover_zugang_aus_der_app(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    c = client()
    gesendet = []
    monkeypatch.setattr(w.urllib.request, "urlopen", lambda url, data=None, timeout=0: gesendet.append((url, data)) or type("R", (), {"read": lambda self: b"{}"})())
    u, t = "u" * 30, "t" * 30
    c.put("/api/einstellungen", json={"pushover": {"user": u, "token": t, "device": "iphone"}}, headers=H)
    a = c.get("/api/einstellungen").json()
    assert a["pushover_gesetzt"] is True and u not in json.dumps(a) and t not in json.dumps(a)
    assert c.post("/api/einstellungen/test", json={"was": "pushover"}, headers=H).json()["ok"]
    body = gesendet[0][1].decode()
    assert f"token={t}" in body and f"user={u}" in body and "device=iphone" in body
    c.put("/api/einstellungen", json={"pushover": {"device": "ipad"}}, headers=H)                 # Teilangaben behalten die Schluessel
    assert w.EINST["pushover"]["token"] == t and w.EINST["pushover"]["device"] == "ipad"


def test_spitznamen_aus_der_app(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    c.put("/api/einstellungen", json={"aliase": [{"name": "Oma", "person": "Anna Muster"}, {"name": "", "person": "x"}, {"name": "a=b;c", "person": "Opa Karl"}]}, headers=H)
    named, alias = w.H.lade_personen()
    assert alias[w.H.norm("Oma")] == "Anna Muster"
    assert [e["name"] for e in c.get("/api/einstellungen").json()["aliase"]] == ["Oma", "abc"]      # Leeres fliegt raus, Sonderzeichen werden entfernt
    assert "Anna Muster" in c.get("/api/einstellungen").json()["personen"]


def test_ortssuche(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    monkeypatch.setattr(w, "http_text", lambda url, *a, **k: json.dumps({"results": [{"name": "Berlin", "country": "Deutschland", "admin1": "Berlin", "latitude": 52.52, "longitude": 13.41}]}))
    r = client().get("/api/einstellungen/ort-suche?q=Berlin").json()
    assert r["orte"][0]["name"] == "Berlin" and r["orte"][0]["lat"] == 52.52
    assert client().get("/api/einstellungen/ort-suche?q=B").json()["orte"] == []
