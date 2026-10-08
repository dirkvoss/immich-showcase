"""Dauerprogramm des Rahmens: Quellen mit Gewicht, keine Wiederholer, Ueberwachung."""
import datetime

import conftest

A, B = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa", "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
LAN = {"RAHMEN_WEB_LAN": "192.168.1.0/24", "RAHMEN_WEB_RAHMEN_ZIELE": "rahmen=Rahmen"}


def test_verteilen_summe_und_verhaeltnis(app_laden):
    w, _, _ = app_laden()
    assert w.verteilen([3, 1], 40) == [30, 10]
    assert sum(w.verteilen([1, 1, 1], 40)) == 40
    assert w.verteilen([70, 20, 10], 10) == [7, 2, 1]
    assert w.verteilen([1], 7) == [7]


def test_quellen_lesen(app_laden):
    w, _, _ = app_laden(RAHMEN_WEB_RAHMEN_QUELLEN=f"{A}:70, neu14:20, *:10, kaputt:5, {B}:0")
    q = w.rahmen_quellen()
    assert [(x["typ"], x["gewicht"]) for x in q] == [("album", 70.0), ("neu", 20.0), ("alle", 10.0)]       # Gewicht 0 und Unsinn fallen weg
    assert q[1]["tage"] == 14


def test_standard_ist_ganze_bibliothek_oder_alben(app_laden):
    w, _, _ = app_laden()
    assert [x["typ"] for x in w.rahmen_quellen()] == ["alle"]
    w, _, _ = app_laden(RAHMEN_WEB_RAHMEN_ALBEN=A)
    assert [x["typ"] for x in w.rahmen_quellen()] == ["alben"]


def test_auswahl_folgt_dem_gewicht(app_laden):
    w, client, schrein = app_laden(RAHMEN_WEB_RAHMEN_QUELLEN=f"{A}:3,{B}:1", **LAN)
    ids = w.rahmen_auswahl(12)
    aus_a = [i for i in ids if i in conftest.ALBEN[A]]
    aus_b = [i for i in ids if i in conftest.ALBEN[B]]
    assert (len(aus_a), len(aus_b)) == (9, 3)


def test_neue_fotos_quelle_setzt_zeitfenster(app_laden):
    w, client, schrein = app_laden(RAHMEN_WEB_RAHMEN_QUELLEN="neu7:1", **LAN)
    w.rahmen_auswahl(5)
    body = [b for p, b in schrein.bodies if p == "/search/random"][0]
    assert body["createdAfter"].endswith(".000Z") and body["type"] == "IMAGE"


def test_keine_wiederholer_innerhalb_des_gedaechtnisses(app_laden):
    w, client, schrein = app_laden(**LAN)
    erste = set(w.rahmen_auswahl(10))
    zweite = set(w.rahmen_auswahl(10))
    assert not erste & zweite


def test_leere_quelle_faellt_zurueck_statt_leer_zu_bleiben(app_laden):
    w, client, schrein = app_laden(RAHMEN_WEB_RAHMEN_QUELLEN="*:1", **LAN)
    w.rahmen_auswahl(28)
    wieder = w.rahmen_auswahl(10)                       # alles schon gezeigt: lieber Wiederholer als nichts
    assert len(wieder) == 10


def test_kaputte_quelle_legt_programm_nicht_lahm(app_laden, monkeypatch):
    w, client, schrein = app_laden(RAHMEN_WEB_RAHMEN_QUELLEN=f"{A}:1,*:1", **LAN)
    echt = w.H.api

    def api(method, path, body=None, timeout=120):
        if body and body.get("albumIds"):
            raise OSError("Album geloescht")
        return echt(method, path, body, timeout)
    monkeypatch.setattr(w.H, "api", api)
    assert len(w.rahmen_auswahl(10)) == 10              # die intakte Quelle springt ein; kein Fehler


def test_endpunkt_liefert_ids(app_laden):
    w, client, _ = app_laden(**LAN)
    assert 0 < len(client().get("/api/rahmen/zufall?n=10").json()["ids"]) <= 10


def test_status_und_abfrage_melden_zustand(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    assert c.get("/api/rahmen/status").json()["rahmen"][0]["online"] is False
    c.get("/api/tv/abfrage?ziel=rahmen&seq=-1&a=1&ra=7&s=0")
    s = c.get("/api/rahmen/status").json()["rahmen"][0]
    assert s["online"] and s["dauerprogramm"] is True and s["bild_alter_s"] == 7 and s["spielt"] is None


def test_wache_meldet_ausfall_einmal_und_rueckkehr(app_laden, monkeypatch):
    w, client, _ = app_laden(RAHMEN_WEB_RAHMEN_ALARM_MIN="10", **LAN)
    gesendet = []
    monkeypatch.setattr(w, "pushover", lambda titel, text, prio=0: gesendet.append(titel))
    t0 = w.WACHE["start"]
    assert w.rahmen_wache_pruefen(t0 + 5 * 60) == []                                  # noch unter der Schwelle
    assert len(w.rahmen_wache_pruefen(t0 + 11 * 60)) == 1                             # Ausfall gemeldet
    assert w.rahmen_wache_pruefen(t0 + 30 * 60) == []                                 # nicht erneut
    w.TV["rahmen"]["hb"] = t0 + 40 * 60                                               # Rahmen meldet sich wieder
    assert [m[0] for m in w.rahmen_wache_pruefen(t0 + 40 * 60 + 5)] == ["Rahmen wieder da"]
    assert gesendet == ["Rahmen nicht erreichbar", "Rahmen wieder da"]


def test_wache_erkennt_haengendes_bild(app_laden, monkeypatch):
    w, client, _ = app_laden(RAHMEN_WEB_RAHMEN_ALARM_MIN="5", **LAN)
    monkeypatch.setattr(w, "pushover", lambda *a, **k: None)
    t0 = w.WACHE["start"]
    w.TV["rahmen"].update(hb=t0 + 100, ambient=True, bild_alter=3000)                 # 50 Minuten dasselbe Bild, aber erreichbar
    m = w.rahmen_wache_pruefen(t0 + 105)
    assert len(m) == 1 and "dasselbe Bild" in m[0][0]


def test_wache_aus_bei_alarm_0(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_RAHMEN_ALARM_MIN="0", **LAN)
    assert w.RAHMEN_ALARM_MIN == 0


def test_kleine_quelle_wird_aus_anderen_aufgefuellt(app_laden, monkeypatch):
    w, client, schrein = app_laden(RAHMEN_WEB_RAHMEN_QUELLEN=f"{A}:1,*:1", **LAN)
    conftest.ALBEN[A] = conftest.ALBEN[A][:2]                    # winziges Album
    try:
        assert len(w.rahmen_auswahl(20)) == 20
    finally:
        conftest.ALBEN[A] = [a["id"] for a in conftest.ASSETS[:14]]


def test_anzeigeoptionen_in_der_konfiguration(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_RAHMEN_FUELLUNG="zuschnitt", RAHMEN_WEB_TV_FUELLUNG="unscharf", RAHMEN_WEB_RAHMEN_ANZEIGE="datum, ort, quatsch",
                             RAHMEN_WEB_RAHMEN_NACHT="22:00-06:30", **LAN)
    d = client().get("/api/config").json()
    assert (d["rahmen_fuellung"], d["tv_fuellung"], d["rahmen_anzeige"], d["rahmen_nacht"]) == ("zuschnitt", "unscharf", ["datum", "ort"], "22:00-06:30")


def test_anzeigeoptionen_vorgaben_und_ungueltige_werte(app_laden):
    w, client, _ = app_laden(RAHMEN_WEB_RAHMEN_FUELLUNG="blau", RAHMEN_WEB_RAHMEN_NACHT="spaet", **LAN)
    d = client().get("/api/config").json()
    assert (d["rahmen_fuellung"], d["tv_fuellung"], d["rahmen_anzeige"], d["rahmen_nacht"]) == ("unscharf", "balken", [], "")


def test_bildinfo_datum_und_ort(app_laden):
    import conftest
    w, client, schrein = app_laden(**LAN)
    c = client()
    a = next(x for x in conftest.ASSETS if x["exifInfo"]["country"] == "Italy")
    a["exifInfo"]["city"] = "Rom"
    d = c.get(f"/api/bildinfo/{a['id']}?lang=de").json()
    assert d["datum"] == a["localDateTime"][:10] and d["ort"] == "Rom, Italien"
    assert c.get(f"/api/bildinfo/{a['id']}?lang=en").json()["ort"] == "Rom, Italy"
    assert c.get("/api/bildinfo/kein-id").status_code == 400
    a["exifInfo"].pop("city")


def test_marker_alben_kommen_dazu_und_nur_rahmen_ist_exklusiv(app_laden):
    w, client, schrein = app_laden(RAHMEN_WEB_RAHMEN_ALBEN=A, RAHMEN_WEB_RAHMEN_MARKER="1", **LAN)
    schrein.albumliste = [{"id": A, "description": "", "assetCount": 14}, {"id": B, "description": "zeig das auf dem #Bilderrahmen", "assetCount": 14}]
    assert w.rahmen_alben() == ([A, B], False)
    w.MARKER_CACHE["t"] = 0
    schrein.albumliste[1]["description"] = "Sardinien #nurrahmen"
    assert w.rahmen_alben() == ([B], True)
    ids = w.rahmen_auswahl(5)
    assert ids and all(i in conftest.ALBEN[B] for i in ids)


def test_marker_leeres_album_und_ohne_marker_zaehlen_nicht(app_laden):
    w, client, schrein = app_laden(RAHMEN_WEB_RAHMEN_ALBEN=A, RAHMEN_WEB_RAHMEN_MARKER="1", **LAN)
    schrein.albumliste = [{"id": B, "description": "#rahmen", "assetCount": 0}, {"id": "cccccccc-3333-4333-8333-cccccccccccc", "description": "Urlaub", "assetCount": 9}]
    assert w.rahmen_alben() == ([A], False)


def test_ohne_marker_schalter_bleibt_alles_beim_alten(app_laden):
    w, client, schrein = app_laden(RAHMEN_WEB_RAHMEN_ALBEN=A, **LAN)
    schrein.albumliste = [{"id": B, "description": "#nurrahmen", "assetCount": 5}]
    assert w.rahmen_alben() == ([A], False)


def test_marker_funktionieren_auch_englisch(app_laden):
    w, client, schrein = app_laden(RAHMEN_WEB_RAHMEN_ALBEN=A, RAHMEN_WEB_RAHMEN_MARKER="1", **LAN)
    schrein.albumliste = [{"id": B, "description": "show on the #picture-frame", "assetCount": 3}]
    assert w.rahmen_alben() == ([A, B], False)
    w.MARKER_CACHE["t"] = 0
    schrein.albumliste[0]["description"] = "#onlyframe"
    assert w.rahmen_alben() == ([B], True)


# ---------------------------------------------------------------- Zeitplan, Quellen je Rahmen, "heute"

def test_zeitplan_lesen_und_wochentage(app_laden):
    w, _, _ = app_laden()
    regeln = w.zeitplan_lesen("Mo-Fr 18:00-22:00 = *; Sa,So 08:00-20:00 = neu7:1, x; kaputt; Mo 25:00 = *")
    assert len(regeln) == 2 and regeln[0][0] == {0, 1, 2, 3, 4} and regeln[1][0] == {5, 6}
    assert regeln[0][1:3] == (18 * 60, 22 * 60) and regeln[1][3] == ["neu7:1", "x"]
    assert w.zeitplan_lesen("taeglich 06:00-07:00 = *")[0][0] == set(range(7))
    assert w.zeitplan_lesen("Fr-Mo 06:00-07:00 = *")[0][0] == {4, 5, 6, 0}


def test_zeitplan_waehlt_nach_zeit_und_ueber_mitternacht(app_laden):
    w, _, _ = app_laden()
    dt = datetime.datetime
    regeln = w.zeitplan_lesen("Mo-Fr 18:00-22:00 = A; Fr 22:00-02:00 = N")
    assert w.zeitplan_quellen(regeln, dt(2026, 10, 5, 19, 0)) == ["A"]        # Montag 19 Uhr
    assert w.zeitplan_quellen(regeln, dt(2026, 10, 5, 23, 0)) is None         # Montag 23 Uhr: nichts
    assert w.zeitplan_quellen(regeln, dt(2026, 10, 9, 23, 30)) == ["N"]       # Freitag 23:30
    assert w.zeitplan_quellen(regeln, dt(2026, 10, 10, 1, 0)) == ["N"]        # Samstag 01:00 gehoert noch zu Freitag
    assert w.zeitplan_quellen(regeln, dt(2026, 10, 10, 3, 0)) is None


def test_zeitplan_ersetzt_die_quellen_nur_im_zeitfenster(app_laden):
    w, _, _ = app_laden(RAHMEN_WEB_RAHMEN_QUELLEN=f"{A}:1", RAHMEN_WEB_RAHMEN_ZEITPLAN=f"Mo-Fr 18:00-22:00 = {B}:1")
    dt = datetime.datetime
    assert w.rahmen_quellen(None, dt(2026, 10, 5, 19, 0))[0]["id"] == B
    assert w.rahmen_quellen(None, dt(2026, 10, 5, 12, 0))[0]["id"] == A


def test_quellen_je_rahmen(app_laden):
    w, _, _ = app_laden(RAHMEN_WEB_RAHMEN_ZIELE="flur=Flur,kueche=Kueche", RAHMEN_WEB_RAHMEN_QUELLEN=f"{A}:1", RAHMEN_WEB_RAHMEN_QUELLEN_KUECHE=f"{B}:1")
    assert w.rahmen_quellen("flur")[0]["id"] == A
    assert w.rahmen_quellen("kueche")[0]["id"] == B
    assert w.rahmen_quellen(None)[0]["id"] == A


def test_heute_quelle_findet_fotos_dieses_tages(app_laden):
    w, client, schrein = app_laden(RAHMEN_WEB_RAHMEN_QUELLEN="heute:1", **LAN)
    a = conftest.ASSETS[0]
    tag = datetime.date.fromisoformat(a["localDateTime"][:10])
    ids = w.heute_ids(0, heute=datetime.date(2030, tag.month, tag.day))
    assert a["id"] in ids
    assert w.rahmen_quellen()[0]["typ"] == "heute"


def test_zufall_nimmt_den_rahmen_aus_der_anfrage(app_laden):
    w, client, schrein = app_laden(**{**LAN, "RAHMEN_WEB_RAHMEN_ZIELE": "flur=Flur,kueche=Kueche", "RAHMEN_WEB_RAHMEN_QUELLEN_FLUR": f"{A}:1", "RAHMEN_WEB_RAHMEN_QUELLEN_KUECHE": f"{B}:1"})
    c = client()
    flur = c.get("/api/rahmen/zufall?n=10&ziel=flur").json()["ids"]
    kueche = c.get("/api/rahmen/zufall?n=10&ziel=kueche").json()["ids"]
    assert flur and all(i in conftest.ALBEN[A] for i in flur)
    assert kueche and all(i in conftest.ALBEN[B] for i in kueche)


def test_mehrere_alben_sind_oder_nicht_und(app_laden):
    """Immich verknuepft mehrere albumIds mit UND; das Dauerprogramm muss Fotos aus JEDEM der Alben mischen."""
    w, client, schrein = app_laden(RAHMEN_WEB_RAHMEN_ALBEN=f"{A},{B}", **LAN)
    ids = set(client().get("/api/rahmen/zufall?n=40").json()["ids"])
    assert ids and ids & set(conftest.ALBEN[A]) and ids & set(conftest.ALBEN[B])
    assert ids <= set(conftest.ALBEN[A]) | set(conftest.ALBEN[B])


def test_mehrere_alben_exklusiv(app_laden, monkeypatch):
    w, client, schrein = app_laden(RAHMEN_WEB_RAHMEN_MARKER="1", **LAN)
    monkeypatch.setattr(w, "marker_alben", lambda: ([], [A, B]))
    ids = client().get("/api/rahmen/zufall?n=30").json()["ids"]
    assert ids and set(ids) & set(conftest.ALBEN[A]) and set(ids) & set(conftest.ALBEN[B])
