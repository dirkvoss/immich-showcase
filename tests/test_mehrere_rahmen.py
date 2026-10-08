"""Mehrere Rahmen: Senden an gewaehlte Rahmen, getrennter Zustand, 'Zurueck' und Reihenfolge je Rahmen."""
import conftest

H = {"X-Rahmen": "1"}
LAN = {"RAHMEN_WEB_LAN": "192.168.1.0/24", "RAHMEN_WEB_RAHMEN_ZIELE": "flur=Flur,kueche=Kueche", "RAHMEN_WEB_RAHMEN_SEK": "5"}


def ids(a, b):
    return [x["id"] for x in conftest.ASSETS[a:b]]


def test_standard_ist_der_erste_rahmen(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    assert c.post("/api/anzeigen", json={"name": "Urlaub", "ids": ids(0, 4)}, headers=H).json()["ziele"] == ["flur"]
    assert c.get("/api/status").json()["laeuft"] == "Urlaub"
    assert c.get("/api/status?ziel=kueche").json()["laeuft"] is None


def test_eine_show_an_mehrere_rahmen(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    r = c.post("/api/anzeigen", json={"name": "Urlaub", "ids": ids(0, 4), "ziele": ["flur", "kueche"]}, headers=H).json()
    assert r["ziele"] == ["flur", "kueche"] and "Flur, Kueche" in r["nachricht"]
    assert c.get("/api/status?ziel=flur").json()["laeuft"] == "Urlaub"
    assert c.get("/api/status?ziel=kueche").json()["laeuft"] == "Urlaub"
    assert [s["name"] for s in c.get("/api/shows").json()["shows"]] == ["Urlaub"]
    assert c.get("/api/shows").json()["shows"][0]["laeuft_auf"] == ["flur", "kueche"]


def test_verschiedene_shows_auf_verschiedenen_rahmen(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    c.post("/api/anzeigen", json={"name": "Urlaub", "ids": ids(0, 4), "ziele": ["flur"]}, headers=H)
    c.post("/api/anzeigen", json={"name": "Weihnachten", "ids": ids(4, 9), "ziele": ["kueche"]}, headers=H)
    assert c.get("/api/status?ziel=flur").json()["laeuft"] == "Urlaub"
    assert c.get("/api/status?ziel=kueche").json()["laeuft"] == "Weihnachten"
    ev_flur = c.get("/api/tv/abfrage?ziel=flur&seq=-1").json()["events"][0]
    ev_kueche = c.get("/api/tv/abfrage?ziel=kueche&seq=-1").json()["events"][0]
    assert len(ev_flur["ids"]) == 4 and len(ev_kueche["ids"]) == 5


def test_normal_und_zurueck_je_rahmen(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    c.post("/api/anzeigen", json={"name": "A", "ids": ids(0, 3), "ziele": ["flur", "kueche"]}, headers=H)
    c.post("/api/anzeigen", json={"name": "B", "ids": ids(3, 6), "ziele": ["kueche"]}, headers=H)
    assert c.get("/api/status?ziel=kueche").json()["zurueck"] == "A"
    assert c.get("/api/status?ziel=flur").json()["zurueck"] == "Normales Programm"
    c.post("/api/normal", json={"ziel": "flur"}, headers=H)
    assert c.get("/api/status?ziel=flur").json()["laeuft"] is None
    assert c.get("/api/status?ziel=kueche").json()["laeuft"] == "B"
    c.post("/api/zurueck", json={"ziel": "kueche"}, headers=H)
    assert c.get("/api/status?ziel=kueche").json()["laeuft"] == "A"


def test_reihenfolge_je_rahmen(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    c.post("/api/reihenfolge", json={"reihenfolge": "zufall", "ziel": "kueche"}, headers=H)
    assert c.get("/api/status?ziel=kueche").json()["reihenfolge"] == "zufall"
    assert c.get("/api/status?ziel=flur").json()["reihenfolge"] == "alt"


def test_unbekannter_rahmen_wird_abgelehnt(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    assert c.post("/api/anzeigen", json={"name": "A", "ids": ids(0, 3), "ziele": ["gibtsnicht"]}, headers=H).status_code == 400
    assert c.get("/api/status?ziel=gibtsnicht").status_code == 400
    assert c.post("/api/normal", json={"ziel": "gibtsnicht"}, headers=H).status_code == 400


def test_status_listet_alle_rahmen_und_config_nennt_namen(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    assert [x["id"] for x in c.get("/api/status").json()["rahmen"]] == ["flur", "kueche"]
    assert c.get("/api/config").json()["rahmen_namen"] == {"flur": "Flur", "kueche": "Kueche"}


def test_gespeicherte_show_an_gewaehlten_rahmen(app_laden):
    w, client, _ = app_laden(**LAN)
    c = client()
    sid = c.post("/api/anzeigen", json={"name": "A", "ids": ids(0, 3), "speichern": True}, headers=H).json()["show"]
    c.post("/api/normal", json={}, headers=H)
    assert c.post(f"/api/shows/{sid}/anzeigen", json={"ziele": ["kueche"]}, headers=H).json()["ziele"] == ["kueche"]
    assert c.get("/api/status?ziel=kueche").json()["laeuft"] == "A" and c.get("/api/status?ziel=flur").json()["laeuft"] is None
