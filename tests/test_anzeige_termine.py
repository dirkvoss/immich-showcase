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
    assert r.status_code == 200 and r.json()["einstellungen"]["layout"]["uhr"]["x"] == 100
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
    assert lv() != c


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
