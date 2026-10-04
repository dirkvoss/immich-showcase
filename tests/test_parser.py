"""Suchsprache: Deutsch darf sich nie unbemerkt aendern, Englisch muss gleichwertig verstehen."""
import datetime as dt

import pytest

import rahmen_helfer as H

PERSONEN = [("Anna Muster", "p1"), ("Oma Erika", "p2"), ("Bjoern Beispiel", "p3"), ("Anna Schmidt", "p4"), ("Anna Meier", "p5")]
ALIAS = {"oma": "Oma Erika", "grandma": "Oma Erika"}
ORTE = {H.norm(n): (t, n) for t, n in [("country", "Italy"), ("country", "Germany"), ("state", "Sardinia"), ("city", "Munich")]}


@pytest.fixture(autouse=True)
def feste_zeit(monkeypatch):
    class FD(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 10, 3)
    monkeypatch.setattr(H.dt, "datetime", FD)


def p(text, lang="de"):
    return H.parse(text, PERSONEN, ALIAS, ORTE, lang)


def fenster(e):
    return [(a.date().isoformat(), b.date().isoformat()) for a, b in e["zeit"]]


@pytest.mark.parametrize("text,lang,kern", [
    ("Oma 2019", "de", {"personen": ["Oma Erika"], "zeit": [("2019-01-01", "2020-01-01")]}),
    ("Grandma 2019", "en", {"personen": ["Oma Erika"], "zeit": [("2019-01-01", "2020-01-01")]}),
    ("Sardinien am Strand", "de", {"ort": "Sardinia", "motiv": "Strand"}),
    ("Sardinia beach", "en", {"ort": "Sardinia", "motiv": "beach"}),
    ("Sommer 2022", "de", {"zeit": [("2022-06-01", "2022-09-01")]}),
    ("summer 2022", "en", {"zeit": [("2022-06-01", "2022-09-01")]}),
    ("Fotos aus Italien im Juli 2021", "de", {"ort": "Italy", "zeit": [("2021-07-01", "2021-08-01")]}),
    ("Photos from Italy in July 2021", "en", {"ort": "Italy", "zeit": [("2021-07-01", "2021-08-01")]}),
    ("dieses Jahr", "de", {"zeit": [("2026-01-01", "2027-01-01")]}),
    ("this year", "en", {"zeit": [("2026-01-01", "2027-01-01")]}),
    ("last year", "en", {"zeit": [("2025-01-01", "2026-01-01")]}),
    ("Hund im Garten 2018 bis 2020", "de", {"motiv": "Hund im Garten", "zeit": [("2018-01-01", "2021-01-01")]}),
    ("dog in the garden 2018 to 2020", "en", {"motiv": "dog in the garden", "zeit": [("2018-01-01", "2021-01-01")]}),
    ("Favoriten", "de", {"favoriten": True}),
    ("best photos", "en", {"favoriten": True}),
    ("Tanja Silvester 2019", "de", {"zeit": [("2019-12-31", "2020-01-01")]}),
    ("New Year's Eve 2019", "en", {"zeit": [("2019-12-31", "2020-01-01")]}),
])
def test_erkennung(text, lang, kern):
    e = p(text, lang)
    if "personen" in kern:
        assert [n for n, _ in e["personen"]] == kern["personen"]
    if "zeit" in kern:
        assert fenster(e)[: len(kern["zeit"])] == kern["zeit"]
    if "ort" in kern:
        assert e["ort"][1] == kern["ort"]
    if "motiv" in kern:
        assert e["motiv"] == kern["motiv"]
    if "favoriten" in kern:
        assert e["favoriten"] is True


def test_mehrdeutiger_vorname_fragt_nach():
    assert p("Anna Kuchen")["rueckfrage"]
    assert p("Anna cake", "en")["rueckfrage"]


def test_letzte_wochen():
    assert fenster(p("die letzten 3 Wochen"))[0] == ("2026-09-12", "2026-10-04")
    assert fenster(p("the last 3 weeks", "en"))[0] == ("2026-09-12", "2026-10-04")


def test_unbekannte_sprache_faellt_auf_deutsch_zurueck():
    assert p("Oma 2019", "xx")["personen"][0][0] == "Oma Erika"
