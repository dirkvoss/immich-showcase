"""Weitere Suchsprachen (es, fr, nl): Grundfaelle wie bei de/en."""
import datetime as dt

import pytest

import rahmen_helfer as H

PERSONEN = [("Anna Muster", "p1"), ("Opa Karl", "p2")]
ORTE = {H.norm(n): (t, n) for t, n in [("country", "Italy"), ("country", "Spain"), ("state", "Sardinia"), ("city", "Munich"), ("country", "Netherlands")]}


@pytest.fixture(autouse=True)
def feste_zeit(monkeypatch):
    class FD(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 10, 3)
    monkeypatch.setattr(H.dt, "datetime", FD)


def p(text, lang, alias=None):
    return H.parse(text, PERSONEN, alias or {}, ORTE, lang)


def fenster(e):
    return [(a.date().isoformat(), b.date().isoformat()) for a, b in e["zeit"]]


@pytest.mark.parametrize("text,lang,erwartung", [
    ("verano 2022", "es", {"zeit": ("2022-06-01", "2022-09-01")}),
    ("fotos de Italia en julio 2021", "es", {"ort": "Italy", "zeit": ("2021-07-01", "2021-08-01")}),
    ("playa en Cerdeña", "es", {"ort": "Sardinia", "motiv": "playa"}),
    ("Navidad 2019", "es", {"zeit": ("2019-12-20", "2019-12-28")}),
    ("este año", "es", {"zeit": ("2026-01-01", "2027-01-01")}),
    ("el año pasado", "es", {"zeit": ("2025-01-01", "2026-01-01")}),
    ("été 2022", "fr", {"zeit": ("2022-06-01", "2022-09-01")}),
    ("photos d'Italie en juillet 2021", "fr", {"ort": "Italy", "zeit": ("2021-07-01", "2021-08-01")}),
    ("plage en Sardaigne", "fr", {"ort": "Sardinia", "motiv": "plage"}),
    ("Noël 2019", "fr", {"zeit": ("2019-12-20", "2019-12-28")}),
    ("cette année", "fr", {"zeit": ("2026-01-01", "2027-01-01")}),
    ("zomer 2022", "nl", {"zeit": ("2022-06-01", "2022-09-01")}),
    ("foto's uit Italië in juli 2021", "nl", {"ort": "Italy", "zeit": ("2021-07-01", "2021-08-01")}),
    ("strand op Sardinië", "nl", {"ort": "Sardinia", "motiv": "strand"}),
    ("kerst 2019", "nl", {"zeit": ("2019-12-20", "2019-12-28")}),
    ("dit jaar", "nl", {"zeit": ("2026-01-01", "2027-01-01")}),
    ("vorig jaar", "nl", {"zeit": ("2025-01-01", "2026-01-01")}),
])
def test_erkennung(text, lang, erwartung):
    e = p(text, lang)
    if "zeit" in erwartung:
        assert fenster(e)[0] == erwartung["zeit"], fenster(e)
    if "ort" in erwartung:
        assert e["ort"] and e["ort"][1] == erwartung["ort"], e["ort"]
    if "motiv" in erwartung:
        assert e["motiv"] == erwartung["motiv"], e["motiv"]


def test_personen_in_jeder_sprache():
    for lang, text in (("es", "fotos de Anna en 2020"), ("fr", "photos de Anna en 2020"), ("nl", "foto's van Anna in 2020")):
        e = p(text, lang)
        assert [n for n, _ in e["personen"]] == ["Anna Muster"] and fenster(e)[0] == ("2020-01-01", "2021-01-01"), (lang, e)


def test_letzte_wochen():
    assert fenster(p("las últimas 3 semanas", "es"))[0] == ("2026-09-12", "2026-10-04")
    assert fenster(p("les 3 dernières semaines", "fr"))[0] == ("2026-09-12", "2026-10-04")
    assert fenster(p("de laatste 3 weken", "nl"))[0] == ("2026-09-12", "2026-10-04")
