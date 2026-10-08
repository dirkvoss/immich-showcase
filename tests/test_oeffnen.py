"""Fernseher-Seite per ADB direkt am Android TV / Fire TV oeffnen (ADB wird nachgebildet)."""
H = {"X-Rahmen": "1"}
LAN = {"RAHMEN_WEB_LAN": "192.168.1.0/24", "RAHMEN_WEB_TV_ZIELE": "wz=Wohnzimmer", "RAHMEN_WEB_TV_URL": "http://192.168.1.20:8090"}


def adb_attrappe(w, monkeypatch, antworten):
    aufrufe = []

    def adb(args, timeout=10):
        aufrufe.append(args)
        for muster, antwort in antworten:
            if muster in " ".join(args):
                return antwort
        return ""
    monkeypatch.setattr(w, "adb", adb)
    return aufrufe


def test_oeffnet_die_seite_und_merkt_die_adresse(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    aufrufe = adb_attrappe(w, monkeypatch, [("connect", "connected to 192.168.1.30:5555"), ("shell", "Starting: Intent { act=android.intent.action.VIEW }")])
    r = client().post("/api/verwaltung/oeffnen", json={"id": "wz", "adb_host": "192.168.1.30"}, headers=H).json()
    assert r["ok"] and r["wartet"] is False
    assert aufrufe[0] == ["connect", "192.168.1.30:5555"]
    assert aufrufe[1][0:2] == ["-s", "192.168.1.30:5555"] and "http://192.168.1.20:8090/tv/?ziel=wz" in aufrufe[1][3]
    assert w.GERAETE["wz"]["adb_host"] == "192.168.1.30"


def test_erste_verbindung_wartet_auf_die_erlaubnis(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    adb_attrappe(w, monkeypatch, [("connect", "connected to x:5555"), ("shell", "error: device unauthorized.")])
    r = client().post("/api/verwaltung/oeffnen", json={"id": "wz", "adb_host": "192.168.1.30"}, headers=H).json()
    assert r["wartet"] is True and "erlauben" in r["nachricht"]


def test_nicht_erreichbar_und_kein_browser(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    adb_attrappe(w, monkeypatch, [("connect", "failed to connect to '192.168.1.30:5555': Connection refused")])
    r = client().post("/api/verwaltung/oeffnen", json={"id": "wz", "adb_host": "192.168.1.30"}, headers=H)
    assert r.status_code == 502 and "nicht erreichbar" in r.json()["nachricht"]
    adb_attrappe(w, monkeypatch, [("connect", "connected to x"), ("shell", "Error: Activity not started, unable to resolve Intent")])
    r = client().post("/api/verwaltung/oeffnen", json={"id": "wz", "adb_host": "192.168.1.30"}, headers=H)
    assert r.status_code == 502 and "kein Browser" in r.json()["nachricht"]


def test_eingaben_werden_geprueft(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    aufrufe = adb_attrappe(w, monkeypatch, [])
    c = client()
    assert c.post("/api/verwaltung/oeffnen", json={"id": "gibtsnicht", "adb_host": "192.168.1.30"}, headers=H).status_code == 404
    assert c.post("/api/verwaltung/oeffnen", json={"id": "wz", "adb_host": "1.2.3.4; rm -rf /"}, headers=H).status_code == 400
    assert c.post("/api/verwaltung/oeffnen", json={"id": "wz"}, headers=H).status_code == 400
    assert c.post("/api/verwaltung/oeffnen", json={"id": "wz", "adb_host": "192.168.1.30", "basis": "http://x/'; reboot; '"}, headers=H).status_code == 400
    assert aufrufe == []                                                                     # nie ein Aufruf mit unsauberen Eingaben
    assert client().post("/api/verwaltung/oeffnen", json={"id": "wz", "adb_host": "192.168.1.30"}).status_code in (400, 401, 403)


def test_adresse_am_geraet_speicherbar(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    assert c.put("/api/verwaltung/geraete/wz", json={"adb_host": "192.168.1.30"}, headers=H).json()["geraet"]["adb_host"] == "192.168.1.30"
    assert c.put("/api/verwaltung/geraete/wz", json={"adb_host": "boese adresse"}, headers=H).status_code == 400
