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
    assert w.zusatz_liste() == []
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
    assert w.zusatz_liste() == ["wetter", "kalender"]
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


# ---------------------------------------------------------------- Programm nach Person
def test_person_quelle_lesen(app_laden):
    w, _, _ = app_laden(RAHMEN_WEB_RAHMEN_QUELLEN="person=Anna Muster:60, person=oma+opa, neu7:10")
    q = w.rahmen_quellen()
    assert q[0] == {"typ": "person", "namen": ["Anna Muster"], "gewicht": 60.0}
    assert q[1]["namen"] == ["oma", "opa"] and q[1]["gewicht"] == 1.0 and q[2]["typ"] == "neu"


def test_rahmen_zeigt_nur_fotos_der_person_auch_per_spitzname(app_laden):
    import conftest
    w, client, _ = app_laden(**{**LAN, "RAHMEN_WEB_RAHMEN_QUELLEN": "person=anna", "RAHMEN_WEB_ALIASE": "kleine=Anna Muster"})
    ids = w.rahmen_auswahl(8)
    assert ids and all(int(i[:8], 16) % 2 == 0 for i in ids)
    w.PERSONEN_CACHE["t"] = 0
    w.RAHMEN_QUELLEN_ROH[:] = ["person=kleine"]
    assert w.person_ids(["kleine"]) == [conftest.PERSONEN[0][1]]


def test_unbekannte_person_bricht_den_rahmen_nicht(app_laden):
    w, client, _ = app_laden(**{**LAN, "RAHMEN_WEB_RAHMEN_QUELLEN": "person=Niemand:1, *:1"})
    assert len(w.rahmen_auswahl(6)) == 6                                 # die zweite Quelle springt ein


# ---------------------------------------------------------------- Fully Kiosk: Nachtruhe, Bildschirm, Akku
FULLY = {**LAN, "RAHMEN_WEB_FULLY_RAHMEN": "10.0.0.7", "RAHMEN_WEB_FULLY_PASSWORT": "geheim", "RAHMEN_WEB_RAHMEN_NACHT": "22:00-06:30", "RAHMEN_WEB_FULLY_HELLIGKEIT": "120"}


def test_nachtzeit_pruefen(app_laden):
    w, _, _ = app_laden(**FULLY)
    dt = datetime.datetime
    assert w.in_nacht(dt(2026, 10, 5, 23, 0)) and w.in_nacht(dt(2026, 10, 6, 5, 0))
    assert not w.in_nacht(dt(2026, 10, 5, 12, 0)) and not w.in_nacht(dt(2026, 10, 5, 6, 30))


def test_fully_schaltet_bildschirm_nur_beim_wechsel(app_laden, monkeypatch):
    w, client, _ = app_laden(**FULLY)
    befehle = []
    monkeypatch.setattr(w, "fully_get", lambda url, timeout=6: (befehle.append(url), '{"batteryLevel": 80, "isPlugged": true}')[1])
    dt = datetime.datetime
    w.fully_wache_pruefen(dt(2026, 10, 5, 23, 0))
    assert any("cmd=screenOff" in u and "password=geheim" in u and u.startswith("http://10.0.0.7:2323/") for u in befehle)
    n = len(befehle)
    w.fully_wache_pruefen(dt(2026, 10, 5, 23, 30))                            # gleicher Zustand: kein neuer Befehl
    assert not any("screenO" in u for u in befehle[n:])
    w.fully_wache_pruefen(dt(2026, 10, 6, 7, 0))                              # Tag: an + Helligkeit
    assert any("cmd=screenOn" in u for u in befehle) and any("screenBrightness" in u and "value=120" in u for u in befehle)


def test_fully_akku_alarm_nur_einmal(app_laden, monkeypatch):
    w, client, _ = app_laden(**{k: v for k, v in FULLY.items() if k != "RAHMEN_WEB_RAHMEN_NACHT"})
    meldungen = []
    monkeypatch.setattr(w, "pushover", lambda t, x, p=0: meldungen.append(t))
    monkeypatch.setattr(w, "fully_get", lambda url, timeout=6: '{"batteryLevel": 5, "isPlugged": false}')
    w.fully_wache_pruefen()
    w.FULLY_STATE["rahmen"]["info_t"] = 0
    w.fully_wache_pruefen()
    assert len(meldungen) == 1 and "Akku" in meldungen[0]


def test_bildschirm_per_app_und_unbekanntes_geraet(app_laden, monkeypatch):
    w, client, _ = app_laden(**FULLY)
    befehle = []
    monkeypatch.setattr(w, "fully_get", lambda url, timeout=6: (befehle.append(url), "{}")[1])
    c = client()
    assert c.post("/api/geraete/bildschirm", json={"ziel": "rahmen", "an": False}, headers=H).json() == {"ok": True, "bildschirm": "aus"}
    assert any("screenOff" in u for u in befehle)
    assert c.post("/api/geraete/bildschirm", json={"ziel": "wz", "an": False}, headers=H).status_code == 400
    g = {x["id"]: x for x in c.get("/api/geraete").json()["geraete"]}
    assert g["rahmen"]["fully"] is True and g["rahmen"]["bildschirm"] == "aus" and g["wz"]["fully"] is False


# ---------------------------------------------------------------- Home Assistant
def test_ha_status_und_steuern(app_laden):
    w, client, _ = app_laden(**LAN)
    ha = client("192.168.1.20")
    s = ha.get("/api/ha/status").json()
    assert s["version"] and {g["id"] for g in s["geraete"]} == {"rahmen", "wz"} and all(g["zustand"] == "offline" for g in s["geraete"])
    ha.get("/api/tv/abfrage?ziel=rahmen&seq=-1&s=1&n=&a=1&ra=3")
    assert next(g for g in ha.get("/api/ha/status").json()["geraete"] if g["id"] == "rahmen")["zustand"] == "dauerprogramm"
    assert ha.post("/api/ha/steuer", json={"ziel": "rahmen", "aktion": "pause"}, headers=H).json() == {"ok": True}
    assert ha.post("/api/ha/steuer", json={"ziel": "rahmen", "aktion": "musik"}, headers=H).status_code == 400
    assert ha.post("/api/ha/steuer", json={"ziel": "rahmen", "aktion": "pause"}).status_code == 403          # ohne Header nicht
    assert client("10.0.0.5").get("/api/ha/status").status_code == 401


def test_ha_startet_gespeicherte_show(app_laden):
    import conftest
    w, client, _ = app_laden(**LAN)
    ha = client("192.168.1.20")
    w.daten_schreiben({"shows": [w.neue_show("Sardinien", [conftest.ASSETS[0]["id"], conftest.ASSETS[1]["id"]], True)]})
    assert "Sardinien" in ha.get("/api/ha/status").json()["shows"]
    r = ha.post("/api/ha/show", json={"ziel": "wz", "show": "sardinien"}, headers=H).json()
    assert r["ok"] and "Sardinien" in r["nachricht"]
    assert ha.post("/api/ha/show", json={"ziel": "wz", "show": "gibtsnicht"}, headers=H).status_code == 404


# ---------------------------------------------------------------- Laufende Show ueberlebt einen Neustart des Servers
def test_laufende_show_ueberlebt_neustart_und_stopp_wird_gemerkt(app_laden):
    import conftest
    ids = [a["id"] for a in conftest.ASSETS[:3]]
    w, client, _ = app_laden(**LAN)
    c = client()
    assert c.post("/api/tv/senden", json={"ziel": "rahmen", "ids": ids, "name": "Sardinien"}, headers=H).json()["ok"]
    w2, client2, _ = app_laden(**LAN)                                       # Neustart: frische Module, gleiche Dateien
    ev = w2.TV["rahmen"]["aktiv"]
    assert ev["name"] == "Sardinien" and set(ev["ids"]) == set(ids) and w2.TV["rahmen"]["seq"] >= ev["seq"]
    assert client2().get("/api/tv/abfrage?ziel=rahmen&seq=-1").json()["events"][0]["name"] == "Sardinien"     # Seite laedt neu: Show laeuft weiter
    assert client2().get("/api/rahmen/status").json()["rahmen"][0]["id"] == "rahmen"
    client2().post("/api/tv/steuer", json={"ziel": "rahmen", "aktion": "stopp"}, headers=H)
    w3, _, _ = app_laden(**LAN)
    assert w3.TV["rahmen"]["aktiv"] is None


def test_kaputte_aktiv_datei_stoert_den_start_nicht(app_laden, tmp_path):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "rahmen_web_aktiv.json").write_text("{kaputt")
    w, client, _ = app_laden(**LAN)
    assert w.TV["rahmen"]["aktiv"] is None
