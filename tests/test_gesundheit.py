"""Status "Alles in Ordnung?": Pruefungen mit verstaendlichen Hinweisen."""
import time

H = {"X-Rahmen": "1"}
LAN = {"RAHMEN_WEB_LAN": "192.168.1.0/24", "RAHMEN_WEB_RAHMEN_ZIELE": "serbien=Serbien,flur=Flur", "RAHMEN_ML_URL": "http://ml.test/predict"}


def vorbereiten(w, monkeypatch, immich_ok=True, ml_ok=True):
    def aufruf(m, p, d=None, **k):
        if not immich_ok:
            raise OSError("keine Verbindung")
        return {"major": 3, "minor": 2, "patch": 4} if p == "/server/version" else []

    class Antwort:
        def read(self): return b'{"message":"pong"}'

    def oeffnen(url, timeout=0):
        if not ml_ok:
            raise OSError("ml aus")
        return Antwort()

    class Platte:
        total, used, free = 100 * 2**30, 40 * 2**30, 60 * 2**30

    monkeypatch.setattr(w, "immich_aufruf", aufruf)
    monkeypatch.setattr(w.urllib.request, "urlopen", oeffnen)
    monkeypatch.setattr(w.shutil, "disk_usage", lambda p: Platte)          # unabhaengig vom Rechner, auf dem der Test laeuft
    w.CACHE.clear()


def eintraege(c):
    d = c.get("/api/gesundheit").json()
    return d["gesamt"], {p["id"]: p for p in d["pruefungen"]}


def test_braucht_anmeldung(app_laden):
    w, client, _ = app_laden(**LAN)
    assert client("203.0.113.9").get("/api/gesundheit").status_code == 401


def test_alles_ok_wenn_gemeldet(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    vorbereiten(w, monkeypatch)
    for z in ("serbien", "flur"):
        w.TV[z]["hb"] = time.time()
    gesamt, p = eintraege(client("192.168.1.50"))
    assert gesamt == "ok", p
    assert p["speicher"]["status"] == "ok" and "60 GB" in p["speicher"]["text"]
    assert p["immich"]["status"] == "ok" and "3.2.4" in p["immich"]["text"]
    assert p["fotos"]["status"] == "ok" and "Fotos sichtbar" in p["fotos"]["text"]
    assert p["ml"]["status"] == "ok"
    assert p["g-serbien"]["status"] == "ok" and p["g-flur"]["status"] == "ok"
    assert p["upload"]["status"] == "info"                     # nicht eingerichtet: nur ein Hinweis, kein Fehler
    assert p["version"]["status"] == "info"


def test_immich_down_ist_fehler_mit_hinweis(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    vorbereiten(w, monkeypatch, immich_ok=False)
    gesamt, p = eintraege(client("192.168.1.50"))
    assert gesamt == "fehler" and p["immich"]["status"] == "fehler" and "Docker" in p["immich"]["hinweis"]


def test_ml_aus_ist_nur_warnung(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    vorbereiten(w, monkeypatch, ml_ok=False)
    monkeypatch.setattr(w, "DB_AKTIV", True)                   # nur mit Datenbankzugang wird der ML-Dienst ueberhaupt gebraucht
    for z in ("serbien", "flur"):
        w.TV[z]["hb"] = time.time()
    gesamt, p = eintraege(client("192.168.1.50"))
    assert p["ml"]["status"] == "warnung" and gesamt == "warnung"


def test_ohne_datenbankzugang_ist_fehlender_ml_dienst_kein_problem(app_laden, monkeypatch):
    """Showcase auf einem anderen Rechner als Immich: die Motivsuche laeuft ueber Immich, der ML-Dienst ist nicht erreichbar und wird nicht gebraucht."""
    w, client, _ = app_laden(**LAN)
    vorbereiten(w, monkeypatch, ml_ok=False)
    monkeypatch.setattr(w, "DB_AKTIV", False)
    for z in ("serbien", "flur"):
        w.TV[z]["hb"] = time.time()
    gesamt, p = eintraege(client("192.168.1.50"))
    assert p["ml"]["status"] == "ok" and gesamt == "ok", p


def test_geraet_offline_und_alarmzeit(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    vorbereiten(w, monkeypatch)
    w.TV["flur"]["hb"] = time.time()
    w.TV["serbien"]["hb"] = time.time() - 30 * 60                       # seit 30 Minuten still
    w.RAHMEN_ALARM_MIN = 15
    gesamt, p = eintraege(client("192.168.1.50"))
    assert p["g-serbien"]["status"] == "fehler" and "30 Minuten" in p["g-serbien"]["text"] and gesamt == "fehler"
    w.GERAETE["serbien"]["alarm_min"] = 120                              # eigene, groessere Zeit: dann nur Warnung
    w.CACHE.clear()
    gesamt, p = eintraege(client("192.168.1.50"))
    assert p["g-serbien"]["status"] == "warnung" and gesamt == "warnung"


def test_noch_nie_gemeldet_und_akku(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    vorbereiten(w, monkeypatch)
    w.TV["flur"]["hb"] = time.time()
    w.FULLY_STATE["flur"] = {"akku": 8, "laedt": False}
    gesamt, p = eintraege(client("192.168.1.50"))
    assert p["g-serbien"]["status"] == "info" and "noch nie" in p["g-serbien"]["text"]
    assert p["g-flur"]["status"] == "warnung" and "Akku" in p["g-flur"]["text"]


def test_wenig_speicher(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    vorbereiten(w, monkeypatch)

    class Platte:
        total, used, free = 100 * 2**30, 97 * 2**30, 3 * 2**30

    monkeypatch.setattr(w.shutil, "disk_usage", lambda p: Platte)
    for z in ("serbien", "flur"):
        w.TV[z]["hb"] = time.time()
    gesamt, p = eintraege(client("192.168.1.50"))
    assert p["speicher"]["status"] == "fehler" and gesamt == "fehler"


def test_update_hinweis_bei_neuerer_version(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    vorbereiten(w, monkeypatch)
    monkeypatch.setattr(w, "VERSION", "2.15.0")
    monkeypatch.setattr(w, "neueste_version", lambda: (2, 17, 1))
    for z in ("serbien", "flur"):
        w.TV[z]["hb"] = time.time()
    gesamt, p = eintraege(client("192.168.1.50"))
    assert p["version"]["status"] == "warnung" and "2.17.1" in p["version"]["text"] and "docker compose pull" in p["version"]["hinweis"]
    assert gesamt == "warnung"


def test_aktuelle_version_und_dev_machen_keine_warnung(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    vorbereiten(w, monkeypatch)
    for z in ("serbien", "flur"):
        w.TV[z]["hb"] = time.time()
    monkeypatch.setattr(w, "VERSION", "2.17.1")
    monkeypatch.setattr(w, "neueste_version", lambda: (2, 17, 1))
    gesamt, p = eintraege(client("192.168.1.50"))
    assert p["version"]["status"] == "info" and "neueste Version" in p["version"]["text"] and gesamt == "ok"
    w.CACHE.clear()
    monkeypatch.setattr(w, "VERSION", "dev")
    assert eintraege(client("192.168.1.50"))[1]["version"]["status"] == "info"


def test_versionsnummer_und_abschalten(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)
    assert w.versionsnummer("v2.17.1") == (2, 17, 1) and w.versionsnummer("2.5.0") == (2, 5, 0)
    assert w.versionsnummer("dev") is None and w.versionsnummer("2.5") is None
    monkeypatch.setattr(w, "UPDATE_PRUEFEN", False)
    assert w.neueste_version() is None


def test_github_antwort_wird_ausgewertet(app_laden, monkeypatch):
    w, client, _ = app_laden(**LAN)

    class Antwort:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'[{"name":"v2.16.0"},{"name":"v2.17.1"},{"name":"nightly"},{"name":"v2.9.0"}]'

    monkeypatch.setattr(w.urllib.request, "urlopen", lambda *a, **k: Antwort())
    w.CACHE.clear()
    assert w.neueste_version() == (2, 17, 1)
    monkeypatch.setattr(w.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    w.CACHE.clear()
    assert w.neueste_version() is None                                         # nicht pruefbar: kein Fehler, kein Hinweis
