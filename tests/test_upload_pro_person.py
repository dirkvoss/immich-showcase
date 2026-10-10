"""Upload pro Person: Bei Anmeldung mit dem Immich-Konto landen hochgeladene Fotos im EIGENEN Konto (eigener Schluessel, eigenes Album)."""
import json
import pathlib

import conftest

H = {"X-Rahmen": "1"}
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
ANNA, KARL = "aaaaaaaa-0000-4000-8000-00000000000a", "bbbbbbbb-0000-4000-8000-00000000000b"


def app(app_laden, monkeypatch, tmp_path, **env):
    w, client, schrein = app_laden(RAHMEN_WEB_AUTH="immich", RAHMEN_WEB_LAN="192.168.1.0/24", RAHMEN_WEB_BENUTZER_FILE=str(tmp_path / "benutzer.json"), **env)
    anm = conftest.SchreinAnmeldung()
    monkeypatch.setattr(w, "immich_aufruf", anm)
    monkeypatch.setattr(w.time, "sleep", lambda s: None)
    gesendet = []

    def senden(pfad, body, kopf):
        gesendet.append((pfad, kopf["x-api-key"], body))
        return 201, json.dumps({"id": "11111111-1111-4111-8111-%012d" % len(gesendet), "status": "created"}).encode()

    monkeypatch.setattr(w, "upload_senden", senden)
    monkeypatch.setattr(w, "immich_roh", lambda *a, **k: (b"x", "image/jpeg"))
    alben = []
    orig = anm.__call__

    def mit_alben(methode, pfad, daten=None, token=None, schluessel=None, basis=None):
        if pfad == "/albums":
            alben.append((methode, schluessel))
            return [] if methode == "GET" else {"id": "album-" + str(schluessel)}
        if pfad.startswith("/albums/") and methode == "PUT":
            alben.append(("PUT:" + pfad, schluessel))
            return []
        return orig(methode, pfad, daten, token, schluessel, basis)

    monkeypatch.setattr(w, "immich_aufruf", mit_alben)
    return w, client, anm, gesendet, alben


def anmelden(c, email="anna@example.org", pw="anna-passwort"):
    return c.post("/api/login", json={"email": email, "passwort": pw}, headers=H)


def test_config_bietet_hochladen_bei_immich_anmeldung(app_laden, monkeypatch, tmp_path):
    w, client, *_ = app(app_laden, monkeypatch, tmp_path)
    assert client("10.0.0.5").get("/api/config").json()["hochladen"] is True            # ohne gemeinsamen Upload-Schluessel


def test_jede_person_laedt_mit_dem_eigenen_schluessel_hoch(app_laden, monkeypatch, tmp_path):
    w, client, anm, gesendet, alben = app(app_laden, monkeypatch, tmp_path)
    a, k = client("10.0.0.5"), client("10.0.0.6")
    anmelden(a); anmelden(k, "karl@example.org", "karl-passwort")
    assert a.put("/api/hochladen", content=JPEG, headers=H).status_code == 200
    assert k.put("/api/hochladen", content=JPEG, headers=H).status_code == 200
    assert gesendet[0][1] == anm.schluessel[ANNA] and gesendet[1][1] == anm.schluessel[KARL]    # je Person der eigene Schluessel
    assert gesendet[0][1] != gesendet[1][1]
    # Album je Person im eigenen Konto angelegt und befuellt
    angelegt = {s for m, s in alben if m == "POST"}
    assert angelegt == {anm.schluessel[ANNA], anm.schluessel[KARL]}


def test_ohne_anmeldung_kein_upload_im_immich_betrieb(app_laden, monkeypatch, tmp_path):
    w, client, *_ = app(app_laden, monkeypatch, tmp_path)
    assert client("10.0.0.5").put("/api/hochladen", content=JPEG, headers=H).status_code == 401


def test_pin_betrieb_braucht_weiter_den_upload_schluessel(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24")
    c = client("192.168.1.50")
    assert c.get("/api/config").json()["hochladen"] is False
    assert c.put("/api/hochladen", content=JPEG, headers=H).status_code == 403


def test_aelterer_schluessel_ohne_upload_recht_wird_beim_login_ersetzt(app_laden, monkeypatch, tmp_path):
    w, client, anm, gesendet, alben = app(app_laden, monkeypatch, tmp_path)
    c = client("10.0.0.5")
    anmelden(c)                                                                          # erster Login legt den Schluessel an
    erster = anm.schluessel[ANNA]
    # Immich meldet fuer diesen Schluessel NUR Leserechte (so waren Schluessel vor dieser Version)
    orig = w.immich_aufruf

    def alt(methode, pfad, daten=None, token=None, schluessel=None, basis=None):
        if pfad == "/api-keys/me" and schluessel == erster:
            return {"id": "alte-id", "name": "Frameside", "permissions": ["asset.read", "asset.view"]}
        return orig(methode, pfad, daten, token, schluessel, basis)

    monkeypatch.setattr(w, "immich_aufruf", alt)
    anmelden(c)
    assert anm.schluessel[ANNA] != erster                                                # neuer Schluessel
    assert "/api-keys/alte-id" in getattr(anm, "geloescht", [])                          # alter wurde in Immich entfernt
    assert json.loads(pathlib.Path(tmp_path / "benutzer.json").read_text())[ANNA]["key"] == anm.schluessel[ANNA]


def test_schluessel_enthaelt_upload_aber_kein_loeschrecht(app_laden):
    w, client, _ = app_laden()
    assert "asset.upload" in w.KEY_RECHTE
    assert not any("delete" in p and p not in ("album.delete", "albumAsset.delete") for p in w.KEY_RECHTE)


def test_gesundheit_nennt_eigene_konten(app_laden, monkeypatch, tmp_path):
    w, client, *_ = app(app_laden, monkeypatch, tmp_path)
    c = client("10.0.0.5")
    anmelden(c)
    p = {x["id"]: x for x in c.get("/api/gesundheit").json()["pruefungen"]}
    assert p["upload"]["status"] == "ok" and "eigenes Immich-Konto" in p["upload"]["text"]
