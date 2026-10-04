"""Eigene Musik: keine im Lieferumfang, Ordner einlesen, optional in der App hinzufuegen."""
import subprocess

H = {"X-Rahmen": "1"}
LAN = {"RAHMEN_WEB_LAN": "192.168.1.0/24"}


def audio(pfad, inhalt=b"AUDIO-demo"):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(inhalt)


def ohne_ffprobe(monkeypatch, w):
    """ffprobe vortaeuschen: Dateien, die mit AUDIO beginnen, sind 3,5 s lang; keine Dateimarken."""
    def lauf(cmd, **kw):
        if cmd[0] == "ffprobe":
            pfad = cmd[-1]
            ok = open(pfad, "rb").read(5) == b"AUDIO"
            return subprocess.CompletedProcess(cmd, 0 if ok else 1, stdout=("3.5\n" if ok and "duration" in " ".join(cmd) else "{}"), stderr="")
        raise AssertionError(cmd)
    monkeypatch.setattr(w.subprocess, "run", lauf)


def test_ohne_musik_ist_alles_leer(app_laden, tmp_path):
    w, client, _ = app_laden(RAHMEN_WEB_MUSIK_DIR=str(tmp_path / "musik"), **LAN)
    assert w.musik_bibliothek() == {}
    assert client().get("/api/tv/ziele").json()["musik"] == []


def test_ordner_werden_zu_sammlungen(app_laden, tmp_path, monkeypatch):
    m = tmp_path / "musik"
    audio(m / "Meine Lieder" / "01_Erstes_Lied.mp3"); audio(m / "Meine Lieder" / "Zweites Lied.ogg"); audio(m / "Klavier & Co" / "Stück.m4a")
    audio(m / "lose.mp3"); (m / "Meine Lieder" / "notiz.txt").write_text("kein Audio")
    w, client, _ = app_laden(RAHMEN_WEB_MUSIK_DIR=str(m), **LAN)
    ohne_ffprobe(monkeypatch, w)
    lib = w.musik_bibliothek()
    assert set(lib) == {"alle", "meine-lieder", "klavier-co", "eigene"}
    assert lib["meine-lieder"]["name"] == "Meine Lieder"
    assert lib["eigene"]["name"] == "Eigene Musik"
    assert [st["titel"] for st in lib["meine-lieder"]["stuecke"]] == ["Erstes Lied", "Zweites Lied"]         # Nummer und Unterstriche weg, notiz.txt ignoriert
    assert len(lib["alle"]["stuecke"]) == 4 and all(st["kat"] for st in lib["alle"]["stuecke"])


def test_wiedergabe_und_pfadschutz(app_laden, tmp_path, monkeypatch):
    m = tmp_path / "musik"
    audio(m / "A" / "eins.mp3", b"AUDIO-eins")
    (tmp_path / "geheim.mp3").write_bytes(b"AUDIO-geheim")
    w, client, _ = app_laden(RAHMEN_WEB_MUSIK_DIR=str(m), **LAN)
    ohne_ffprobe(monkeypatch, w)
    c = client()
    st = c.get("/api/tv/musikliste?k=a").json()["stuecke"][0]
    assert c.get(f"/api/tv/musikdatei/a/{st['datei']}").content == b"AUDIO-eins"
    assert c.get("/api/tv/musikdatei/a/..%2F..%2Fgeheim.mp3").status_code == 404
    assert c.get("/api/tv/musikdatei/a/unbekannt.mp3").status_code == 404


def test_info_json_ueberschreibt_marken(app_laden, tmp_path, monkeypatch):
    import json
    m = tmp_path / "musik"
    audio(m / "klavier" / "chopin_01.mp3")
    (m / "klavier" / "info.json").write_text(json.dumps({"name": "Klavier", "stuecke": [{"datei": "chopin_01.mp3", "titel": "Nocturne", "urheber": "Chopin", "lizenz": "CC0"}]}))
    w, client, _ = app_laden(RAHMEN_WEB_MUSIK_DIR=str(m), **LAN)
    ohne_ffprobe(monkeypatch, w)
    st = w.musik_bibliothek()["klavier"]["stuecke"][0]
    assert (st["datei"], st["titel"], st["urheber"], st["lizenz"]) == ("chopin_01.mp3", "Nocturne", "Chopin", "CC0")


def test_hochladen_ist_standardmaessig_aus(app_laden, tmp_path):
    w, client, _ = app_laden(RAHMEN_WEB_MUSIK_DIR=str(tmp_path / "musik"), **LAN)
    assert client().get("/api/config").json()["musik_upload"] is False
    assert client().put("/api/musik/neu/lied.mp3", content=b"AUDIO-x", headers=H).status_code == 403


def test_hochladen_und_loeschen(app_laden, tmp_path, monkeypatch):
    m = tmp_path / "musik"
    w, client, _ = app_laden(RAHMEN_WEB_MUSIK_DIR=str(m), RAHMEN_WEB_MUSIK_UPLOAD="1", **LAN)
    ohne_ffprobe(monkeypatch, w)
    c = client()
    assert c.get("/api/config").json()["musik_upload"] is True
    r = c.put("/api/musik/Urlaub 2024/Strand-Lied.mp3", content=b"AUDIO-1234", headers=H)
    assert r.status_code == 200 and r.json()["sammlung"] == "urlaub-2024"
    assert (m / "urlaub-2024" / "Strand-Lied.mp3").read_bytes() == b"AUDIO-1234"
    r2 = c.put("/api/musik/Urlaub 2024/Strand-Lied.mp3", content=b"AUDIO-5678", headers=H)       # gleicher Name: nicht ueberschreiben
    assert r2.json()["datei"] == "Strand-Lied (2).mp3"
    assert c.get("/api/tv/musikliste?k=urlaub-2024").json()["name"] == "Urlaub 2024"          # eingegebener Name bleibt erhalten
    ziel = c.get("/api/tv/musikliste?k=urlaub-2024").json()["stuecke"]
    assert sorted(st["titel"] for st in ziel) == ["Strand-Lied", "Strand-Lied (2)"]
    for st in ziel:
        assert c.delete(f"/api/musik/urlaub-2024/{st['datei']}", headers=H).status_code == 200
    assert not (m / "urlaub-2024").exists()                                              # leere Sammlung verschwindet


def test_hochladen_grenzen(app_laden, tmp_path, monkeypatch):
    m = tmp_path / "musik"
    w, client, _ = app_laden(RAHMEN_WEB_MUSIK_DIR=str(m), RAHMEN_WEB_MUSIK_UPLOAD="1", RAHMEN_WEB_MUSIK_MAX_MB="1", **LAN)
    ohne_ffprobe(monkeypatch, w)
    c = client()
    assert c.put("/api/musik/x/lied.exe", content=b"AUDIO", headers=H).status_code == 400          # falscher Typ
    assert c.put("/api/musik/x/leer.mp3", content=b"kein audio", headers=H).status_code == 400      # kein Audio
    assert c.put("/api/musik/x/gross.mp3", content=b"AUDIO" + b"0" * (1024 * 1024 + 1), headers=H).status_code == 413
    assert c.put("/api/musik/x/lied.mp3", content=b"AUDIO-ok").status_code == 403                    # ohne Header (CSRF)
    assert not list(m.rglob("*.hochladen")) and not list((m).rglob("gross*"))                      # keine Reste


def test_hochladen_braucht_anmeldung(app_laden, tmp_path, monkeypatch):
    w, client, _ = app_laden(RAHMEN_WEB_MUSIK_DIR=str(tmp_path / "musik"), RAHMEN_WEB_MUSIK_UPLOAD="1")
    assert client("10.0.0.5").put("/api/musik/x/lied.mp3", content=b"AUDIO", headers=H).status_code == 401
