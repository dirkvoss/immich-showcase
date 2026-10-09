"""Fotos vom Handy hochladen: Annahme, Pruefungen, Weitergabe an Immich (Schein-Immich, kein Netzwerk)."""
import json
import urllib.error

import pytest

H = {"X-Rahmen": "1"}
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
HEIC = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64


def aktiv(app_laden, **env):
    w, client, schrein = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24", RAHMEN_IMMICH_UPLOAD_KEY="upload-key", **env)
    return w, client("192.168.1.50")


def test_ohne_schluessel_ist_hochladen_aus(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24")
    c = client("192.168.1.50")
    assert c.get("/api/config").json()["hochladen"] is False
    assert c.put("/api/hochladen", content=JPEG, headers=H).status_code == 403


def test_config_meldet_hochladen(app_laden):
    w, c = aktiv(app_laden)
    d = c.get("/api/config").json()
    assert d["hochladen"] is True and d["hochladen_mb"] == 40


def test_braucht_anmeldung_und_csrf(app_laden):
    w, client, _ = app_laden(RAHMEN_IMMICH_UPLOAD_KEY="upload-key")
    assert client("10.0.0.5").put("/api/hochladen", content=JPEG, headers=H).status_code == 401
    w2, c = aktiv(app_laden)
    assert c.put("/api/hochladen", content=JPEG).status_code == 403


@pytest.mark.parametrize("daten", [JPEG, PNG, HEIC])
def test_fotos_werden_angenommen(app_laden, monkeypatch, daten):
    w, c = aktiv(app_laden)
    gesehen = []
    monkeypatch.setattr(w, "upload_zu_immich", lambda d, typ, name, ms: gesehen.append((typ, name, ms)) or {"ok": True, "id": "x", "neu": True})
    r = c.put("/api/hochladen", content=daten, headers={**H, "X-Dateiname": "Urlaub%20%C3%9Cberraschung.JPG", "X-Datum": "1700000000000"})
    assert r.status_code == 200 and r.json()["ok"] is True
    typ, name, ms = gesehen[0]
    assert typ.startswith("image/") and name.startswith("Urlaub Überraschung") and ms == 1700000000000


def test_videos_und_unsinn_werden_abgelehnt(app_laden, monkeypatch):
    w, c = aktiv(app_laden)
    monkeypatch.setattr(w, "upload_zu_immich", lambda *a: pytest.fail("darf nicht aufgerufen werden"))
    assert c.put("/api/hochladen", content=MP4, headers=H).status_code == 415
    assert c.put("/api/hochladen", content=b"<html>", headers=H).status_code == 415
    assert c.put("/api/hochladen", content=b"", headers=H).status_code == 415


def test_zu_grosse_datei(app_laden, monkeypatch):
    w, c = aktiv(app_laden, RAHMEN_WEB_UPLOAD_MAX_MB="1")
    monkeypatch.setattr(w, "upload_zu_immich", lambda *a: pytest.fail("darf nicht aufgerufen werden"))
    assert c.put("/api/hochladen", content=JPEG + b"\x00" * (1024 * 1024 + 1), headers=H).status_code == 413


def test_gefaehrliche_dateinamen_werden_bereinigt(app_laden, monkeypatch):
    w, c = aktiv(app_laden)
    namen = []
    monkeypatch.setattr(w, "upload_zu_immich", lambda d, typ, name, ms: namen.append(name) or {"ok": True, "id": "x", "neu": True})
    c.put("/api/hochladen", content=JPEG, headers={**H, "X-Dateiname": "..%2F..%2Fetc%2Fpasswd"})
    c.put("/api/hochladen", content=JPEG, headers={**H, "X-Dateiname": '%22%3Bx%0D%0A.jpg'})
    assert namen[0] == "passwd.jpg"
    assert "\n" not in namen[1] and '"' not in namen[1] and ";" not in namen[1]


def test_zu_viele_uploads_pro_stunde(app_laden, monkeypatch):
    w, c = aktiv(app_laden)
    monkeypatch.setattr(w, "UPLOAD_PRO_STUNDE", 2)
    monkeypatch.setattr(w, "upload_zu_immich", lambda *a: {"ok": True, "id": "x", "neu": True})
    assert [c.put("/api/hochladen", content=JPEG, headers=H).status_code for _ in range(3)] == [200, 200, 429]


class _Antwort:
    def __init__(self, daten): self._d = daten
    def read(self): return self._d
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_weitergabe_an_immich_mit_album_und_vorschau(app_laden, monkeypatch):
    w, c = aktiv(app_laden)
    aufrufe = []

    def urlopen(req, timeout=0):
        aufrufe.append((req.get_method(), req.full_url.replace("http://immich.test/api", ""), dict((k.lower(), v) for k, v in req.header_items()), req.data))
        return _Antwort(json.dumps({"id": "11111111-1111-4111-8111-111111111111", "status": "created"}).encode())

    monkeypatch.setattr(w.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(w, "immich_aufruf", lambda m, p, d=None, **k: aufrufe.append((m, p, k, d)) or ([] if m == "GET" else {"id": "alb"}))
    monkeypatch.setattr(w, "immich_roh", lambda pfad, **k: aufrufe.append(("GET", pfad, {}, None)) or (b"x", "image/jpeg"))
    r = c.put("/api/hochladen", content=JPEG, headers={**H, "X-Dateiname": "a.jpg", "X-Datum": "1700000000000"})
    assert r.json() == {"ok": True, "id": "11111111-1111-4111-8111-111111111111", "neu": True}
    post = next(a for a in aufrufe if a[0] == "POST" and a[1] == "/assets")
    assert post[2]["x-api-key"] == "upload-key" and post[2]["x-immich-checksum"]
    assert b'name="assetData"; filename="a.jpg"' in post[3] and b'name="deviceId"' in post[3] and JPEG in post[3]
    assert b'2023-11-14T22:13:20.000Z' in post[3]
    assert ("POST", "/albums") in [(a[0], a[1]) for a in aufrufe]            # Album wird angelegt
    assert any(a[0] == "PUT" and a[1] == "/albums/alb/assets" and a[3] == {"ids": ["11111111-1111-4111-8111-111111111111"]} for a in aufrufe)
    assert any(a[1].endswith("/thumbnail?size=preview") for a in aufrufe)    # wartet auf die Vorschau


def test_immich_lehnt_ab_gibt_verstaendliche_meldung(app_laden, monkeypatch):
    w, c = aktiv(app_laden)

    def urlopen(req, timeout=0):
        raise urllib.error.HTTPError("x", 403, "nein", {}, None)

    monkeypatch.setattr(w.urllib.request, "urlopen", urlopen)
    r = c.put("/api/hochladen", content=JPEG, headers=H)
    assert r.status_code == 502 and "Rechte" in r.json()["nachricht"]


def test_schluessel_wird_in_der_diagnose_geschwaerzt(app_laden):
    w, c = aktiv(app_laden)
    assert "upload-key" not in w.schwaerzen("Fehler mit upload-key im Text")
