"""Einrichtungsassistent und Anmeldung per API-Schluessel."""
import json
import conftest

H = {"X-Rahmen": "1"}
LEER = {"RAHMEN_IMMICH_URL": "", "RAHMEN_IMMICH_KEY": ""}


def unkonfiguriert(app_laden, monkeypatch, tmp_path, **env):
    w, client, schrein = app_laden(RAHMEN_WEB_EINSTELLUNGEN=str(tmp_path / "einst.json"), **LEER, **env)
    anm = conftest.SchreinAnmeldung()
    monkeypatch.setattr(w, "immich_aufruf", anm)
    monkeypatch.setattr(w.time, "sleep", lambda s: None)
    neustarts = []
    monkeypatch.setattr(w, "neu_starten", lambda: neustarts.append(1))
    monkeypatch.setattr(w.threading, "Timer", lambda sek, fn: type("T", (), {"start": lambda s: fn()})())
    w.setup_code_erzeugen()
    return w, client, anm, neustarts


def test_ohne_einrichtung_sind_app_daten_gesperrt(app_laden, monkeypatch, tmp_path):
    w, client, anm, _ = unkonfiguriert(app_laden, monkeypatch, tmp_path)
    c = client("192.168.1.9")
    assert c.get("/api/config").json()["konfiguriert"] is False
    r = c.get("/api/neueste")
    assert r.status_code == 503 and r.json()["setup"] is True
    assert c.get("/setup/").status_code == 200


def test_falscher_code_und_sperre(app_laden, monkeypatch, tmp_path):
    w, client, anm, _ = unkonfiguriert(app_laden, monkeypatch, tmp_path)
    c = client("10.0.0.5")
    for _ in range(w.FEHLVERSUCHE):
        assert c.post("/api/setup/pruefen", json={"code": "000000", "url": "http://x:1"}, headers=H).status_code == 403
    assert c.post("/api/setup/pruefen", json={"code": w.SETUP_CODE["wert"], "url": "http://x:1"}, headers=H).status_code == 429


def test_komplette_einrichtung_mit_immich_konto(app_laden, monkeypatch, tmp_path):
    w, client, anm, neustarts = unkonfiguriert(app_laden, monkeypatch, tmp_path)
    c = client("10.0.0.5")
    code = w.SETUP_CODE["wert"]
    r = c.post("/api/setup/pruefen", json={"code": code, "url": "http://immich.lan:2283"}, headers=H)
    assert r.status_code == 200 and r.json() == {"ok": True, "immich_version": "3.2.4", "url": "http://immich.lan:2283/api"}
    r = c.post("/api/setup/speichern", json={"code": code, "url": "http://immich.lan:2283", "email": "anna@example.org", "passwort": "anna-passwort", "pin": "246810", "name": "Familienbilder"}, headers=H)
    assert r.status_code == 200 and r.json()["ok"] is True and "pin" not in r.json()          # PIN selbst gewaehlt: nicht zurueckgeben
    einst = json.load(open(tmp_path / "einst.json"))
    assert einst["RAHMEN_IMMICH_URL"] == "http://immich.lan:2283/api" and einst["RAHMEN_IMMICH_KEY"].startswith("key-") and einst["RAHMEN_WEB_NAME"] == "Familienbilder"
    assert oct((tmp_path / "einst.json").stat().st_mode & 0o777) == "0o600"
    assert anm.abgemeldet                                                                       # Immich-Sitzung beendet
    assert w.pin_pruefen("246810") and not w.pin_pruefen("000000")
    assert neustarts == [1]


def test_einrichtung_mit_zufaelliger_pin_und_eigenem_schluessel(app_laden, monkeypatch, tmp_path):
    w, client, anm, neustarts = unkonfiguriert(app_laden, monkeypatch, tmp_path)
    c = client("10.0.0.5")
    r = c.post("/api/setup/speichern", json={"code": w.SETUP_CODE["wert"], "url": "http://immich.lan:2283/api", "schluessel": "eigener-key"}, headers=H).json()
    assert r["ok"] and len(r["pin"]) == 6 and w.pin_pruefen(r["pin"])
    assert json.load(open(tmp_path / "einst.json"))["RAHMEN_IMMICH_KEY"] == "eigener-key"


def test_falsche_zugangsdaten_werden_gemeldet_und_nichts_gespeichert(app_laden, monkeypatch, tmp_path):
    w, client, anm, neustarts = unkonfiguriert(app_laden, monkeypatch, tmp_path)
    r = client("10.0.0.5").post("/api/setup/speichern", json={"code": w.SETUP_CODE["wert"], "url": "http://x:2283", "email": "anna@example.org", "passwort": "falsch"}, headers=H)
    assert r.status_code == 400 and "falsch" in r.json()["nachricht"]
    assert not (tmp_path / "einst.json").exists() and neustarts == []


def test_ungueltige_adresse(app_laden, monkeypatch, tmp_path):
    w, client, anm, _ = unkonfiguriert(app_laden, monkeypatch, tmp_path)
    r = client("10.0.0.5").post("/api/setup/pruefen", json={"code": w.SETUP_CODE["wert"], "url": "ftp://x"}, headers=H)
    assert r.status_code == 400


def test_setup_ist_nach_der_einrichtung_zu(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24")
    assert client().get("/api/config").json()["konfiguriert"] is True
    assert client("10.0.0.5").post("/api/setup/pruefen", json={"code": "123456", "url": "http://x"}, headers=H).status_code == 404


def test_einstellungsdatei_ergaenzt_die_umgebung(app_laden, tmp_path):
    (tmp_path / "e.json").write_text(json.dumps({"RAHMEN_IMMICH_URL": "http://aus-datei/api", "RAHMEN_IMMICH_KEY": "k", "RAHMEN_WEB_NAME": "Aus Datei", "ANDERES": "x"}))
    w, client, _ = app_laden(RAHMEN_WEB_EINSTELLUNGEN=str(tmp_path / "e.json"), RAHMEN_IMMICH_URL="", RAHMEN_IMMICH_KEY="", RAHMEN_WEB_NAME="Aus Umgebung")
    import os
    assert w.konfiguriert() and os.environ["RAHMEN_IMMICH_URL"] == "http://aus-datei/api"
    assert w.APP_NAME == "Aus Umgebung"                       # die Umgebung (.env) hat Vorrang vor der Datei
    assert "ANDERES" not in os.environ


def test_login_mit_api_schluessel(app_laden, monkeypatch, tmp_path):
    w, client, schrein = app_laden(RAHMEN_WEB_AUTH="immich", RAHMEN_WEB_BENUTZER_FILE=str(tmp_path / "b.json"))
    monkeypatch.setattr(w, "immich_aufruf", conftest.SchreinAnmeldung())
    monkeypatch.setattr(w.time, "sleep", lambda s: None)
    c = client("10.0.0.5")
    assert c.post("/api/login", json={"schluessel": "falsch"}, headers=H).status_code == 401
    r = c.post("/api/login", json={"schluessel": "eigener-key"}, headers=H)
    assert r.status_code == 200 and r.json()["name"] == "Sven"
    assert c.get("/api/me").json()["name"] == "Sven"
    schrein.schluessel.clear()
    assert c.get("/api/facetten?typ=foto").status_code == 200 and set(schrein.schluessel) == {"eigener-key"}


def test_schluessel_login_sperre(app_laden, monkeypatch, tmp_path):
    w, client, schrein = app_laden(RAHMEN_WEB_AUTH="immich", RAHMEN_WEB_BENUTZER_FILE=str(tmp_path / "b.json"))
    monkeypatch.setattr(w, "immich_aufruf", conftest.SchreinAnmeldung())
    monkeypatch.setattr(w.time, "sleep", lambda s: None)
    c = client("10.0.0.5")
    for _ in range(w.FEHLVERSUCHE):
        assert c.post("/api/login", json={"schluessel": "nein"}, headers=H).status_code == 401
    assert c.post("/api/login", json={"schluessel": "eigener-key"}, headers=H).status_code == 429


def test_keine_waisen_schluessel_wenn_die_pruefung_scheitert(app_laden, monkeypatch, tmp_path):
    w, client, anm, neustarts = unkonfiguriert(app_laden, monkeypatch, tmp_path)
    anm.widerrufen.add("key-aaaa-0")                          # der gleich angelegte Schluessel wird von Immich abgelehnt
    r = client("10.0.0.5").post("/api/setup/speichern", json={"code": w.SETUP_CODE["wert"], "url": "http://x:2283", "email": "anna@example.org", "passwort": "anna-passwort"}, headers=H)
    assert r.status_code == 400
    assert anm.geloescht == ["/api-keys/id-aaaa"]            # angelegter Schluessel wieder entfernt
    assert anm.abgemeldet and not (tmp_path / "einst.json").exists()
