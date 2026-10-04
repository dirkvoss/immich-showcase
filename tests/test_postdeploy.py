"""Pruefungen nach dem Deploy: Selbsttest-Zugang (Sicherheit) und postdeploy.py gegen eine echte laufende Instanz mit Schein-Immich."""
import socket
import sys
import threading
import time

import pytest

import conftest

H = {"X-Rahmen": "1"}


def token_schreiben(w, wert="geheim-123"):
    open(w.SELBSTTEST_FILE, "w").write(wert)


def test_selbsttest_nur_von_loopback_mit_geheimnis(app_laden, tmp_path):
    w, client, _ = app_laden(SHOWCASE_SELBSTTEST_FILE=str(tmp_path / "token"))
    token_schreiben(w)
    assert client("127.0.0.1").get("/api/neueste", headers={"X-Selbsttest": "geheim-123"}).status_code == 200
    assert client("127.0.0.1").get("/api/neueste", headers={"X-Selbsttest": "falsch"}).status_code == 401
    assert client("127.0.0.1").get("/api/neueste").status_code == 401
    assert client("203.0.113.9").get("/api/neueste", headers={"X-Selbsttest": "geheim-123"}).status_code == 401      # richtiges Geheimnis, aber von aussen
    assert client("192.168.1.50").get("/api/neueste", headers={"X-Selbsttest": "geheim-123"}).status_code == 401


def test_selbsttest_erlaubt_nur_lesen(app_laden, tmp_path):
    w, client, _ = app_laden(SHOWCASE_SELBSTTEST_FILE=str(tmp_path / "token"))
    token_schreiben(w)
    c = client("127.0.0.1")
    assert c.post("/api/normal", json={}, headers={**H, "X-Selbsttest": "geheim-123"}).status_code == 401
    assert c.post("/api/tv/steuer", json={"ziel": "lg", "aktion": "stopp"}, headers={**H, "X-Selbsttest": "geheim-123"}).status_code == 401


def test_selbsttest_ohne_datei_ist_zu(app_laden, tmp_path):
    w, client, _ = app_laden(SHOWCASE_SELBSTTEST_FILE=str(tmp_path / "gibt-es-nicht"))
    assert client("127.0.0.1").get("/api/neueste", headers={"X-Selbsttest": ""}).status_code == 401


def test_selbsttest_im_immich_betrieb(app_laden, tmp_path):
    w, client, _ = app_laden(RAHMEN_WEB_AUTH="immich", SHOWCASE_SELBSTTEST_FILE=str(tmp_path / "token"))
    token_schreiben(w)
    assert client("127.0.0.1").get("/api/status", headers={"X-Selbsttest": "geheim-123"}).status_code == 200


def freier_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def laufende_instanz(app_laden, tmp_path, monkeypatch):
    import uvicorn

    def starten(**env):
        w, _, schrein = app_laden(SHOWCASE_SELBSTTEST_FILE=str(tmp_path / "token"), RAHMEN_WEB_RAHMEN_ZIELE="rahmen=Rahmen", **env)
        monkeypatch.setattr(w, "immich_roh", lambda pfad, timeout=60, schluessel=None: (b"\xff\xd8" + b"x" * 2000, "image/jpeg"))
        w.selbsttest_geheimnis()
        port = freier_port()
        server = uvicorn.Server(uvicorn.Config(w.app, host="127.0.0.1", port=port, log_level="error"))
        threading.Thread(target=server.run, daemon=True).start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        return w, f"http://127.0.0.1:{port}", server

    gestartet = []

    def fabrik(**env):
        r = starten(**env)
        gestartet.append(r[2])
        return r
    yield fabrik
    for srv in gestartet:
        srv.should_exit = True


def test_postdeploy_besteht_gegen_gesunde_instanz(laufende_instanz, tmp_path, capsys):
    import postdeploy
    w, url, _ = laufende_instanz()
    code = postdeploy.main(["--url", url, "--token-datei", str(tmp_path / "token"), "--version", "dev"])
    ausgabe = capsys.readouterr().out
    assert code == 0, ausgabe
    for muster in ("OK   Konfiguration erreichbar", "OK   laufende Version stimmt", "OK   Immich: Filter und Zaehler", "OK   Immich: Vorschaubild", "OK   Rahmen: Dauerprogramm liefert Fotos", "OK   App-Daten ohne Anmeldung gesperrt"):
        assert muster in ausgabe, ausgabe


def test_postdeploy_erkennt_falsche_version(laufende_instanz, tmp_path, capsys):
    import postdeploy
    w, url, _ = laufende_instanz()
    assert postdeploy.main(["--url", url, "--token-datei", str(tmp_path / "token"), "--version", "9.9.9"]) == 1
    assert "FEHL laufende Version stimmt" in capsys.readouterr().out


def test_postdeploy_erkennt_kaputte_immich_verbindung(laufende_instanz, tmp_path, capsys, monkeypatch):
    import postdeploy
    w, url, _ = laufende_instanz()

    def kaputt(method, path, body=None, timeout=120):
        raise OSError("Immich nicht erreichbar")
    monkeypatch.setattr(w.H, "api", kaputt)
    w.CACHE.clear()
    assert postdeploy.main(["--url", url, "--token-datei", str(tmp_path / "token")]) == 1
    assert "FEHL Immich" in capsys.readouterr().out


def test_postdeploy_ohne_immich_besteht_ohne_immich(laufende_instanz, tmp_path, capsys, monkeypatch):
    import postdeploy
    w, url, _ = laufende_instanz()
    monkeypatch.setattr(w.H, "api", lambda *a, **k: (_ for _ in ()).throw(OSError("aus")))
    assert postdeploy.main(["--url", url, "--token-datei", str(tmp_path / "token"), "--ohne-immich"]) == 0, capsys.readouterr().out


def test_postdeploy_ohne_geheimnis_ueberspringt_zugriff(laufende_instanz, tmp_path, capsys):
    import postdeploy
    w, url, _ = laufende_instanz()
    assert postdeploy.main(["--url", url, "--token-datei", str(tmp_path / "fehlt")]) == 0
    assert "WARN kein Selbsttest-Geheimnis" in capsys.readouterr().out
