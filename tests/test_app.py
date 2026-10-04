"""App-Verhalten gegen ein Schein-Immich: Zugang, Konfiguration, Filter (API-Weg), Fernseher, Rahmen-Player, Modi."""
H = {"X-Rahmen": "1"}


def test_sichere_vorgabe_ohne_vertrautes_netz(app_laden):
    w, client, _ = app_laden()
    c = client("192.168.1.50")
    assert c.get("/api/me").json() == {"angemeldet": False, "lan": False, "auth": "pin"}
    assert c.get("/api/neueste").status_code == 401


def test_vertrautes_netz_braucht_keine_pin(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24")
    assert client("192.168.1.50").get("/api/me").json()["lan"] is True
    assert client("10.0.0.5").get("/api/me").json()["lan"] is False


def test_login_mit_pin(app_laden):
    w, client, _ = app_laden()
    c = client("10.0.0.5")
    assert c.post("/api/login", json={"pin": "123456"}, headers=H).json() == {"ok": True}
    assert c.get("/api/me").json()["angemeldet"] is True
    assert c.get("/api/neueste").status_code == 200


def test_login_ohne_csrf_header_abgelehnt(app_laden):
    w, client, _ = app_laden()
    assert client("10.0.0.5").post("/api/login", json={"pin": "123456"}).status_code == 403


def test_sperre_nach_fehlversuchen(app_laden, monkeypatch):
    w, client, _ = app_laden()
    monkeypatch.setattr(w.time, "sleep", lambda s: None)
    c = client("10.0.0.5")
    for _ in range(w.FEHLVERSUCHE):
        assert c.post("/api/login", json={"pin": "000000"}, headers=H).status_code == 401
    assert c.post("/api/login", json={"pin": "123456"}, headers=H).status_code == 429


def test_proxy_ip_wird_nur_vertrauten_proxys_geglaubt(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24", RAHMEN_WEB_PROXIES="10.9.9.9")
    # Anfrage kommt vom Proxy und behauptet, aus dem LAN zu sein -> gilt
    assert client("10.9.9.9").get("/api/me", headers={"X-Real-IP": "192.168.1.7"}).json()["lan"] is True
    # gleicher Header von einem fremden Rechner -> wird ignoriert
    assert client("203.0.113.5").get("/api/me", headers={"X-Real-IP": "192.168.1.7"}).json()["lan"] is False


def test_config(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_NAME="Meins", RAHMEN_WEB_MODUS="tv", RAHMEN_WEB_TV_ZIELE="wz=Wohnzimmer")
    d = client().get("/api/config").json()
    assert d["name"] == "Meins" and d["modus"] == "tv" and d["ziele"] == {"wz": "Wohnzimmer"}
    assert "test" not in d["ziele"]


def test_falscher_modus_wird_beides(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_MODUS="quatsch", RAHMEN_WEB_LAN="192.168.1.0/24")
    assert client().get("/api/config").json()["modus"] == "beides"


def test_facetten_ueber_api(app_laden):
    w, client, schrein = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24")
    d = client().get("/api/facetten?typ=foto").json()
    assert d["gesamt"] == 28
    assert {j["wert"] for j in d["jahre"]} == {2019, 2020, 2021}
    assert {x["wert"] for x in d["laender"]} == {"Germany", "Italy", "Serbia"}
    assert not any(m == "POST" and p.startswith("/search/") is False for m, p in schrein.aufrufe)


def test_facetten_verknuepft(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24")
    alle = client().get("/api/facetten?typ=foto").json()
    nur_italien = client().get("/api/facetten?typ=foto&ort=Italy").json()
    assert 0 < nur_italien["gesamt"] < alle["gesamt"]


def test_ungueltige_filter_abgelehnt(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24")
    assert client().get("/api/facetten?typ=quatsch").status_code == 400


def test_sortierung_nach_datum_ueber_api(app_laden):
    w, client, _ = app_laden()
    ids = [a["id"] for a in __import__("conftest").ASSETS[:12]][::-1]
    alt = w.nach_datum(ids, True)
    daten = {a["id"]: a["localDateTime"] for a in __import__("conftest").ASSETS}
    assert [daten[i] for i in alt] == sorted(daten[i] for i in ids)
    assert w.nach_datum(ids, False) == alt[::-1] or [daten[i] for i in w.nach_datum(ids, False)] == sorted((daten[i] for i in ids), reverse=True)


def test_tv_senden_und_steuern(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24", RAHMEN_WEB_TV_ZIELE="wz=Wohnzimmer")
    c = client()
    ids = [a["id"] for a in __import__("conftest").ASSETS[:5]]
    r = c.post("/api/tv/senden", json={"ziel": "wz", "ids": ids, "name": "Test", "sekunden": 5, "reihenfolge": "alt"}, headers=H).json()
    assert r["ok"]
    ev = c.get("/api/tv/abfrage?ziel=wz&seq=-1").json()["events"][0]
    assert ev["typ"] == "start" and ev["name"] == "Test" and set(ev["ids"]) == set(ids) and ev["zufall"] is False
    c.post("/api/tv/steuer", json={"ziel": "wz", "aktion": "stopp"}, headers=H)
    assert c.get("/api/tv/abfrage?ziel=wz&seq=-1").json()["events"] == []


def test_tv_unbekanntes_ziel(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24")
    r = client().post("/api/tv/senden", json={"ziel": "gibtsnicht", "ids": [_id() for _id in []] or ["00000001-0000-4000-8000-000000000001"], "name": "x"}, headers=H)
    assert r.status_code == 400


def test_rahmen_player_ablauf(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24", RAHMEN_WEB_RAHMEN_ZIELE="rahmen=Rahmen", RAHMEN_WEB_RAHMEN_SEK="5")
    c = client()
    ids = [a["id"] for a in __import__("conftest").ASSETS[:4]]
    assert c.get("/api/status").json()["laeuft"] is None
    assert c.post("/api/anzeigen", json={"name": "Urlaub", "ids": ids}, headers=H).json()["ok"]
    st = c.get("/api/status").json()
    assert st["laeuft"] == "Urlaub" and st["anzahl"] == 4 and st["reihenfolge"] == "alt"
    ev = c.get("/api/tv/abfrage?ziel=rahmen&seq=-1").json()["events"][0]
    assert ev["sek"] == 5 and ev["zufall"] is False
    c.post("/api/reihenfolge", json={"reihenfolge": "zufall"}, headers=H)
    assert c.get("/api/status").json()["reihenfolge"] == "zufall"
    assert c.get("/api/tv/abfrage?ziel=rahmen&seq=-1").json()["events"][0]["zufall"] is True
    assert [s["name"] for s in c.get("/api/shows").json()["shows"]] == ["Urlaub"]
    c.post("/api/normal", json={}, headers=H)
    assert c.get("/api/status").json()["laeuft"] is None


def test_rahmen_zufallsprogramm(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24", RAHMEN_WEB_RAHMEN_ZIELE="rahmen=Rahmen")
    ids = client().get("/api/rahmen/zufall?n=10").json()["ids"]
    assert 0 < len(ids) <= 10


def test_rahmenziel_nicht_in_tv_liste(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24", RAHMEN_WEB_RAHMEN_ZIELE="rahmen=Rahmen", RAHMEN_WEB_TV_ZIELE="wz=Wohnzimmer")
    assert [z["id"] for z in client().get("/api/tv/ziele").json()["ziele"]] == ["wz"]


def test_reine_tv_installation_merkt_shows(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24", RAHMEN_WEB_MODUS="tv", RAHMEN_WEB_TV_ZIELE="wz=Wohnzimmer")
    c = client()
    ids = [a["id"] for a in __import__("conftest").ASSETS[:3]]
    c.post("/api/tv/senden", json={"ziel": "wz", "ids": ids, "name": "Abend"}, headers=H)
    assert [s["name"] for s in c.get("/api/shows").json()["shows"]] == ["Abend"]


def test_statische_dateien_ohne_anmeldung(app_laden):
    w, client, _ = app_laden()
    c = client("203.0.113.9")
    for pfad in ("/", "/i18n.js", "/i18n/en.json", "/manifest.webmanifest", "/tv/"):
        assert c.get(pfad).status_code == 200, pfad
    assert c.get("/api/shows").status_code == 401


def test_version_aendert_sich_nicht_zwischen_aufrufen(app_laden):
    w, client, _ = app_laden()
    c = client()
    assert c.get("/api/version").json() == c.get("/api/version").json()


# --------------------------------------------------------------------------- Anmeldung mit dem Immich-Konto

def immich_app(app_laden, monkeypatch, **env):
    import conftest
    w, client, schrein = app_laden(RAHMEN_WEB_AUTH="immich", RAHMEN_WEB_LAN="192.168.1.0/24",
                                   RAHMEN_WEB_BENUTZER_FILE=str(__import__("pathlib").Path(env.pop("tmp")) / "benutzer.json"), **env)
    anm = conftest.SchreinAnmeldung()
    monkeypatch.setattr(w, "immich_aufruf", anm)
    monkeypatch.setattr(w.time, "sleep", lambda s: None)
    return w, client, schrein, anm


def anmelden(c, email="anna@example.org", pw="anna-passwort"):
    return c.post("/api/login", json={"email": email, "passwort": pw}, headers=H)


def test_immich_login_und_eigener_schluessel(app_laden, monkeypatch, tmp_path):
    w, client, schrein, anm = immich_app(app_laden, monkeypatch, tmp=tmp_path)
    c = client("10.0.0.5")
    assert c.get("/api/me").json()["angemeldet"] is False
    assert c.get("/api/neueste").status_code == 401
    r = anmelden(c)
    assert r.json() == {"ok": True, "name": "Anna"}
    assert c.get("/api/me").json() == {"angemeldet": True, "lan": False, "auth": "immich", "name": "Anna"}
    assert anm.abgemeldet == ["tok-aaaaaaaa-0000-4000-8000-00000000000a"]        # Immich-Sitzung wurde beendet
    schrein.schluessel.clear()
    assert c.get("/api/neueste").status_code == 200
    assert set(schrein.schluessel) == {anm.schluessel["aaaaaaaa-0000-4000-8000-00000000000a"]}   # Aufrufe laufen mit dem Schluessel der Person


def test_zwei_personen_haben_getrennte_schluessel_und_shows(app_laden, monkeypatch, tmp_path):
    w, client, schrein, anm = immich_app(app_laden, monkeypatch, tmp=tmp_path, RAHMEN_WEB_RAHMEN_ZIELE="rahmen=Rahmen")
    a, k = client("10.0.0.5"), client("10.0.0.6")
    anmelden(a); anmelden(k, "karl@example.org", "karl-passwort")
    ids = [x["id"] for x in __import__("conftest").ASSETS[:3]]
    a.post("/api/anzeigen", json={"name": "Annas Show", "ids": ids}, headers=H)
    assert [s["name"] for s in a.get("/api/shows").json()["shows"]] == ["Annas Show"]
    assert k.get("/api/shows").json()["shows"] == []                       # Karl sieht Annas Shows nicht
    schrein.schluessel.clear()
    a.get("/api/facetten?typ=foto"); k.get("/api/facetten?typ=foto")
    assert len(set(schrein.schluessel)) == 2                              # je Person mit eigenem Schluessel (kein Cache-Mix)


def test_falsches_passwort_und_sperre(app_laden, monkeypatch, tmp_path):
    w, client, schrein, anm = immich_app(app_laden, monkeypatch, tmp=tmp_path)
    c = client("10.0.0.5")
    for _ in range(w.FEHLVERSUCHE):
        assert anmelden(c, pw="falsch").status_code == 401
    assert anmelden(c).status_code == 429                                  # auch das richtige Passwort wird gesperrt


def test_sperre_gilt_auch_je_email_von_anderer_ip(app_laden, monkeypatch, tmp_path):
    w, client, schrein, anm = immich_app(app_laden, monkeypatch, tmp=tmp_path)
    for i in range(w.FEHLVERSUCHE):
        assert anmelden(client(f"10.0.1.{i}"), pw="falsch").status_code == 401
    assert anmelden(client("10.0.2.9")).status_code == 429


def test_lan_gilt_im_immich_betrieb_nur_fuer_geraete(app_laden, monkeypatch, tmp_path):
    w, client, schrein, anm = immich_app(app_laden, monkeypatch, tmp=tmp_path, RAHMEN_WEB_TV_ZIELE="wz=Wohnzimmer")
    c = client("192.168.1.50")
    assert c.get("/api/neueste").status_code == 401            # App-Daten nicht ohne Anmeldung
    assert c.get("/api/shows").status_code == 401
    assert c.get("/api/tv/abfrage?ziel=wz&seq=-1").status_code == 200      # Fernseher-Seite im LAN ohne Anmeldung
    assert c.get("/tv/").status_code == 200


def test_pin_ist_im_reinen_immich_betrieb_aus(app_laden, monkeypatch, tmp_path):
    w, client, schrein, anm = immich_app(app_laden, monkeypatch, tmp=tmp_path)
    assert client("10.0.0.5").post("/api/login", json={"pin": "123456"}, headers=H).status_code == 400


def test_beide_betriebsarten(app_laden, monkeypatch, tmp_path):
    import conftest
    w, client, schrein = app_laden(RAHMEN_WEB_AUTH="beide", RAHMEN_WEB_BENUTZER_FILE=str(tmp_path / "benutzer.json"))
    monkeypatch.setattr(w, "immich_aufruf", conftest.SchreinAnmeldung())
    monkeypatch.setattr(w.time, "sleep", lambda s: None)
    c1, c2 = client("10.0.0.5"), client("10.0.0.6")
    assert c1.post("/api/login", json={"pin": "123456"}, headers=H).json() == {"ok": True}
    assert c2.post("/api/login", json={"email": "karl@example.org", "passwort": "karl-passwort"}, headers=H).json()["ok"] is True
    assert c1.get("/api/me").json()["angemeldet"] and c2.get("/api/me").json()["name"] == "Karl"


def test_widerrufener_schluessel_erzwingt_neue_anmeldung(app_laden, monkeypatch, tmp_path):
    import urllib.error
    w, client, schrein, anm = immich_app(app_laden, monkeypatch, tmp=tmp_path)
    c = client("10.0.0.5")
    anmelden(c)
    def abgelehnt(method, path, body=None, timeout=120):
        raise urllib.error.HTTPError("x", 401, "nein", {}, None)
    monkeypatch.setattr(w.H, "api", abgelehnt)
    assert c.get("/api/facetten?typ=foto").status_code == 401           # Immich lehnt den Schluessel ab -> Client zeigt wieder die Anmeldung


def test_ausgestellter_schluessel_wird_wiederverwendet(app_laden, monkeypatch, tmp_path):
    w, client, schrein, anm = immich_app(app_laden, monkeypatch, tmp=tmp_path)
    anmelden(client("10.0.0.5")); anmelden(client("10.0.0.5"))
    assert len(anm.schluessel) == 1                                       # zweite Anmeldung legt keinen weiteren Schluessel an


def test_geraet_holt_fotos_mit_dem_schluessel_des_absenders(app_laden, monkeypatch, tmp_path):
    import conftest
    w, client, schrein, anm = immich_app(app_laden, monkeypatch, tmp=tmp_path, RAHMEN_WEB_RAHMEN_ZIELE="rahmen=Rahmen")
    gesehen = []
    monkeypatch.setattr(w, "immich_roh", lambda pfad, timeout=60, schluessel=None: (gesehen.append(schluessel) or (b"x", "image/jpeg")))
    a = client("10.0.0.5")
    anmelden(a)
    ids = [x["id"] for x in conftest.ASSETS[:3]]
    a.post("/api/anzeigen", json={"name": "S", "ids": ids}, headers=H)
    tv = client("192.168.1.50")                                            # Rahmen im LAN, nicht angemeldet
    assert tv.get(f"/api/vorschau/{ids[0]}?s=gross").status_code == 200
    assert gesehen[-1] == anm.schluessel["aaaaaaaa-0000-4000-8000-00000000000a"]
    tv.get(f"/api/vorschau/{conftest._id(77)}?s=gross")                    # nicht in der Show -> Dienstschluessel
    assert gesehen[-1] is None


def test_aliase_aus_der_umgebung(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_ALIASE="oma=Anna Muster; opa = Opa Karl;kaputt")
    named, alias = w.H.lade_personen()
    assert alias == {"oma": "Anna Muster", "opa": "Opa Karl"}


def test_pushover_aus_der_umgebung(app_laden, monkeypatch):
    w, client, _ = app_laden(RAHMEN_WEB_PUSHOVER_API_KEY="tok", RAHMEN_WEB_PUSHOVER_USER_KEY="usr")
    gesendet = []
    monkeypatch.setattr(w.urllib.request, "urlopen", lambda url, data=None, timeout=0: gesendet.append((url, data)) or type("R", (), {"read": lambda s: b"{}"})())
    w.pushover("Titel", "Text")
    assert gesendet and b"token=tok" in gesendet[0][1] and b"user=usr" in gesendet[0][1]


def test_motivsuche_faellt_ohne_ml_auf_suche_ohne_motiv_zurueck(app_laden, monkeypatch):
    import urllib.error
    w, client, schrein = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24")
    echt = w.H.api

    def api(method, path, body=None, timeout=120):
        if path == "/search/smart":
            raise urllib.error.HTTPError("x", 500, "ML aus", {}, None)
        return echt(method, path, body, timeout)
    monkeypatch.setattr(w.H, "api", api)
    d = client().get("/api/suche?text=Strand%202020").json()
    assert d["ok"] and d["fotos"] and "nicht verfuegbar" in d["nachricht"]          # Zeitraum 2020 liefert trotzdem Fotos
    d2 = client().get("/api/suche?text=Strand").json()
    assert d2["ok"] is False and "Bildsuche" in d2["nachricht"]


def test_diagnose_ohne_geheimnisse(app_laden):
    import json
    w, client, _ = app_laden(RAHMEN_WEB_LAN="192.168.1.0/24", RAHMEN_IMMICH_KEY="SUPERGEHEIMER-SCHLUESSEL-12345", RAHMEN_WEB_PUSHOVER_API_KEY="pushover-token-abc")
    w.H.log.warning("Test: der Schluessel SUPERGEHEIMER-SCHLUESSEL-12345 und pushover-token-abc stehen hier, ebenso http://benutzer:passwort@host/x und %s", "A" * 40)
    r = client().get("/api/diagnose")
    assert r.status_code == 200
    d = r.json()
    roh = json.dumps(d)
    assert "SUPERGEHEIMER" not in roh and "pushover-token-abc" not in roh and "passwort@" not in roh and "A" * 40 not in roh
    assert d["version"] == w.VERSION and d["einstellungen"]["auth"] == "pin" and "immich" in d and isinstance(d["protokoll"], list)
    assert any("Test:" in z for z in d["protokoll"])


def test_diagnose_braucht_anmeldung(app_laden):
    w, client, _ = app_laden()
    assert client("10.0.0.5").get("/api/diagnose").status_code == 401
