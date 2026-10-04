"""Zusatzanzeige (Wetter, Termine), Geraeteuebersicht und Kopplung per Code."""
import datetime

H = {"X-Rahmen": "1"}
LAN = {"RAHMEN_WEB_LAN": "192.168.1.0/24", "RAHMEN_WEB_RAHMEN_ZIELE": "rahmen=Rahmen", "RAHMEN_WEB_TV_ZIELE": "wz=Wohnzimmer"}

ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20261005T183000
SUMMARY:Zahnarzt\\, Dr. Muster
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261005
SUMMARY:Muelltonne
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:19900506
RRULE:FREQ=YEARLY
SUMMARY:Geburtstag Oma
END:VEVENT
BEGIN:VEVENT
DTSTART:20260105T070000
RRULE:FREQ=WEEKLY;BYDAY=MO,TH
SUMMARY:Sport
END:VEVENT
BEGIN:VEVENT
DTSTART:20261009T100000
SUMMARY:Spaeter
END:VEVENT
END:VCALENDAR
"""


def test_ics_termine_heute_morgen_und_wiederholungen(app_laden):
    w, _, _ = app_laden()
    t = w.ics_termine(ICS, datetime.date(2026, 10, 5))
    titel = [(e["tag"], e["zeit"], e["titel"]) for e in t]
    assert ("heute", "", "Muelltonne") in titel                       # ganztaegig zuerst (00:00)
    assert ("heute", "07:00", "Sport") in titel                       # Montag, woechentlich
    assert ("heute", "18:30", "Zahnarzt, Dr. Muster") in titel
    assert all("Spaeter" not in x[2] and "Oma" not in x[2] for x in titel)
    assert [e["tag"] for e in w.ics_termine(ICS, datetime.date(2026, 5, 5))] == ["morgen"]      # 6.5. ist morgen: Geburtstag


def test_zusatz_nur_wenn_eingerichtet(app_laden):
    w, client, _ = app_laden(**LAN)
    assert w.ZUSATZ == []
    assert client().get("/api/rahmen/zusatz").json() == {}
    assert client().get("/api/config").json()["rahmen_zusatz"] == []


def test_zusatz_wetter_und_kalender_gecacht(app_laden, monkeypatch):
    w, client, _ = app_laden(RAHMEN_WEB_WETTER_ORT="52.5,13.4", RAHMEN_WEB_KALENDER_URL="https://example.org/cal.ics", **LAN)
    aufrufe = []

    def falsch(url, timeout=10):
        aufrufe.append(url)
        if "open-meteo" in url:
            return '{"current": {"temperature_2m": 12.6, "weather_code": 3}}'
        return ICS.replace("20261005", datetime.date.today().strftime("%Y%m%d"))
    monkeypatch.setattr(w, "http_text", falsch)
    assert w.ZUSATZ == ["wetter", "kalender"]
    d = client().get("/api/rahmen/zusatz").json()
    assert d["wetter"] == {"temp": 13, "symbol": "☁️"} and any(e["titel"] == "Muelltonne" for e in d["termine"])
    client().get("/api/rahmen/zusatz")
    assert len(aufrufe) == 2                                         # zweiter Abruf kommt aus dem Zwischenspeicher


def test_zusatz_fehler_stoert_nicht(app_laden, monkeypatch):
    w, client, _ = app_laden(RAHMEN_WEB_WETTER_ORT="52.5,13.4", **LAN)
    monkeypatch.setattr(w, "http_text", lambda url, timeout=10: (_ for _ in ()).throw(OSError("offline")))
    assert client().get("/api/rahmen/zusatz").json() == {}


def test_geraete_uebersicht_braucht_anmeldung_und_zeigt_zustand(app_laden):
    w, client, _ = app_laden(**LAN)
    assert client("10.0.0.5").get("/api/geraete").status_code == 401
    c = client()
    c.get("/api/tv/abfrage?ziel=rahmen&seq=-1&s=1&n=&a=1&ra=3")        # Rahmen meldet sich im Dauerprogramm
    g = {x["id"]: x for x in c.get("/api/geraete").json()["geraete"]}
    assert g["rahmen"]["online"] and g["rahmen"]["dauerprogramm"] and g["rahmen"]["art"] == "rahmen"
    assert g["wz"]["online"] is False and g["wz"]["art"] == "tv" and "test" not in g


def test_kopplung_per_code(app_laden):
    w, client, _ = app_laden(**LAN)
    geraet, handy = client("192.168.1.60"), client()
    code = geraet.post("/api/koppeln/neu", headers=H).json()["code"]
    assert len(code) == 6 and geraet.get(f"/api/koppeln/status?code={code}").json() == {"ziel": None, "name": None}
    assert handy.post("/api/koppeln", json={"code": "ZZZZZZ", "ziel": "wz"}, headers=H).status_code == 404
    assert handy.post("/api/koppeln", json={"code": code, "ziel": "gibtsnicht"}, headers=H).status_code == 400
    assert handy.post("/api/koppeln", json={"code": code.lower(), "ziel": "wz"}, headers=H).json()["name"] == "Wohnzimmer"
    assert geraet.get(f"/api/koppeln/status?code={code}").json() == {"ziel": "wz", "name": "Wohnzimmer"}


def test_kopplung_braucht_anmeldung_zum_zuweisen_und_ist_begrenzt(app_laden):
    w, client, _ = app_laden(**LAN)
    fremd = client("10.0.0.5")
    code = fremd.post("/api/koppeln/neu", headers=H).json()["code"]
    assert fremd.post("/api/koppeln", json={"code": code, "ziel": "wz"}, headers=H).status_code == 401
    assert client("10.0.0.5").post("/api/koppeln/neu").status_code == 403          # ohne Header nicht
    for _ in range(4):
        assert fremd.post("/api/koppeln/neu", headers=H).status_code == 200
    assert fremd.post("/api/koppeln/neu", headers=H).status_code == 429             # je IP hoechstens 5 offene Codes
