"""Einblendungen am Rahmen: Uhrzeit, Datum, Foto-Datum, Foto-Ort, Wetter, Termine - jedes einzeln ein-/ausschaltbar, frei positionierbar und skalierbar.

Ein Element hat: an (sichtbar), farbe (#rrggbb, leer = Standard), schrift (serif/sans/mono, leer = Standard), x/y (0-100, Prozent der Flaeche; 0/0 = oben links, 100/100 = unten rechts, das Element liegt dabei immer
innerhalb des Bildschirms), gr (Groesse in Prozent) bei "fotodatum" zeit (Aufnahmezeit zusaetzlich zeigen) und format (lang/kurz) und bei "termine" person (Kuerzel der Person davor).
Die Werte setzen sich schichtweise zusammen: Standard <- alte Einstellung "anzeige" (allgemein, dann am Geraet) <- allgemeines Layout <- Layout des Geraets.
"""
import re

ELEMENTE = ("uhr", "heute", "fotodatum", "fotoort", "wetter", "termine", "geburtstag", "titel")
STANDARD = {
    "uhr": {"an": True, "x": 0, "y": 100, "gr": 100, "farbe": "", "schrift": ""},
    "heute": {"an": False, "x": 0, "y": 90, "gr": 100, "farbe": "", "schrift": ""},
    "fotodatum": {"an": False, "x": 100, "y": 100, "gr": 100, "farbe": "", "schrift": "", "zeit": False, "format": "lang"},
    "fotoort": {"an": False, "x": 100, "y": 92, "gr": 100, "farbe": "", "schrift": ""},
    "wetter": {"an": True, "x": 100, "y": 0, "gr": 100, "farbe": "", "schrift": ""},
    "termine": {"an": True, "x": 100, "y": 14, "gr": 100, "farbe": "", "schrift": "", "person": True},
    "geburtstag": {"an": True, "x": 50, "y": 0, "gr": 100, "farbe": "", "schrift": ""},
    "titel": {"an": True, "x": 0, "y": 88, "gr": 100, "farbe": "", "schrift": ""},      # Name der Show, kurz beim Start einer Show
}
GR_MIN, GR_MAX = 40, 300
SCHRIFTEN = ("", "serif", "sans", "mono")                 # "" = Standard des Elements
NUR_BEI = {"zeit": "fotodatum", "person": "termine", "format": "fotodatum"}      # Felder, die nur bestimmte Elemente haben
DATUMSFORMATE = ("lang", "kurz")                          # lang: 4. Dezember 2025, kurz: 04.12.2025


def aus_anzeige(anzeige):
    """Die frueheren Haken 'Bildunterschrift: Datum / Uhrzeit / Ort' als Layout-Schicht."""
    a = [x for x in (anzeige or []) if x in ("datum", "zeit", "ort")]
    if not a:
        return {}
    schicht = {}
    if "datum" in a or "zeit" in a:
        schicht["fotodatum"] = {"an": True, "zeit": "zeit" in a}
    if "ort" in a:
        schicht["fotoort"] = {"an": True}
    return schicht


def pruefen(daten):
    """Prueft vom Nutzer gesendetes Layout; Rueckgabe: bereinigtes Layout (nur bekannte Elemente und Felder). Fehler: ValueError mit deutschem Text."""
    if not isinstance(daten, dict):
        raise ValueError("Das Layout muss eine Liste von Elementen sein.")
    aus = {}
    for name, w in daten.items():
        if name not in ELEMENTE:
            raise ValueError("Unbekanntes Anzeige-Element: " + str(name)[:30])
        if not isinstance(w, dict):
            raise ValueError("Ungültige Angaben zum Element " + name)
        e = {}
        for feld in ("an", "zeit", "person"):
            if feld in w:
                if NUR_BEI.get(feld, name) != name:
                    continue
                if not isinstance(w[feld], bool):
                    raise ValueError(f"{name}: {feld} muss ein/aus sein")
                e[feld] = w[feld]
        if "farbe" in w:
            if not isinstance(w["farbe"], str) or not re.fullmatch(r"|#[0-9a-fA-F]{6}", w["farbe"]):
                raise ValueError(f"{name}: Farbe bitte als #rrggbb angeben")
            e["farbe"] = w["farbe"].lower()
        if "format" in w and NUR_BEI["format"] == name:
            if w["format"] not in DATUMSFORMATE:
                raise ValueError(f"{name}: unbekanntes Datumsformat")
            e["format"] = w["format"]
        if "schrift" in w:
            if w["schrift"] not in SCHRIFTEN:
                raise ValueError(f"{name}: unbekannte Schrift")
            e["schrift"] = w["schrift"]
        for feld in ("x", "y"):
            if feld in w:
                try:
                    v = float(w[feld])
                except (TypeError, ValueError):
                    raise ValueError(f"{name}: Position ungültig")
                if not 0 <= v <= 100:
                    raise ValueError(f"{name}: Position muss zwischen 0 und 100 liegen")
                e[feld] = round(v, 1)
        if "gr" in w:
            try:
                v = int(w["gr"])
            except (TypeError, ValueError):
                raise ValueError(f"{name}: Größe ungültig")
            if not GR_MIN <= v <= GR_MAX:
                raise ValueError(f"{name}: Größe muss zwischen {GR_MIN} und {GR_MAX} Prozent liegen")
            e["gr"] = v
        if e:
            aus[name] = e
    return aus


def zusammen(*schichten):
    """Legt Schichten uebereinander (spaetere gewinnen, feldweise); Rueckgabe: vollstaendiges Layout fuer alle Elemente."""
    ergebnis = {n: dict(STANDARD[n]) for n in ELEMENTE}
    for s in schichten:
        for name, w in (s or {}).items():
            if name in ergebnis and isinstance(w, dict):
                for feld, wert in w.items():
                    if feld in ergebnis[name]:
                        ergebnis[name][feld] = wert
    return ergebnis
