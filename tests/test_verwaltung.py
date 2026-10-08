"""Verwaltung: Rahmen und Fernseher in der App anlegen, einstellen, loeschen (Geraeteliste in der Datei)."""
import json
import os

import conftest

H = {"X-Rahmen": "1"}
LAN = {"RAHMEN_WEB_LAN": "192.168.1.0/24", "RAHMEN_WEB_RAHMEN_ZIELE": "rahmen=Bilderrahmen", "RAHMEN_WEB_TV_ZIELE": "wz=Wohnzimmer", "RAHMEN_WEB_RAHMEN_SEK": "8"}


def ids(a, b):
    return [x["id"] for x in conftest.ASSETS[a:b]]


def test_start_aus_umgebung_ohne_datei(app_laden):
    w, client, _ = app_laden(**LAN)
    d = client().get("/api/verwaltung").json()
    assert [(g["id"], g["art"], g["name"]) for g in d["geraete"]] == [("wz", "tv", "Wohnzimmer"), ("rahmen", "rahmen", "Bilderrahmen")]
    assert d["register_aktiv"] is False and d["standard"]["sek"] == 8
    assert not os.path.exists(w.GERAETE_FILE)


def test_rahmen_anlegen_wirkt_sofort_und_wird_gespeichert(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    r = c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Flur Obergeschoß", "sek": 12}, headers=H).json()
    assert r["id"] == "flurobergeschoss" and r["geraet"]["sek"] == 12
    assert "flurobergeschoss" in c.get("/api/config").json()["rahmen"]
    assert c.get("/api/config").json()["rahmen_namen"]["flurobergeschoss"] == "Flur Obergeschoß"
    gespeichert = json.load(open(w.GERAETE_FILE))
    assert [g["id"] for g in gespeichert["geraete"]] == ["wz", "rahmen", "flurobergeschoss"]
    assert oct(os.stat(w.GERAETE_FILE).st_mode)[-3:] == "600"
    assert c.post("/api/anzeigen", json={"name": "A", "ids": ids(0, 3), "ziele": ["flurobergeschoss"]}, headers=H).json()["ziele"] == ["flurobergeschoss"]


def test_einstellungen_je_rahmen_gelten(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Flur", "sek": 15, "fuellung": "zuschnitt", "anzeige": ["ort"], "nacht": "22:00-06:30"}, headers=H)
    cfg = c.get("/api/config?ziel=flur").json()
    assert cfg["rahmen_sek"] == 15 and cfg["rahmen_fuellung"] == "zuschnitt" and cfg["rahmen_anzeige"] == ["ort"] and cfg["rahmen_nacht"] == "22:00-06:30"
    assert c.get("/api/config?ziel=rahmen").json()["rahmen_sek"] == 8                       # anderer Rahmen: allgemeiner Wert
    c.post("/api/anzeigen", json={"name": "A", "ids": ids(0, 3), "ziele": ["flur"]}, headers=H)
    assert c.get("/api/tv/abfrage?ziel=flur&seq=-1").json()["events"][0]["sek"] == 15
    assert w.in_nacht(w.datetime.datetime(2026, 1, 1, 23, 0), "flur") and not w.in_nacht(w.datetime.datetime(2026, 1, 1, 12, 0), "flur")
    assert not w.in_nacht(w.datetime.datetime(2026, 1, 1, 23, 0), "rahmen")


def test_quellen_und_zeitplan_je_rahmen_aus_der_app(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    A = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
    c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Flur", "quellen": f"{A}:1"}, headers=H)
    assert w.rahmen_quellen("flur")[0]["id"] == A
    assert w.rahmen_quellen("rahmen")[0]["typ"] == "alle"
    assert c.put("/api/verwaltung/geraete/flur", json={"quellen": "gibtsnicht"}, headers=H).status_code == 400
    assert c.put("/api/verwaltung/geraete/flur", json={"zeitplan": "Quatsch"}, headers=H).status_code == 400
    assert c.put("/api/verwaltung/geraete/flur", json={"zeitplan": "Mo-Fr 18:00-22:00 = *"}, headers=H).status_code == 200
    c.put("/api/verwaltung/geraete/flur", json={"quellen": ""}, headers=H)
    assert w.rahmen_quellen("flur", w.datetime.datetime(2026, 10, 5, 12, 0))[0]["typ"] == "alle"       # Einstellung entfernt -> allgemeiner Wert


def test_pruefungen(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    assert c.post("/api/verwaltung/geraete", json={"art": "toaster", "name": "x"}, headers=H).status_code == 400
    assert c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": ""}, headers=H).status_code == 400
    assert c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "X", "sek": 1}, headers=H).json()["geraet"]["sek"] == 3        # begrenzt auf 3..120
    assert c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Y", "nacht": "25:00-06:00"}, headers=H).status_code == 400
    assert c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Z", "fuellung": "bunt"}, headers=H).status_code == 400
    assert c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "W", "fully_host": "böse host"}, headers=H).status_code == 400
    assert c.put("/api/verwaltung/geraete/gibtsnicht", json={"name": "A"}, headers=H).status_code == 404
    assert c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Test"}, headers=H).json()["id"] == "test2"          # "test" ist vergeben
    assert client().post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Q"}).status_code in (400, 401, 403)             # ohne X-Rahmen (CSRF)


def test_fully_passwort_wird_nie_ausgeliefert(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Flur", "fully_host": "tablet.lan", "fully_pw": "geheim123"}, headers=H)
    d = c.get("/api/verwaltung").json()
    assert "geheim123" not in json.dumps(d) and [g for g in d["geraete"] if g["id"] == "flur"][0]["fully_pw_gesetzt"] is True
    assert w.FULLY["flur"] == {"host": "tablet.lan:2323", "pw": "geheim123"}
    c.put("/api/verwaltung/geraete/flur", json={"name": "Flur 2"}, headers=H)                                                  # Passwort bleibt bei anderen Aenderungen
    assert w.FULLY["flur"]["pw"] == "geheim123"
    c.put("/api/verwaltung/geraete/flur", json={"fully_host": ""}, headers=H)
    assert "flur" not in w.FULLY


def test_loeschen_raeumt_auf(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Flur"}, headers=H)
    c.post("/api/anzeigen", json={"name": "A", "ids": ids(0, 3), "ziele": ["flur"]}, headers=H)
    assert c.delete("/api/verwaltung/geraete/flur", headers=H).json()["ok"]
    assert "flur" not in c.get("/api/config").json()["rahmen"] and "flur" not in w.TV
    assert c.get("/api/status?ziel=flur").status_code == 400
    assert [s["name"] for s in c.get("/api/shows").json()["shows"]] == ["A"]                                                    # Shows bleiben
    assert c.delete("/api/verwaltung/geraete/flur", headers=H).status_code == 404


def test_ohne_rahmen_kein_kiosk_weg_wenn_register_aktiv(app_laden):
    w, client, _ = app_laden(**{**LAN, "RAHMEN_WEB_RAHMEN_ZIELE": ""})
    c = client()
    assert w.PLAYER is None and w.REGISTER["aktiv"] is False                    # alter Kiosk-Weg bleibt, solange die Datei nicht gilt
    c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Flur"}, headers=H)
    c.delete("/api/verwaltung/geraete/flur", headers=H)
    assert w.PLAYER is None and w.REGISTER["aktiv"] is True
    r = c.post("/api/anzeigen", json={"name": "A", "ids": ids(0, 3)}, headers=H)
    assert r.status_code == 400 and "kein Bilderrahmen" in r.json()["nachricht"]


def test_datei_hat_vorrang_nach_neustart(app_laden, tmp_path):
    w, client, _ = app_laden(**LAN)
    client().post("/api/verwaltung/geraete", json={"art": "tv", "name": "Küche TV"}, headers=H)
    pfad = w.GERAETE_FILE
    w2, client2, _ = app_laden(**{**LAN, "RAHMEN_WEB_GERAETE_FILE": pfad, "RAHMEN_WEB_RAHMEN_ZIELE": "nurenv=Nur Umgebung"})
    namen = [g["id"] for g in client2().get("/api/verwaltung").json()["geraete"]]
    assert "kuechetv" in namen and "nurenv" not in namen and w2.REGISTER["aktiv"] is True


def test_zeitplan_im_format_der_app(app_laden):
    """Der Zeitplan-Editor der App schreibt Tage als Liste ('Mo,Di,Mi') bzw. 'taeglich' - der Server muss das lesen."""
    w, client, _ = app_laden(**LAN)
    c = client()
    A = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
    plan = f"Mo,Di,Mi,Do,Fr 18:00-22:00 = neu14:70, *:30; Sa,So 08:00-20:00 = {A}; taeglich 00:00-06:00 = person=Anna:50"
    assert c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Flur", "zeitplan": plan}, headers=H).status_code == 200
    dt = w.datetime.datetime
    assert [q["typ"] for q in w.rahmen_quellen("flur", dt(2026, 10, 5, 19, 0))] == ["neu", "alle"]          # Montag Abend
    assert w.rahmen_quellen("flur", dt(2026, 10, 10, 9, 0))[0]["id"] == A                                  # Samstag Vormittag
    assert w.rahmen_quellen("flur", dt(2026, 10, 7, 3, 0))[0]["typ"] == "person"                           # taeglich nachts


def test_bildunterschrift_mit_uhrzeit(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    r = c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Flur", "anzeige": ["ort", "zeit", "datum"]}, headers=H).json()
    assert r["geraet"]["anzeige"] == ["datum", "zeit", "ort"]                                   # feste Reihenfolge
    assert c.get("/api/config?ziel=flur").json()["rahmen_anzeige"] == ["datum", "zeit", "ort"]
    a = conftest.ASSETS[0]
    w.BILDINFO[a["id"]] = a
    info = c.get(f"/api/bildinfo/{a['id']}").json()
    assert info["zeit"] == "12:00" and info["datum"] == a["localDateTime"][:10]
    assert c.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "X", "anzeige": ["wetter"]}, headers=H).status_code == 400


def test_tablet_meldet_sich_selbst_ueber_fully(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    gesendet = []
    monkeypatch.setattr(w, "pushover", lambda *a, **k: gesendet.append(a))
    c = client()
    assert c.get("/api/verwaltung").json()["geraete"][1]["selbst"] is False
    c.get("/api/tv/abfrage?ziel=rahmen&seq=-1&fj=1&ak=15&pl=0")
    g = [x for x in c.get("/api/geraete").json()["geraete"] if x["id"] == "rahmen"][0]
    assert g["selbst"] is True and g["akku"] == 15 and g["laedt"] is False
    assert [x for x in c.get("/api/verwaltung").json()["geraete"] if x["id"] == "rahmen"][0]["selbst"] is True
    import time
    for _ in range(50):
        if gesendet:
            break
        time.sleep(0.05)
    assert gesendet and "Akku niedrig" in gesendet[0][0]
    n = len(gesendet)
    c.get("/api/tv/abfrage?ziel=rahmen&seq=-1&fj=1&ak=14&pl=0")                 # nicht noch einmal melden
    time.sleep(0.2)
    assert len(gesendet) == n
    c.get("/api/tv/abfrage?ziel=rahmen&seq=-1&fj=1&ak=60&pl=1")
    assert w.FULLY_STATE["rahmen"]["akku_gemeldet"] is False


def test_ohne_fully_meldet_das_geraet_nichts_selbst(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    c.get("/api/tv/abfrage?ziel=rahmen&seq=-1")
    assert [x for x in c.get("/api/verwaltung").json()["geraete"] if x["id"] == "rahmen"][0]["selbst"] is False


def test_fully_test_meldet_passwort_und_erreichbarkeit(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    c = client()
    monkeypatch.setattr(w, "fully_get", lambda url, timeout=6: '{"status":"Error","statustext":"Please login"}')
    r = c.post("/api/verwaltung/fully-test", json={"id": "rahmen", "fully_host": "tablet.lan", "fully_pw": "falsch"}, headers=H)
    assert r.status_code == 401 and "Passwort stimmt nicht" in r.json()["nachricht"]
    monkeypatch.setattr(w, "fully_get", lambda url, timeout=6: '{"batteryLevel": 71, "isPlugged": true}')
    r = c.post("/api/verwaltung/fully-test", json={"id": "rahmen", "fully_host": "tablet.lan", "fully_pw": "ok"}, headers=H).json()
    assert r["ok"] and r["akku"] == 71 and "71" in r["nachricht"]

    def kaputt(url, timeout=6):
        raise OSError("timed out")
    monkeypatch.setattr(w, "fully_get", kaputt)
    r = c.post("/api/verwaltung/fully-test", json={"id": "rahmen", "fully_host": "tablet.lan", "fully_pw": "x"}, headers=H)
    assert r.status_code == 502 and "nicht erreichbar" in r.json()["nachricht"]
