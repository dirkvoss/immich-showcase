"""Geraete-Zugang: ein Tablet ausserhalb des Heimnetzes bekommt beim Koppeln einen eigenen Cookie, der nur die Rahmen-Seiten oeffnet."""
H = {"X-Rahmen": "1"}
LAN = {"RAHMEN_WEB_LAN": "192.168.1.0/24", "RAHMEN_WEB_RAHMEN_ZIELE": "serbien=Serbien,flur=Flur", "RAHMEN_WEB_RAHMEN_SEK": "5"}


def kopplung(w, client, ziel="serbien"):
    """Das Tablet (von aussen) holt einen Code, die App (im Heimnetz) weist ihn zu, das Tablet fragt den Status ab."""
    tablet, app = client("203.0.113.9"), client("192.168.1.50")
    code = tablet.post("/api/koppeln/neu", headers=H).json()["code"]
    assert app.post("/api/koppeln", json={"code": code, "ziel": ziel}, headers=H).json()["ok"]
    r = tablet.get(f"/api/koppeln/status?code={code}")
    assert r.json()["ziel"] == ziel
    return tablet, app, r


def test_ohne_zugang_kein_zutritt_von_aussen(app_laden):
    w, client, _ = app_laden(**LAN)
    assert client("203.0.113.9").get("/api/tv/abfrage?ziel=serbien&seq=-1").status_code == 401


def test_kopplung_stellt_zugang_aus_und_er_oeffnet_nur_die_rahmen_seiten(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    monkeypatch.setattr(w, "immich_roh", lambda *a, **k: (b"JPEG", "image/jpeg"))
    tablet, app, r = kopplung(w, client)
    assert "rw_geraet" in r.headers.get("set-cookie", "") and "HttpOnly" in r.headers["set-cookie"]
    assert tablet.get("/api/tv/abfrage?ziel=serbien&seq=-1").status_code == 200                       # Rahmen-Abfrage
    assert tablet.get("/api/vorschau/00000001-0000-4000-8000-000000000001").status_code == 200        # Fotos
    assert tablet.get("/api/rahmen/zufall?ziel=serbien").status_code == 200                           # Dauerprogramm
    assert tablet.get("/api/rahmen/zufall?ziel=flur").status_code == 403                              # nicht fuer andere Rahmen
    # ... aber NICHT die App
    assert tablet.get("/api/neueste").status_code == 401
    assert tablet.get("/api/shows").status_code == 401
    assert tablet.get("/api/verwaltung").status_code == 401
    assert tablet.post("/api/anzeigen", json={"name": "x", "ids": ["00000001-0000-4000-8000-000000000001"]}, headers=H).status_code == 401
    assert tablet.get("/api/me").json()["angemeldet"] is False


def test_zugang_wird_bei_der_nutzung_erneuert(app_laden):
    w, client, _ = app_laden(**LAN)
    tablet, app, r = kopplung(w, client)
    assert "Max-Age=34560000" in r.headers["set-cookie"]                                                # 400 Tage
    erste = tablet.get("/api/tv/abfrage?ziel=serbien&seq=-1")
    assert "rw_geraet" in erste.headers.get("set-cookie", "")                                           # beim ersten Abruf erneuert
    assert "set-cookie" not in tablet.get("/api/tv/abfrage?ziel=serbien&seq=-1").headers               # danach nicht bei jedem Abruf
    w.GERAET_ERNEUERT["serbien"] -= 2 * 86400
    assert "rw_geraet" in tablet.get("/api/tv/abfrage?ziel=serbien&seq=-1").headers.get("set-cookie", "")   # am naechsten Tag wieder


def test_zugang_gilt_nur_fuer_das_eigene_geraet(app_laden):
    w, client, _ = app_laden(**LAN)
    tablet, app, _ = kopplung(w, client, "serbien")
    assert tablet.get("/api/tv/abfrage?ziel=flur&seq=-1").status_code == 403


def test_zugang_oeffnet_keine_home_assistant_schnittstellen(app_laden):
    w, client, _ = app_laden(**LAN)
    tablet, app, _ = kopplung(w, client)
    assert tablet.get("/api/ha/status").status_code == 401
    assert tablet.post("/api/ha/show", json={"name": "x", "ids": []}, headers=H).status_code == 401


def test_gefaelschter_zugang_wird_abgelehnt(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client("203.0.113.9")
    c.cookies.set("rw_geraet", "Zy5zZXJiaWVuLjAuYWFhYQ==")
    assert c.get("/api/tv/abfrage?ziel=serbien&seq=-1").status_code == 401
    c.cookies.set("rw_geraet", "kein base64!")
    assert c.get("/api/tv/abfrage?ziel=serbien&seq=-1").status_code == 401


def test_widerruf_sperrt_nur_dieses_geraet(app_laden):
    w, client, _ = app_laden(**LAN)
    tablet, app, _ = kopplung(w, client, "serbien")
    flur, app2, _ = kopplung(w, client, "flur")
    assert app.post("/api/verwaltung/geraete/serbien/zugang-widerrufen", headers=H).json()["ok"]
    assert tablet.get("/api/tv/abfrage?ziel=serbien&seq=-1").status_code == 401
    assert flur.get("/api/tv/abfrage?ziel=flur&seq=-1").status_code == 200
    # neu koppeln geht wieder
    tablet2, _, _ = kopplung(w, client, "serbien")
    assert tablet2.get("/api/tv/abfrage?ziel=serbien&seq=-1").status_code == 200


def test_widerruf_braucht_anmeldung(app_laden):
    w, client, _ = app_laden(**LAN)
    assert client("203.0.113.9").post("/api/verwaltung/geraete/serbien/zugang-widerrufen", headers=H).status_code == 401


def test_befehl_kommt_einmal_beim_geraet_an(app_laden):
    w, client, _ = app_laden(**LAN)
    app = client("192.168.1.50")
    assert app.post("/api/geraete/serbien/befehl", json={"aktion": "neuladen"}, headers=H).json()["ok"]
    assert app.get("/api/tv/abfrage?ziel=serbien&seq=-1").json()["befehl"] == "neuladen"
    assert "befehl" not in app.get("/api/tv/abfrage?ziel=serbien&seq=-1").json()                      # nur einmal
    assert app.post("/api/geraete/serbien/befehl", json={"aktion": "böse"}, headers=H).status_code == 400
    assert app.post("/api/geraete/gibtsnicht/befehl", json={"aktion": "neuladen"}, headers=H).status_code == 404
    assert client("203.0.113.9").post("/api/geraete/serbien/befehl", json={"aktion": "neuladen"}, headers=H).status_code == 401


def test_alarmzeit_je_geraet(app_laden):
    w, client, _ = app_laden(**LAN)
    app = client("192.168.1.50")
    r = app.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Oma", "alarm_min": 90}, headers=H)
    assert r.status_code == 200
    gid = r.json()["id"]
    assert app.put(f"/api/verwaltung/geraete/{gid}", json={"alarm_min": 120}, headers=H).json()["geraet"]["alarm_min"] == 120
    assert app.put(f"/api/verwaltung/geraete/{gid}", json={"alarm_min": "x"}, headers=H).status_code == 400
    assert app.put(f"/api/verwaltung/geraete/{gid}", json={"alarm_min": ""}, headers=H).json()["geraet"]["alarm_min"] is None
    assert w.gwert(gid, "alarm_min", 15) == 15
    app.put(f"/api/verwaltung/geraete/{gid}", json={"alarm_min": 0}, headers=H)
    assert w.gwert(gid, "alarm_min", 15) == 0                                                          # 0 = nie melden
