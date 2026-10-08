import json
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN = json.load(open(os.path.join(RAIZ, "static", "i18n", "en.json")))


def test_muster_sind_gueltige_regex():
    for muster, ersatz, *_ in EN["muster"]:
        re.compile(muster)
        assert isinstance(ersatz, str)


def test_keine_leeren_uebersetzungen():
    assert all(k.strip() and v.strip() for k, v in EN["texte"].items())


def test_beispielsaetze():
    texte = EN["texte"]
    assert texte["Neueste"] == "Latest"
    assert texte["Suchen"] == "Search"
    treffer = {m[0]: m for m in EN["muster"]}
    m = re.compile(r"^(\d+) Fotos ausgewählt ›$")
    assert m.sub(r"\1 photos selected ›", "3 Fotos ausgewählt ›") == "3 photos selected ›"
    assert r"^(\d+) Fotos ausgewählt ›$" in treffer


def test_statische_dateien_vorhanden():
    for f in ("index.html", "tv/index.html", "i18n.js", "sw.js", "manifest.webmanifest", "icon-192.png", "icon-512.png", "fonts/cormorant-600.woff2"):
        assert os.path.exists(os.path.join(RAIZ, "static", f)), f


def test_oberflaeche_enthaelt_keine_privaten_daten():
    verboten = ("dirk-voss", "mail@dirk")      # persoenliche Daten des Autors; allgemeine Beispiel-Adressen sind erlaubt
    for wurzel, _, dateien in os.walk(RAIZ):
        if {".git", "tests", "build"} & set(wurzel.split(os.sep)) or wurzel.endswith(".xcodeproj"):
            continue
        for d in dateien:
            if d.endswith((".png", ".woff2", ".pyc")) or d in ("LICENSE", "OFL.txt"):
                continue
            inhalt = open(os.path.join(wurzel, d), errors="ignore").read().replace("com.dirk-voss", "")      # Bundle-ID der iPhone-App (ios/) ist bewusst oeffentlich
            for v in verboten:
                assert v not in inhalt or d in ("conftest.py",), f"{v} in {d}"


def test_alle_sprachdateien_sind_konsistent():
    """Jede Sprache hat dieselben Schluessel und Muster wie en.json (Quelle der Wahrheit) und kompilierbare Regex."""
    import glob
    en = EN
    dateien = sorted(glob.glob(os.path.join(RAIZ, "static", "i18n", "*.json")))
    assert {os.path.basename(d)[:-5] for d in dateien} >= {"en", "es", "fr", "nl"}
    for d in dateien:
        D = json.load(open(d))
        name = os.path.basename(d)
        assert set(D["texte"]) == set(en["texte"]), f"{name}: Texte weichen von en.json ab"
        assert [m[0] for m in D["muster"]] == [m[0] for m in en["muster"]], f"{name}: Muster weichen von en.json ab"
        assert len(D["beschreibung"]) == len(en["beschreibung"]), name
        for m in D["muster"]:
            re.compile(m[0])
        assert all(v.strip() for v in D["texte"].values()), name


def test_sprachen_in_i18n_js_und_parser():
    import rahmen_helfer
    js = open(os.path.join(RAIZ, "static", "i18n.js")).read()
    for lang in ("en", "es", "fr", "nl"):
        assert f"{lang}:" in js
        assert lang in rahmen_helfer.SPRACHEN, f"Suchsprache {lang} fehlt"
