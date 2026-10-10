"""Termine aus den Kalendern der Handys (iPhone-App) fuer die Terminanzeige am Rahmen.

Jedes Handy ("Quelle") schickt die Termine der naechsten Tage; der Server speichert sie je Quelle und zeigt am Rahmen die naechsten Termine
des heutigen Tages (ist heute nichts mehr, die von morgen). Es gibt keine Konten, nur eine zufaellige Kennung je Handy.
"""
import datetime
import re

QUELLE_RE = re.compile(r"[A-Za-z0-9-]{8,64}")
MAX_QUELLEN = 20
MAX_TERMINE = 400
STANDARD_DAUER = datetime.timedelta(hours=1)
BEHALTEN = datetime.timedelta(days=60)


def _zeit(text):
    """'YYYY-MM-DD' oder 'YYYY-MM-DDTHH:MM[:SS]' (Ortszeit, ohne Zeitzone) -> (datetime, ganztag)."""
    t = str(text or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        return datetime.datetime.fromisoformat(t), True
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?", t):
        return datetime.datetime.fromisoformat(t), False
    raise ValueError("Zeitangabe ungültig")


def termine_pruefen(termine):
    """Bereinigt die gesendete Terminliste; ungueltige Eintraege werden verworfen (kein Abbruch), zu viele abgelehnt."""
    if not isinstance(termine, list):
        raise ValueError("Die Terminliste fehlt.")
    if len(termine) > MAX_TERMINE:
        raise ValueError(f"Zu viele Termine (höchstens {MAX_TERMINE}).")
    aus = []
    for t in termine:
        try:
            von, ganztag = _zeit(t.get("von"))
            bis = None
            if t.get("bis"):
                bis, _g = _zeit(t.get("bis"))
            titel = " ".join(str(t.get("titel") or "").split())[:120] or "Termin"
        except (AttributeError, ValueError, TypeError):
            continue
        e = {"titel": titel, "von": t["von"].strip()[:19], "ganztag": ganztag}
        if t.get("geburtstag") is True:
            e["geburtstag"] = True
        if bis and bis >= von:
            e["bis"] = str(t["bis"]).strip()[:19]
        aus.append(e)
    return aus


FARBE_RE = re.compile(r"#[0-9a-fA-F]{6}")


def quelle_setzen(daten, quelle, name, termine, jetzt, kuerzel="", farbe=""):
    """Ersetzt die Termine einer Quelle. Rueckgabe: neuer Stand (das uebergebene Woerterbuch wird nicht veraendert)."""
    if not QUELLE_RE.fullmatch(str(quelle or "")):
        raise ValueError("Ungültige Kennung des Handys.")
    neu = {k: v for k, v in daten.items() if _frisch(v, jetzt)}
    if quelle not in neu and len(neu) >= MAX_QUELLEN:
        raise ValueError(f"Es sind höchstens {MAX_QUELLEN} Handys möglich. Entferne ein altes in den Einstellungen.")
    neu[quelle] = {"name": " ".join(str(name or "").split())[:40] or "Handy", "aktualisiert": jetzt.isoformat(timespec="seconds"), "termine": termine_pruefen(termine)}
    k = "".join(str(kuerzel or "").split())[:2]
    if k:
        neu[quelle]["kuerzel"] = k
    if FARBE_RE.fullmatch(str(farbe or "")):
        neu[quelle]["farbe"] = str(farbe).lower()
    return neu


def _frisch(eintrag, jetzt):
    try:
        return jetzt - datetime.datetime.fromisoformat(eintrag.get("aktualisiert")) < BEHALTEN
    except (AttributeError, TypeError, ValueError):
        return False


def ereignisse(daten, heute):
    """Alle Termine von heute und morgen aus allen Quellen im Format der Terminanzeige: tag ('heute'/'morgen'), zeit ('HH:MM' oder ''), ende ('HH:MM' oder ''), titel."""
    morgen = heute + datetime.timedelta(days=1)
    aus = []
    for _q, e in sorted((daten or {}).items()):
        for t in e.get("termine", []):
            try:
                von, ganztag = _zeit(t.get("von"))
                bis = _zeit(t["bis"])[0] if t.get("bis") else None
            except (AttributeError, KeyError, ValueError, TypeError):
                continue
            ende_tag = (bis or von).date()
            if ganztag and bis and bis > von:                      # Ganztags-Termine enden in Kalendern am Folgetag um 0 Uhr (exklusiv)
                ende_tag = (bis - datetime.timedelta(days=1)).date()
            for tag, name in ((heute, "heute"), (morgen, "morgen")):
                if not von.date() <= tag <= ende_tag:
                    continue
                beginnt_heute = von.date() == tag
                zeit = "" if ganztag or not beginnt_heute else von.strftime("%H:%M")
                ende = "" if ganztag or bis is None or bis.date() != tag else bis.strftime("%H:%M")
                eintrag = {"tag": name, "zeit": zeit, "ende": ende, "titel": t["titel"]}
                if t.get("geburtstag"):
                    eintrag["geburtstag"] = True
                if e.get("kuerzel"):
                    eintrag["p"] = {"k": e["kuerzel"], "f": e.get("farbe") or ""}
                aus.append(eintrag)
    return aus


def geburtstage(liste):
    """Geburtstage von heute (aus dem Geburtstags-Kalender des Handys), ohne Doppelte."""
    namen = []
    for e in liste:
        if e.get("geburtstag") and e.get("tag") == "heute" and e["titel"] not in namen:
            namen.append(e["titel"])
    return namen


def naechste(liste, jetzt, maximum=4, personen=True):
    """Die naechsten Termine des heutigen Tages (laufende und kommende, ganztaegige zuerst); ist heute nichts mehr, die von morgen.
    liste: Eintraege mit tag, zeit, titel und optional ende. Ohne Endzeit gilt ein Termin eine Stunde lang."""
    jetzt_min = jetzt.hour * 60 + jetzt.minute

    def minuten(t):
        return int(t[:2]) * 60 + int(t[3:5])

    def sortiert(eintraege):
        return sorted(eintraege, key=lambda e: (e["zeit"] or "", e["titel"]))

    liste = [e for e in liste if not e.get("geburtstag")]            # Geburtstage haben ihr eigenes Element
    heute = []
    for e in liste:
        if e.get("tag") != "heute":
            continue
        if e.get("zeit"):
            ende = minuten(e["ende"]) if e.get("ende") else minuten(e["zeit"]) + int(STANDARD_DAUER.total_seconds() // 60)
            if ende <= jetzt_min:
                continue
        heute.append(e)
    wahl = sortiert(heute)
    if not wahl:
        wahl = sortiert([e for e in liste if e.get("tag") == "morgen"])
    aus = []
    for e in wahl[:maximum]:
        z = {"tag": e["tag"], "zeit": e["zeit"], "titel": e["titel"]}
        if personen and e.get("p"):
            z["p"] = e["p"]
        aus.append(z)
    return aus
