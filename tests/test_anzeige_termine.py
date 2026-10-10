"""Einblendungen am Rahmen (Layout je Element) und Termine aus den Kalendern der Handys."""
import datetime

import anzeige as ANZ
import telefontermine as TT

H = {"X-Rahmen": "1"}
LAN = {"RAHMEN_WEB_LAN": "192.168.1.0/24", "RAHMEN_WEB_RAHMEN_ZIELE": "flur=Flur"}
QUELLE = "11111111-2222-3333-4444-555555555555"


# ---------------------------------------------------------------- Layout
def test_standard_entspricht_dem_bisherigen_aussehen():
    l = ANZ.zusammen()
    assert l["uhr"]["an"] and (l["uhr"]["x"], l["uhr"]["y"]) == (0, 100)                 # Uhr unten links
    assert l["wetter"]["an"] and (l["wetter"]["x"], l["wetter"]["y"]) == (100, 0)         # Wetter oben rechts
    assert not l["heute"]["an"] and not l["fotodatum"]["an"] and not l["fotoort"]["an"]


def test_alte_bildunterschrift_wird_zum_layout():
    l = ANZ.zusammen(ANZ.aus_anzeige(["datum", "ort"]))
    assert l["fotodatum"]["an"] and not l["fotodatum"]["zeit"] and l["fotoort"]["an"]
    assert ANZ.zusammen(ANZ.aus_anzeige(["zeit"]))["fotodatum"]["zeit"]
    assert ANZ.aus_anzeige([]) == {} and ANZ.aus_anzeige(["quatsch"]) == {}


def test_spaetere_schicht_gewinnt_feldweise():
    l = ANZ.zusammen({"uhr": {"x": 50, "y": 50, "gr": 150}}, {"uhr": {"an": False}})
    assert (l["uhr"]["an"], l["uhr"]["x"], l["uhr"]["y"], l["uhr"]["gr"]) == (False, 50, 50, 150)


def test_pruefen_nimmt_nur_gueltiges():
    assert ANZ.pruefen({"uhr": {"an": True, "x": "12.34", "y": 100, "gr": "120"}}) == {"uhr": {"an": True, "x": 12.3, "y": 100.0, "gr": 120}}
    assert ANZ.pruefen({"uhr": {"zeit": True}}) == {}                                     # zeit gibt es nur beim Foto-Datum
    assert ANZ.pruefen({"fotodatum": {"zeit": True}}) == {"fotodatum": {"zeit": True}}
    for schlecht in ({"gibtsnicht": {"an": True}}, {"uhr": {"x": 101}}, {"uhr": {"x": -1}}, {"uhr": {"gr": 5}}, {"uhr": {"gr": 999}}, {"uhr": {"an": "ja"}}, {"uhr": 5}, [1], {"uhr": {"x": "abc"}}):
        try:
            ANZ.pruefen(schlecht)
        except ValueError:
            continue
        raise AssertionError(f"nicht abgelehnt: {schlecht}")


def test_layout_in_den_einstellungen_und_am_geraet(app_laden):
    w, client, _ = app_laden(**LAN)
    app = client("192.168.1.50")
    assert app.get("/api/config?ziel=flur").json()["rahmen_layout"]["uhr"]["x"] == 0
    r = app.put("/api/einstellungen", json={"layout": {"uhr": {"x": 100, "y": 100}, "heute": {"an": True}}}, headers=H)
    assert r.status_code == 200
    cfg = app.get("/api/config?ziel=flur").json()["rahmen_layout"]
    assert cfg["uhr"]["x"] == 100 and cfg["heute"]["an"]
    # eigene Anordnung am Geraet gewinnt, der Rest bleibt allgemein
    r = app.put("/api/verwaltung/geraete/flur", json={"layout": {"uhr": {"x": 50, "y": 0}}}, headers=H)
    assert r.status_code == 200 and r.json()["geraet"]["layout_eigen"]
    cfg = app.get("/api/config?ziel=flur").json()["rahmen_layout"]
    assert cfg["uhr"]["x"] == 50 and cfg["uhr"]["y"] == 0 and cfg["heute"]["an"]
    # zurueck auf "wie allgemein"
    r = app.put("/api/verwaltung/geraete/flur", json={"layout": None}, headers=H)
    assert not r.json()["geraet"]["layout_eigen"] and app.get("/api/config?ziel=flur").json()["rahmen_layout"]["uhr"]["x"] == 100


def test_ungueltiges_layout_wird_abgelehnt(app_laden):
    w, client, _ = app_laden(**LAN)
    app = client("192.168.1.50")
    assert app.put("/api/einstellungen", json={"layout": {"uhr": {"x": 500}}}, headers=H).status_code == 400
    assert app.put("/api/verwaltung/geraete/flur", json={"layout": {"gibtsnicht": {}}}, headers=H).status_code == 400
    assert app.put("/api/einstellungen", json={"layout": {"uhr": {"x": 1}}}).status_code == 403          # ohne X-Rahmen


def test_alte_bildunterschrift_wirkt_weiter_im_layout(app_laden):
    w, client, _ = app_laden(**LAN, RAHMEN_WEB_RAHMEN_ANZEIGE="datum,ort")
    l = client("192.168.1.50").get("/api/config?ziel=flur").json()["rahmen_layout"]
    assert l["fotodatum"]["an"] and l["fotoort"]["an"]


# ---------------------------------------------------------------- Termine der Handys
def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M")


def test_ereignisse_und_naechste():
    jetzt = datetime.datetime(2026, 10, 10, 14, 30)
    heute = jetzt.date()
    daten = TT.quelle_setzen({}, QUELLE, "Dirk", [
        {"titel": "Frühstück", "von": "2026-10-10T08:00", "bis": "2026-10-10T09:00"},              # vorbei
        {"titel": "Zahnarzt", "von": "2026-10-10T14:00", "bis": "2026-10-10T15:00"},               # laeuft
        {"titel": "Training", "von": "2026-10-10T18:30"},                                          # kommt
        {"titel": "Geburtstag Oma", "von": "2026-10-10", "bis": "2026-10-11"},                     # ganztaegig (Ende exklusiv)
        {"titel": "Urlaub", "von": "2026-10-09", "bis": "2026-10-12"},                             # mehrtaegig
        {"titel": "Schule", "von": "2026-10-11T08:00"},                                            # morgen
        {"titel": "kaputt", "von": "gestern"},                                                     # wird verworfen
    ], jetzt)
    assert len(daten[QUELLE]["termine"]) == 6
    liste = TT.ereignisse(daten, heute)
    n = TT.naechste(liste, jetzt)
    assert [t["titel"] for t in n] == ["Geburtstag Oma", "Urlaub", "Zahnarzt", "Training"]       # ganztaegig zuerst, dann nach Uhrzeit
    assert n[2]["zeit"] == "14:00" and n[0]["zeit"] == "" and all(t["tag"] == "heute" for t in n)
    # abends: es bleibt nur noch Ganztaegiges; ist auch das weg, kommt der naechste Tag
    spaet = datetime.datetime(2026, 10, 10, 23, 30)
    assert [t["titel"] for t in TT.naechste(liste, spaet)] == ["Geburtstag Oma", "Urlaub"]
    nur_zeit = [e for e in liste if e["zeit"]]
    assert [(t["tag"], t["titel"]) for t in TT.naechste(nur_zeit, spaet)] == [("morgen", "Schule")]


def test_ohne_endzeit_gilt_eine_stunde():
    jetzt = datetime.datetime(2026, 10, 10, 10, 30)
    liste = [{"tag": "heute", "zeit": "09:45", "titel": "läuft noch"}, {"tag": "heute", "zeit": "09:15", "titel": "vorbei"}]
    assert [t["titel"] for t in TT.naechste(liste, jetzt)] == ["läuft noch"]


def test_quelle_pruefen_und_grenzen():
    jetzt = datetime.datetime(2026, 10, 10, 12, 0)
    for schlecht in ("", "kurz", "mit leerzeichen!!", "x" * 80):
        try:
            TT.quelle_setzen({}, schlecht, "A", [], jetzt)
        except ValueError:
            continue
        raise AssertionError(schlecht)
    try:
        TT.quelle_setzen({}, QUELLE, "A", [{"titel": "x", "von": "2026-10-10"}] * 401, jetzt)
        raise AssertionError("zu viele")
    except ValueError:
        pass
    voll = {f"quelle-{i:03d}-abcdef": {"name": "x", "aktualisiert": jetzt.isoformat(), "termine": []} for i in range(TT.MAX_QUELLEN)}
    try:
        TT.quelle_setzen(voll, QUELLE, "A", [], jetzt)
        raise AssertionError("zu viele Handys")
    except ValueError:
        pass
    alt = {"altes-handy-1234": {"name": "alt", "aktualisiert": "2025-01-01T00:00:00", "termine": []}}
    assert "altes-handy-1234" not in TT.quelle_setzen(alt, QUELLE, "A", [], jetzt)                    # sehr alte Handys werden aufgeraeumt
    assert TT.quelle_setzen({}, QUELLE, "  Dirks   iPhone ", [], jetzt)[QUELLE]["name"] == "Dirks iPhone"


def test_handy_termine_erscheinen_am_rahmen(app_laden):
    w, client, _ = app_laden(**LAN)
    app = client("192.168.1.50")
    jetzt = datetime.datetime.now()
    heute = jetzt.replace(hour=23, minute=0, second=0, microsecond=0)
    assert "kalender" not in app.get("/api/config?ziel=flur").json()["rahmen_zusatz"]                # noch nichts eingerichtet
    r = app.put("/api/termine/telefon", json={"quelle": QUELLE, "name": "Dirks iPhone", "termine": [
        {"titel": "Abendessen", "von": iso(heute), "bis": iso(heute + datetime.timedelta(minutes=30))}]}, headers=H)
    assert r.status_code == 200 and r.json()["anzahl"] == 1
    assert "kalender" not in app.get("/api/config?ziel=flur").json()["rahmen_zusatz"]                # neues Handy: auf keinem Rahmen, bis es freigegeben ist
    app.put("/api/verwaltung/geraete/flur", json={"termin_quellen": [QUELLE]}, headers=H)
    assert "kalender" in app.get("/api/config?ziel=flur").json()["rahmen_zusatz"]
    z = app.get("/api/rahmen/zusatz?ziel=flur").json()
    assert z["termine"] == [{"tag": "heute", "zeit": "23:00", "titel": "Abendessen"}] or jetzt.hour == 23     # (kurz vor Mitternacht kann der Termin schon vorbei sein)
    liste = app.get("/api/termine/telefon").json()["quellen"]
    assert liste == [{"id": QUELLE, "name": "Dirks iPhone", "anzahl": 1, "aktualisiert": liste[0]["aktualisiert"], "kuerzel": "", "farbe": ""}]
    # bleibt nach einem Neustart erhalten
    assert w.lies_json(w.TERMINE_FILE, {})[QUELLE]["termine"][0]["titel"] == "Abendessen"
    assert app.delete(f"/api/termine/telefon/{QUELLE}", headers=H).status_code == 200
    assert app.delete(f"/api/termine/telefon/{QUELLE}", headers=H).status_code == 404
    assert app.get("/api/termine/telefon").json()["quellen"] == []


def test_handy_termine_brauchen_anmeldung_und_header(app_laden):
    w, client, _ = app_laden(**LAN)
    fremd = client("203.0.113.9")
    assert fremd.put("/api/termine/telefon", json={"quelle": QUELLE, "termine": []}, headers=H).status_code == 401
    assert fremd.get("/api/termine/telefon").status_code == 401
    assert client("192.168.1.50").put("/api/termine/telefon", json={"quelle": QUELLE, "termine": []}).status_code == 403
    assert client("192.168.1.50").put("/api/termine/telefon", json={"quelle": "zu kurz", "termine": []}, headers=H).status_code == 400


def test_rahmen_erfaehrt_aenderungen_ohne_neuladen(app_laden):
    """Die 2-Sekunden-Abfrage des Rahmens liefert eine Kennung ('lv'); aendert sich Anordnung oder Handy-Termine, aendert sie sich."""
    w, client, _ = app_laden(**LAN)
    app = client("192.168.1.50")
    lv = lambda: app.get("/api/tv/abfrage?ziel=flur&seq=-1").json()["lv"]
    a = lv()
    assert a == lv()                                                                                   # unveraendert = gleich
    app.put("/api/einstellungen", json={"layout": {"uhr": {"x": 50}}}, headers=H)
    b = lv()
    assert b != a
    app.put("/api/verwaltung/geraete/flur", json={"layout": {"uhr": {"y": 0}}}, headers=H)
    c = lv()
    assert c != b
    app.put("/api/termine/telefon", json={"quelle": QUELLE, "name": "x", "termine": []}, headers=H)
    assert lv() == c                                                                                     # Handy noch nicht fuer diesen Rahmen freigegeben
    app.put("/api/verwaltung/geraete/flur", json={"termin_quellen": [QUELLE]}, headers=H)
    d = lv()
    assert d != c
    app.put("/api/termine/telefon", json={"quelle": QUELLE, "name": "x", "termine": [{"titel": "t", "von": "2026-10-10"}]}, headers=H)
    assert lv() != d

# ---------------------------------------------------------------- Farbe, Schrift, Show-Titel, Geburtstage, Personen
def test_standard_hat_alle_elemente_mit_farbe_und_schrift():
    l = ANZ.zusammen()
    assert set(l) == set(ANZ.ELEMENTE) and {"geburtstag", "titel"} <= set(l)
    assert all(w["farbe"] == "" and w["schrift"] == "" for w in l.values())
    assert l["termine"]["person"] is True and l["geburtstag"]["an"] and l["titel"]["an"]


def test_farbe_schrift_person_pruefen():
    assert ANZ.pruefen({"uhr": {"farbe": "#FFAA00", "schrift": "mono"}}) == {"uhr": {"farbe": "#ffaa00", "schrift": "mono"}}
    assert ANZ.pruefen({"uhr": {"farbe": "", "schrift": ""}}) == {"uhr": {"farbe": "", "schrift": ""}}
    assert ANZ.pruefen({"termine": {"person": False}}) == {"termine": {"person": False}}
    assert ANZ.pruefen({"uhr": {"person": True}}) == {}                                   # person gibt es nur bei den Terminen
    for schlecht in ({"uhr": {"farbe": "rot"}}, {"uhr": {"farbe": "#12345"}}, {"uhr": {"farbe": "#12345g"}}, {"uhr": {"farbe": 5}}, {"uhr": {"schrift": "comic"}}):
        try:
            ANZ.pruefen(schlecht)
        except ValueError:
            continue
        raise AssertionError(f"nicht abgelehnt: {schlecht}")


def test_geburtstage_haben_ein_eigenes_element():
    jetzt = datetime.datetime(2026, 10, 10, 9, 0)
    daten = TT.quelle_setzen({}, QUELLE, "Dirk", [
        {"titel": "Omas Geburtstag", "von": "2026-10-10", "bis": "2026-10-11", "geburtstag": True},
        {"titel": "Opas Geburtstag", "von": "2026-10-11", "bis": "2026-10-12", "geburtstag": True},        # morgen
        {"titel": "Zahnarzt", "von": "2026-10-10T14:00"}], jetzt)
    liste = TT.ereignisse(daten, jetzt.date())
    assert TT.geburtstage(liste) == ["Omas Geburtstag"]
    assert [t["titel"] for t in TT.naechste(liste, jetzt)] == ["Zahnarzt"]                 # nicht doppelt in der Terminliste
    assert TT.geburtstage(liste + liste) == ["Omas Geburtstag"]


def test_personen_kuerzel_nur_bei_mehreren_handys():
    jetzt = datetime.datetime(2026, 10, 10, 9, 0)
    t = [{"titel": "Zahnarzt", "von": "2026-10-10T14:00"}]
    daten = TT.quelle_setzen({}, QUELLE, "Dirk", t, jetzt, "d", "#E0A24A")
    assert daten[QUELLE]["kuerzel"] == "d" and daten[QUELLE]["farbe"] == "#e0a24a"
    assert TT.quelle_setzen({}, QUELLE, "x", t, jetzt, "ABC", "grün")[QUELLE].get("farbe") is None           # ungueltige Farbe wird ignoriert
    assert TT.quelle_setzen({}, QUELLE, "x", t, jetzt, "ABC", "")[QUELLE]["kuerzel"] == "AB"               # hoechstens 2 Zeichen
    n = TT.naechste(TT.ereignisse(daten, jetzt.date()), jetzt)
    assert n[0]["p"] == {"k": "d", "f": "#e0a24a"}
    assert "p" not in TT.naechste(TT.ereignisse(daten, jetzt.date()), jetzt, personen=False)[0]


def test_geburtstage_und_personen_am_rahmen(app_laden):
    w, client, _ = app_laden(**LAN)
    app = client("192.168.1.50")
    heute = datetime.date.today()
    spaet = datetime.datetime.combine(heute, datetime.time(23, 50))
    app.put("/api/verwaltung/geraete/flur", json={"termin_quellen": ["aaaaaaaa-0001", "bbbbbbbb-0002"]}, headers=H)
    for quelle, kuerzel in (("aaaaaaaa-0001", "D"), ("bbbbbbbb-0002", "S")):
        app.put("/api/termine/telefon", json={"quelle": quelle, "name": kuerzel, "kuerzel": kuerzel, "farbe": "#336699", "termine": [
            {"titel": "Omas Geburtstag", "von": heute.isoformat(), "bis": (heute + datetime.timedelta(days=1)).isoformat(), "geburtstag": True},
            {"titel": "Termin " + kuerzel, "von": iso(spaet)}]}, headers=H)
    z = app.get("/api/rahmen/zusatz?ziel=flur").json()
    assert z["geburtstage"] == ["Omas Geburtstag"]
    termine = z["termine"]
    assert {t["titel"] for t in termine} <= {"Termin D", "Termin S"}
    assert all(t.get("p", {}).get("k") in ("D", "S") for t in termine)                       # zwei Handys: Kuerzel dabei
    app.delete("/api/termine/telefon/bbbbbbbb-0002", headers=H)
    assert all("p" not in t for t in app.get("/api/rahmen/zusatz?ziel=flur").json()["termine"])   # nur noch ein Handy: kein Kuerzel


def test_gespeichertes_layout_schlaegt_alte_bildunterschrift_am_geraet(app_laden):
    """Ein Geraet mit der alten Einstellung 'Bildunterschrift' darf das im Editor gespeicherte Layout nicht uebersteuern."""
    w, client, _ = app_laden(**LAN)
    app = client("192.168.1.50")
    app.put("/api/verwaltung/geraete/flur", json={"anzeige": ["datum", "ort"]}, headers=H)
    cfg = lambda: app.get("/api/config?ziel=flur").json()["rahmen_layout"]
    assert cfg()["fotoort"]["an"] and cfg()["fotodatum"]["an"]                                      # Ausgangspunkt: die alte Einstellung
    app.put("/api/einstellungen", json={"layout": {"fotoort": {"an": False}}}, headers=H)            # im Editor ausgeschaltet
    assert not cfg()["fotoort"]["an"] and cfg()["fotodatum"]["an"]


# ---------------------------------------------------------------- Anzeige pro Rahmen
ZWEI = {"RAHMEN_WEB_LAN": "192.168.1.0/24", "RAHMEN_WEB_RAHMEN_ZIELE": "flur=Flur,serbien=Serbien"}


def test_handys_je_rahmen_freigeben(app_laden):
    w, client, _ = app_laden(**ZWEI)
    app = client("192.168.1.50")
    spaet = datetime.datetime.combine(datetime.date.today(), datetime.time(23, 50))
    app.put("/api/termine/telefon", json={"quelle": QUELLE, "name": "Dirk", "termine": [{"titel": "Privat", "von": iso(spaet)}]}, headers=H)
    zusatz = lambda z: app.get(f"/api/rahmen/zusatz?ziel={z}").json()
    assert zusatz("flur").get("termine", []) == [] and zusatz("serbien").get("termine", []) == []        # neues Handy: nirgends
    app.put("/api/verwaltung/geraete/flur", json={"termin_quellen": [QUELLE]}, headers=H)
    assert [t["titel"] for t in zusatz("flur")["termine"]] == ["Privat"]
    assert zusatz("serbien").get("termine", []) == []                                                     # auf dem anderen Rahmen bleibt es unsichtbar
    assert app.put("/api/verwaltung/geraete/flur", json={"termin_quellen": ["ungueltig!"]}, headers=H).status_code == 400
    assert app.put("/api/verwaltung/geraete/flur", json={"termin_quellen": "x"}, headers=H).status_code == 400
    assert [h["id"] for h in app.get("/api/verwaltung").json()["telefone"]] == [QUELLE]


def test_wetter_ort_und_kalender_link_je_rahmen(app_laden, monkeypatch):
    w, client, _ = app_laden(**ZWEI)
    app = client("192.168.1.50")
    app.put("/api/einstellungen", json={"wetter": {"lat": 51.3, "lon": 6.8, "name": "Ratingen"}}, headers=H)
    assert w.wetter_ort("flur") == (51.3, 6.8) and w.wetter_ort("serbien") == (51.3, 6.8)                # ohne eigenen Ort gilt der allgemeine
    r = app.put("/api/verwaltung/geraete/serbien", json={"wetter": {"lat": 44.8, "lon": 20.46, "name": "Belgrad"}}, headers=H)
    assert r.status_code == 200 and r.json()["geraet"]["wetter"]["name"] == "Belgrad"
    assert w.wetter_ort("serbien") == (44.8, 20.46) and w.wetter_ort("flur") == (51.3, 6.8)
    gefragt = []
    monkeypatch.setattr(w, "http_text", lambda url, timeout=10: gefragt.append(url) or '{"current": {"temperature_2m": 9.4, "weather_code": 0}}')
    assert app.get("/api/rahmen/zusatz?ziel=serbien").json()["wetter"]["temp"] == 9 and "latitude=44.8" in gefragt[-1]
    assert app.get("/api/rahmen/zusatz?ziel=flur").json()["wetter"]["temp"] == 9 and "latitude=51.3" in gefragt[-1]
    assert app.put("/api/verwaltung/geraete/serbien", json={"wetter": {"lat": 999, "lon": 0}}, headers=H).status_code == 400
    assert app.put("/api/verwaltung/geraete/serbien", json={"wetter": None}, headers=H).json()["geraet"]["wetter"] is None
    assert w.wetter_ort("serbien") == (51.3, 6.8)
    # Kalender-Link je Rahmen
    assert app.put("/api/verwaltung/geraete/serbien", json={"kalender_url": "kein-link"}, headers=H).status_code == 400
    r = app.put("/api/verwaltung/geraete/serbien", json={"kalender_url": "https://example.org/serbien.ics"}, headers=H)
    assert r.json()["geraet"]["kalender_gesetzt"] and w.kalender_url("serbien") == "https://example.org/serbien.ics" and not w.kalender_url("flur")


def test_neuer_rahmen_startet_mit_standardwerten(app_laden):
    w, client, _ = app_laden(**ZWEI)
    app = client("192.168.1.50")
    app.put("/api/einstellungen", json={"layout": {"uhr": {"x": 77}}}, headers=H)                        # alte allgemeine Anordnung (aus 2.18.x)
    assert app.get("/api/config?ziel=flur").json()["rahmen_layout"]["uhr"]["x"] == 77                    # bestehende Rahmen erben sie weiter
    r = app.post("/api/verwaltung/geraete", json={"art": "rahmen", "name": "Kueche"}, headers=H).json()
    neu = r["id"]
    assert r["geraet"]["layout"] == ANZ.zusammen() and r["geraet"]["termin_quellen"] == []               # ein neuer Rahmen: Standard, keine Handys
    assert app.get(f"/api/config?ziel={neu}").json()["rahmen_layout"]["uhr"]["x"] == 0


def test_update_uebernimmt_bekannte_handys_fuer_bestehende_rahmen(app_laden):
    """Rahmen aus einer Version ohne Freigaben zeigen weiter die bis dahin bekannten Handys; spaetere Handys muessen freigegeben werden."""
    w, client, _ = app_laden(**ZWEI)
    app = client("192.168.1.50")
    app.put("/api/verwaltung/geraete/flur", json={"name": "Flur"}, headers=H)                            # legt die Geraetedatei an
    w.TELEFON.update({QUELLE: {"name": "Dirk", "aktualisiert": "2026-10-10T08:00:00", "termine": []}})
    for e in w.GERAETE.values():
        e.pop("termin_quellen", None)                                                                     # Stand vor dem Update
    w.handys_freigaben_migrieren()
    assert w.GERAETE["flur"]["termin_quellen"] == [QUELLE] and w.GERAETE["serbien"]["termin_quellen"] == [QUELLE]
    w.TELEFON["cccccccc-0003"] = {"name": "Neu", "aktualisiert": "2026-10-10T09:00:00", "termine": []}
    w.handys_freigaben_migrieren()                                                                        # zweiter Lauf aendert nichts
    assert w.GERAETE["flur"]["termin_quellen"] == [QUELLE]


def test_datumsformat_des_aufnahmedatums():
    assert ANZ.zusammen()["fotodatum"]["format"] == "lang"
    assert ANZ.pruefen({"fotodatum": {"format": "kurz"}}) == {"fotodatum": {"format": "kurz"}}
    assert ANZ.pruefen({"uhr": {"format": "kurz"}}) == {}                                    # nur beim Foto-Datum
    try:
        ANZ.pruefen({"fotodatum": {"format": "komisch"}})
        raise AssertionError("nicht abgelehnt")
    except ValueError:
        pass


def test_zoom_und_hochformat_paare_je_rahmen(app_laden):
    w, client, _ = app_laden(**ZWEI)
    app = client("192.168.1.50")
    cfg = lambda z: app.get(f"/api/config?ziel={z}").json()
    assert cfg("flur")["rahmen_bewegung"] is False and cfg("flur")["rahmen_paare"] is False               # Standard: aus
    lv = app.get("/api/tv/abfrage?ziel=flur&seq=-1").json()["lv"]
    r = app.put("/api/verwaltung/geraete/flur", json={"bewegung": True, "paare": True}, headers=H)
    assert r.status_code == 200 and r.json()["geraet"]["bewegung"] and r.json()["geraet"]["paare"]
    assert cfg("flur")["rahmen_bewegung"] and cfg("flur")["rahmen_paare"] and not cfg("serbien")["rahmen_bewegung"]
    assert app.get("/api/tv/abfrage?ziel=flur&seq=-1").json()["lv"] != lv                                  # laufender Rahmen laedt neu
    assert app.put("/api/verwaltung/geraete/flur", json={"paare": "ja"}, headers=H).status_code == 400
    app.put("/api/verwaltung/geraete/flur", json={"bewegung": False}, headers=H)
    assert not cfg("flur")["rahmen_bewegung"] and cfg("flur")["rahmen_paare"]


def test_notiz_an_den_rahmen(app_laden):
    w, client, _ = app_laden(**ZWEI)
    app = client("192.168.1.50")
    zusatz = lambda z: app.get(f"/api/rahmen/zusatz?ziel={z}").json()
    assert "notiz" not in zusatz("flur")
    lv = app.get("/api/tv/abfrage?ziel=flur&seq=-1").json()["lv"]
    r = app.put("/api/notizen/flur", json={"text": "  Heute Abend   Pizza 🍕 ", "stunden": 3}, headers=H)
    assert r.status_code == 200 and r.json()["text"] == "Heute Abend Pizza 🍕"
    assert zusatz("flur")["notiz"] == "Heute Abend Pizza 🍕" and "notiz" not in zusatz("serbien")        # nur dieser Rahmen
    assert app.get("/api/tv/abfrage?ziel=flur&seq=-1").json()["lv"] != lv                              # laufender Rahmen laedt neu
    assert app.get("/api/notizen/flur").json()["text"] == "Heute Abend Pizza 🍕"
    assert w.lies_json(w.NOTIZEN_FILE, {})["flur"]["text"] == "Heute Abend Pizza 🍕"
    # abgelaufen
    assert w.notiz_fuer("flur", datetime.datetime.now() + datetime.timedelta(hours=4)) == ""
    assert w.notiz_fuer("flur", datetime.datetime.now() + datetime.timedelta(hours=2)) != ""
    # entfernen, Grenzen, Schutz
    assert app.put("/api/notizen/flur", json={"text": ""}, headers=H).json()["text"] == "" and "notiz" not in zusatz("flur")
    assert app.put("/api/notizen/gibtsnicht", json={"text": "x"}, headers=H).status_code == 404
    assert app.put("/api/notizen/flur", json={"text": "x", "stunden": "abc"}, headers=H).status_code == 400
    assert len(app.put("/api/notizen/flur", json={"text": "a" * 500, "stunden": 1}, headers=H).json()["text"]) == w.NOTIZ_MAX
    assert app.put("/api/notizen/flur", json={"text": "x"}).status_code == 403
    assert client("203.0.113.9").put("/api/notizen/flur", json={"text": "x"}, headers=H).status_code == 401
    assert ANZ.zusammen()["notiz"]["an"]


def test_erinnerungen_und_geburtstagsfotos_im_dauerprogramm(app_laden, monkeypatch):
    w, client, _ = app_laden(**ZWEI)
    app = client("192.168.1.50")
    typen = lambda: [q["typ"] for q in w.rahmen_quellen("flur")]
    assert "heute" not in typen()                                                                           # Standard: aus
    assert app.put("/api/verwaltung/geraete/flur", json={"erinnerungen": "komisch"}, headers=H).status_code == 400
    r = app.put("/api/verwaltung/geraete/flur", json={"erinnerungen": "oft"}, headers=H)
    assert r.json()["geraet"]["erinnerungen"] == "oft" and "heute" in typen()
    assert [q["gewicht"] for q in w.rahmen_quellen("flur") if q["typ"] == "heute"] == [0.4] and "heute" not in [q["typ"] for q in w.rahmen_quellen("serbien")]
    app.put("/api/verwaltung/geraete/flur", json={"erinnerungen": ""}, headers=H)
    assert "heute" not in typen()
    # Geburtstag: 'Omas Geburtstag' -> Person 'Oma' (Spitzname fuer 'Anna Muster'); ohne Freigabe des Handys nichts
    monkeypatch.setitem(w.PERSONEN_CACHE, "t", w.time.time())
    monkeypatch.setitem(w.PERSONEN_CACHE, "named", [("Anna Muster", "p1"), ("Ben", "p2"), ("Al", "p3")])
    monkeypatch.setitem(w.PERSONEN_CACHE, "alias", {"oma": "Anna Muster"})
    heute = datetime.date.today()
    app.put("/api/termine/telefon", json={"quelle": QUELLE, "name": "x", "termine": [
        {"titel": "Omas Geburtstag", "von": heute.isoformat(), "bis": (heute + datetime.timedelta(days=1)).isoformat(), "geburtstag": True},
        {"titel": "Als Geburtstag", "von": heute.isoformat(), "bis": (heute + datetime.timedelta(days=1)).isoformat(), "geburtstag": True}]}, headers=H)
    assert w.geburtstag_personen("flur") == []                                                              # Handy nicht freigegeben
    app.put("/api/verwaltung/geraete/flur", json={"termin_quellen": [QUELLE]}, headers=H)
    assert w.geburtstag_personen("flur") == ["Anna Muster"]                                                 # 'Al' ist zu kurz fuer einen Treffer
    assert {"typ": "person", "namen": ["Anna Muster"], "gewicht": 0.6} in w.rahmen_quellen("flur")
    app.put("/api/verwaltung/geraete/flur", json={"geburtstagsfotos": False}, headers=H)
    assert not any(q["typ"] == "person" for q in w.rahmen_quellen("flur"))
    assert app.put("/api/verwaltung/geraete/flur", json={"geburtstagsfotos": "ja"}, headers=H).status_code == 400
    assert ANZ.zusammen()["erinnerung"]["an"]


def test_sonnenzeiten_und_nachtruhe_nach_sonnenstand(app_laden, monkeypatch):
    import os
    import time
    import sonne
    monkeypatch.setenv("TZ", "Europe/Berlin")
    time.tzset()
    auf, unter = sonne.sonnenzeiten(51.3, 6.85, datetime.date(2026, 10, 10))                          # Ratingen: Sommerzeit, Aufgang ~07:35, Untergang ~18:50
    assert datetime.time(7, 25) <= auf.time() <= datetime.time(7, 45) and datetime.time(18, 40) <= unter.time() <= datetime.time(19, 0)
    auf_w, unter_w = sonne.sonnenzeiten(51.3, 6.85, datetime.date(2026, 12, 21))                     # Winter: kurze Tage
    assert datetime.time(8, 15) <= auf_w.time() <= datetime.time(8, 35) and datetime.time(16, 15) <= unter_w.time() <= datetime.time(16, 35)
    assert sonne.sonnenzeiten(80, 10, datetime.date(2026, 6, 21)) is None                              # Polartag
    w, client, _ = app_laden(**ZWEI)
    app = client("192.168.1.50")
    assert app.put("/api/verwaltung/geraete/flur", json={"nacht": "sonne"}, headers=H).json()["geraet"]["nacht"] == "sonne"
    assert w.rahmen_nacht("flur") == ""                                                                  # ohne Wetter-Ort keine Berechnung
    app.put("/api/einstellungen", json={"wetter": {"lat": 51.3, "lon": 6.85, "name": "Ratingen"}}, headers=H)
    von, bis = w.rahmen_nacht("flur", datetime.datetime(2026, 10, 10, 12, 0)).split("-")
    assert von.startswith("18:") and bis.startswith("07:")
    assert app.get("/api/config?ziel=flur").json()["rahmen_nacht"] == w.rahmen_nacht("flur")
    assert app.put("/api/verwaltung/geraete/flur", json={"nacht": "22:00-06:30"}, headers=H).json()["geraet"]["nacht"] == "22:00-06:30"
    assert app.put("/api/verwaltung/geraete/flur", json={"nacht": "sonnig"}, headers=H).status_code == 400
    assert app.put("/api/verwaltung/geraete/flur", json={"nacht": ""}, headers=H).json()["geraet"]["nacht"] == ""


# ---------------------------------------------------------------- weitere Meldungen und Monatsbrief
def wache_vorbereiten(w, monkeypatch, immich_ok=True, frei=0.5):
    gesendet = []
    monkeypatch.setattr(w, "pushover", lambda titel, text, prio=0: gesendet.append((titel, text)))
    def aufruf(*a, **k):
        if not immich_ok:
            raise OSError("keine Verbindung")
        return {"major": 3, "minor": 3, "patch": 1}
    monkeypatch.setattr(w, "immich_aufruf", aufruf)

    class Platte:
        total, free = 100 * 2**30, int(100 * 2**30 * frei)
    monkeypatch.setattr(w.shutil, "disk_usage", lambda p: Platte)
    monkeypatch.setattr(w, "einst_speichern", lambda: None)
    return gesendet


def test_immich_ausfall_wird_nach_zehn_minuten_gemeldet(app_laden, monkeypatch):
    w, client, _ = app_laden(**ZWEI)
    gesendet = wache_vorbereiten(w, monkeypatch, immich_ok=False)
    t0 = datetime.datetime(2026, 10, 10, 12, 0)
    w.weitere_wache_pruefen(t0)
    w.weitere_wache_pruefen(t0 + datetime.timedelta(minutes=9))
    assert gesendet == []
    w.weitere_wache_pruefen(t0 + datetime.timedelta(minutes=10))
    w.weitere_wache_pruefen(t0 + datetime.timedelta(minutes=30))
    assert [g[0] for g in gesendet] == ["Immich nicht erreichbar"]                                      # nur einmal
    wache_vorbereiten(w, monkeypatch, immich_ok=True)
    gesendet2 = wache_vorbereiten(w, monkeypatch, immich_ok=True)
    w.weitere_wache_pruefen(t0 + datetime.timedelta(minutes=31))
    assert [g[0] for g in gesendet2] == ["Immich wieder erreichbar"]


def test_speicher_und_kalender_meldungen_und_abschalten(app_laden, monkeypatch):
    w, client, _ = app_laden(**ZWEI)
    app = client("192.168.1.50")
    gesendet = wache_vorbereiten(w, monkeypatch, frei=0.04)
    jetzt = datetime.datetime(2026, 10, 10, 12, 0)
    w.weitere_wache_pruefen(jetzt)
    w.weitere_wache_pruefen(jetzt + datetime.timedelta(minutes=5))
    assert [g[0] for g in gesendet] == ["Speicherplatz knapp"]                                          # einmal am Tag
    w.weitere_wache_pruefen(jetzt + datetime.timedelta(days=1))
    assert [g[0] for g in gesendet] == ["Speicherplatz knapp", "Speicherplatz knapp"]
    # Handy-Kalender: nur wenn ein Rahmen das Handy zeigt und es seit Tagen nichts gesendet hat
    gesendet.clear()
    w.TELEFON[QUELLE] = {"name": "Dirks iPhone", "aktualisiert": "2026-10-05T08:00:00", "termine": []}
    wache_vorbereiten(w, monkeypatch)
    g2 = wache_vorbereiten(w, monkeypatch)
    w.weitere_wache_pruefen(jetzt)
    assert g2 == []                                                                                      # auf keinem Rahmen freigegeben
    app.put("/api/verwaltung/geraete/flur", json={"termin_quellen": [QUELLE]}, headers=H)
    w.weitere_wache_pruefen(jetzt)
    assert [g[0] for g in g2] == ["Handy-Kalender nicht aktualisiert"] and "Dirks iPhone" in g2[0][1]
    w.weitere_wache_pruefen(jetzt + datetime.timedelta(hours=1))
    assert len(g2) == 1                                                                                  # nicht staendig wiederholen
    # abschalten in den Einstellungen
    assert app.put("/api/einstellungen", json={"meldungen": {"kalender": False, "speicher": False}}, headers=H).status_code == 200
    ansicht = app.get("/api/einstellungen").json()
    assert ansicht["meldungen"] == {"immich": True, "speicher": False, "kalender": False, "monat": True}
    w.weitere_wache_pruefen(jetzt + datetime.timedelta(days=2))
    assert len(g2) == 1
    assert app.put("/api/einstellungen", json={"meldungen": {"unbekannt": False}}, headers=H).status_code == 400
    assert app.put("/api/einstellungen", json={"meldungen": {"immich": "nein"}}, headers=H).status_code == 400


def test_monatsbrief_am_ersten_einmal(app_laden, monkeypatch):
    w, client, _ = app_laden(**ZWEI)
    gesendet = wache_vorbereiten(w, monkeypatch)
    monkeypatch.setattr(w.H, "api", lambda m, p, d=None: {"total": 1234} if p == "/search/statistics" else [])
    w.STATISTIK["2026-09"] = {"min_online": {"flur": 900, "serbien": 300}, "min_offline": {"flur": 100, "serbien": 700}, "ausfaelle": {"serbien": 2}}
    w.weitere_wache_pruefen(datetime.datetime(2026, 10, 1, 8, 0))                                        # zu frueh am Tag
    assert gesendet == []
    w.weitere_wache_pruefen(datetime.datetime(2026, 10, 1, 9, 30))
    assert len(gesendet) == 1 and gesendet[0][0] == "Dein Rückblick auf den September"
    text = gesendet[0][1]
    assert "1.234" in text and "Flur: 90 % erreichbar, keine Ausfälle" in text and "Serbien: 30 % erreichbar, 2 Ausfälle" in text
    w.weitere_wache_pruefen(datetime.datetime(2026, 10, 1, 18, 0))
    w.weitere_wache_pruefen(datetime.datetime(2026, 10, 2, 9, 30))
    assert len(gesendet) == 1                                                                            # einmal je Monat
    assert w.EINST["monatsbrief"] == "2026-09"
    # Januar: Vormonat ist Dezember des Vorjahres
    w.weitere_wache_pruefen(datetime.datetime(2027, 1, 1, 10, 0))
    assert gesendet[-1][0] == "Dein Rückblick auf den Dezember"


def test_favoriten_oefter_zeigen(app_laden):
    w, client, _ = app_laden(**ZWEI)
    app = client("192.168.1.50")
    assert not any(q["typ"] == "favoriten" for q in w.rahmen_quellen("flur"))
    assert app.put("/api/verwaltung/geraete/flur", json={"favoriten": "komisch"}, headers=H).status_code == 400
    r = app.put("/api/verwaltung/geraete/flur", json={"favoriten": "oft"}, headers=H)
    assert r.json()["geraet"]["favoriten"] == "oft" and {"typ": "favoriten", "gewicht": 0.4} in w.rahmen_quellen("flur")
    assert not any(q["typ"] == "favoriten" for q in w.rahmen_quellen("serbien"))
    app.put("/api/verwaltung/geraete/flur", json={"favoriten": ""}, headers=H)
    assert not any(q["typ"] == "favoriten" for q in w.rahmen_quellen("flur"))


def test_gruss_mit_foto_und_herz(app_laden, monkeypatch):
    w, client, _ = app_laden(**ZWEI)
    app = client("192.168.1.50")
    push = []
    monkeypatch.setattr(w, "pushover", lambda titel, text, prio=0: push.append((titel, text)))
    zusatz = lambda z: app.get(f"/api/rahmen/zusatz?ziel={z}").json()
    FOTO = "0123abcd-4567-89ab-cdef-0123456789ab"
    lv = app.get("/api/tv/abfrage?ziel=flur&seq=-1").json()["lv"]
    r = app.put("/api/gruss/flur", json={"text": "Hallo Oma!", "absender": "Anna", "id": FOTO, "minuten": 60}, headers=H)
    assert r.status_code == 200 and r.json()["gruss"] == {"text": "Hallo Oma!", "absender": "Anna", "id": FOTO, "herz": False}
    assert zusatz("flur")["gruss"]["text"] == "Hallo Oma!" and "gruss" not in zusatz("serbien")
    assert app.get("/api/tv/abfrage?ziel=flur&seq=-1").json()["lv"] != lv
    # Herz: einmal je Gruss, Pushover
    assert app.post("/api/gruss/flur/herz", headers=H).status_code == 200
    assert app.post("/api/gruss/flur/herz", headers=H).status_code == 200
    assert len(push) == 1 and "Anna" in push[0][1] and zusatz("flur")["gruss"]["herz"] is True
    assert app.post("/api/gruss/serbien/herz", headers=H).status_code == 404                              # dort ist kein Gruss
    # abgelaufen / entfernt / Pruefungen
    assert w.gruss_fuer("flur", datetime.datetime.now() + datetime.timedelta(minutes=61)) is None
    assert app.put("/api/gruss/flur", json={"text": ""}, headers=H).json()["gruss"] is None
    assert app.put("/api/gruss/flur", json={"text": "x", "id": "../../etc"}, headers=H).status_code == 400
    assert app.put("/api/gruss/flur", json={"text": "x", "minuten": "viel"}, headers=H).status_code == 400
    assert app.put("/api/gruss/gibtsnicht", json={"text": "x"}, headers=H).status_code == 404
    assert app.put("/api/gruss/flur", json={"text": "x"}).status_code == 403
    assert client("203.0.113.9").put("/api/gruss/flur", json={"text": "x"}, headers=H).status_code == 401
    assert ANZ.zusammen()["gruss"]["an"]


# ---------------------------------------------------------------- Gaeste-Upload per QR-Code
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def gaeste_app(app_laden, **env):
    w, client, _ = app_laden(**ZWEI, RAHMEN_IMMICH_UPLOAD_KEY="upload-key", **env)
    return w, client, client("192.168.1.50")


def test_gaeste_fest_ablauf(app_laden, monkeypatch):
    w, client, app = gaeste_app(app_laden)
    hochgeladen = []
    monkeypatch.setattr(w, "upload_zu_immich", lambda d, typ, name, ms, key=None: hochgeladen.append(name) or {"ok": True, "id": f"foto-{len(hochgeladen):04d}-aaaa-bbbb-cccc-dddddddddddd", "neu": True})
    assert not app.get("/api/gaeste/flur").json()["aktiv"] and "gaeste" not in app.get("/api/rahmen/zusatz?ziel=flur").json()
    lv = app.get("/api/tv/abfrage?ziel=flur&seq=-1").json()["lv"]
    r = app.post("/api/gaeste/flur", json={"stunden": 4}, headers=H).json()
    assert r["ok"] and r["pfad"].startswith("/gast/") and len(r["pfad"]) > 12
    kennung = r["pfad"][6:]
    assert app.get("/api/tv/abfrage?ziel=flur&seq=-1").json()["lv"] != lv                                # Rahmen zeigt den QR-Code
    z = app.get("/api/rahmen/zusatz?ziel=flur").json()["gaeste"]
    assert z["pfad"] == r["pfad"] and z["anzahl"] == 0 and "gaeste" not in app.get("/api/rahmen/zusatz?ziel=serbien").json()
    # Gast (ohne Anmeldung, von aussen) sieht die Seite, die Info und kann hochladen
    gast = client("203.0.113.77")
    assert gast.get(r["pfad"]).status_code == 200 and "Fotos" in gast.get(r["pfad"]).text
    info = gast.get(f"/api/gast/{kennung}").json()
    assert info["aktiv"] and info["rahmen"] == "Flur" and info["max_mb"] == 40
    for n in range(3):
        assert gast.put(f"/api/gast/{kennung}/hochladen", content=JPEG, headers={**H, "X-Dateiname": f"Fest%20{n}.jpg"}).status_code == 200
    assert hochgeladen == ["Gast-Fest 0.jpg", "Gast-Fest 1.jpg", "Gast-Fest 2.jpg"]
    z = app.get("/api/rahmen/zusatz?ziel=flur").json()["gaeste"]
    assert z["anzahl"] == 3 and len(z["ids"]) == 3 and z["ids"][0].startswith("foto-0001")               # der Rahmen bekommt die neuen Foto-IDs
    # Schutz: ohne Header, falsche Kennung, kein Foto
    assert gast.put(f"/api/gast/{kennung}/hochladen", content=JPEG).status_code == 403
    assert gast.put("/api/gast/falsch/hochladen", content=JPEG, headers=H).status_code == 410
    assert gast.put(f"/api/gast/{kennung}/hochladen", content=b"<html>", headers=H).status_code == 415
    assert not gast.get("/api/gast/falsch").json()["aktiv"]
    # Gaeste duerfen nichts anderes
    assert gast.post("/api/gaeste/flur", json={}, headers=H).status_code == 401 and gast.get("/api/verwaltung").status_code == 401
    # Ende
    assert app.delete("/api/gaeste/flur", headers=H).json()["ok"]
    assert gast.put(f"/api/gast/{kennung}/hochladen", content=JPEG, headers=H).status_code == 410
    assert "gaeste" not in app.get("/api/rahmen/zusatz?ziel=flur").json()


def test_gaeste_grenzen(app_laden, monkeypatch):
    w, client, app = gaeste_app(app_laden)
    monkeypatch.setattr(w, "upload_zu_immich", lambda d, typ, name, ms, key=None: {"ok": True, "id": "x" * 36, "neu": True})
    assert app.post("/api/gaeste/gibtsnicht", json={}, headers=H).status_code == 404
    assert app.post("/api/gaeste/flur", json={"stunden": "viel"}, headers=H).status_code == 400
    kennung = app.post("/api/gaeste/flur", json={}, headers=H).json()["pfad"][6:]
    neu = app.post("/api/gaeste/flur", json={}, headers=H).json()["pfad"][6:]                          # ein neues Fest ersetzt das alte desselben Rahmens
    assert neu != kennung and client("203.0.113.77").put(f"/api/gast/{kennung}/hochladen", content=JPEG, headers=H).status_code == 410
    monkeypatch.setattr(w, "GAST_PRO_IP", 2)
    g = client("203.0.113.78")
    assert [g.put(f"/api/gast/{neu}/hochladen", content=JPEG, headers=H).status_code for _ in range(3)] == [200, 200, 429]
    # Abgelaufen
    w.GAESTE[neu]["bis"] = (datetime.datetime.now() - datetime.timedelta(minutes=1)).isoformat()
    assert not client("203.0.113.79").get(f"/api/gast/{neu}").json()["aktiv"]
    assert w.gaeste_fuer("flur") == (None, None)
    # ohne Upload-Schluessel kein Fest
    w2, client2, _ = app_laden(**ZWEI)
    assert client2("192.168.1.50").post("/api/gaeste/flur", json={}, headers=H).status_code == 403
    assert ANZ.zusammen()["gaeste"]["an"]
