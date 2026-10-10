#!/usr/bin/env python3
"""Pruefungen nach dem Deploy: testet die LAUFENDE Instanz von innen (nur lesend, aendert nichts, startet keine Show auf Fernseher/Rahmen).

Aufruf im Container:   docker compose exec -T showcase python /app/postdeploy.py --version 1.2.0
Von deploy/deploy.sh nach jedem Umschalten ausgefuehrt; bei einem Fehler geht deploy.sh auf die vorherige Version zurueck.

Zugriff: von der eigenen Loopback-Adresse mit dem beim Start erzeugten Geheimnis (Datei /tmp/showcase-selbsttest). Nur Python-Standardbibliothek.
  --ohne-immich   Immich-Pruefungen ueberspringen (z. B. im Rauchtest ohne Immich)
Beendet sich mit 0 (alles gut) oder 1 (mindestens ein FEHL). WARN laesst den Deploy bestehen.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


class Pruefer:
    def __init__(self, url, token):
        self.url, self.token = url.rstrip("/"), token
        self.ergebnis = []

    def hole(self, pfad, mit_token=True, bereich=None, timeout=40):
        kopf = {"X-Selbsttest": self.token} if (mit_token and self.token) else {}
        if bereich:
            kopf["Range"] = bereich
        req = urllib.request.Request(self.url + pfad, headers=kopf)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()
        except Exception as e:  # noqa: BLE001
            return 0, {}, str(e).encode()

    def json(self, pfad, **kw):
        status, kopf, body = self.hole(pfad, **kw)
        try:
            return status, json.loads(body or b"null")
        except ValueError:
            return status, None

    def ok(self, name, detail=""):
        self.ergebnis.append(("OK", name, detail))

    def warn(self, name, detail=""):
        self.ergebnis.append(("WARN", name, detail))

    def fehl(self, name, detail=""):
        self.ergebnis.append(("FEHL", name, detail))

    def pruefe(self, name, bedingung, detail_ok="", detail_fehl=""):
        (self.ok if bedingung else self.fehl)(name, detail_ok if bedingung else detail_fehl)
        return bool(bedingung)


def pruefungen(p, version=None, mit_immich=True):
    # --- Grundzustand
    st, cfg = p.json("/api/config", mit_token=False)
    if not p.pruefe("Konfiguration erreichbar", st == 200 and isinstance(cfg, dict) and cfg.get("name"), f"{cfg.get('name')} {cfg.get('version')}" if cfg else "", f"HTTP {st}"):
        return                                                      # ohne Konfiguration ist alles Weitere sinnlos
    if version:
        p.pruefe("laufende Version stimmt", cfg.get("version") == version, version, f"erwartet {version}, laeuft {cfg.get('version')}")
    st, v = p.json("/api/version", mit_token=False)
    p.pruefe("Versionsstand", st == 200 and isinstance(v, dict) and v.get("v"), "", f"HTTP {st}")
    st, me = p.json("/api/me", mit_token=False)
    p.pruefe("Anmeldestatus", st == 200 and isinstance(me, dict) and "angemeldet" in me and me.get("auth") in ("pin", "immich", "beide"), f"Anmeldung: {me.get('auth')}" if me else "", f"HTTP {st}")

    # --- Oberflaeche und Dateien
    for pfad, merkmal in (("/", b"Frameside"), ("/tv/", b"Frameside"), ("/i18n.js", b"RW_LANG"), ("/sw.js", b"fetch"), ("/manifest.webmanifest", b"icons")):
        st, _, body = p.hole(pfad, mit_token=False)
        p.pruefe(f"Datei {pfad}", st == 200 and merkmal in body, "", f"HTTP {st}")
    st, en = p.json("/i18n/en.json", mit_token=False)
    p.pruefe("Uebersetzung en.json", st == 200 and isinstance(en, dict) and len(en.get("texte", {})) > 50, f"{len((en or {}).get('texte', {}))} Texte", f"HTTP {st}")
    st, _, body = p.hole("/icon-192.png", mit_token=False)
    p.pruefe("Symbol", st == 200 and body[:4] == b"\x89PNG", "", f"HTTP {st}")

    # --- Sicherheit: App-Daten ohne Anmeldung gesperrt
    st, _, _ = p.hole("/api/neueste", mit_token=False)
    if st == 401:
        p.ok("App-Daten ohne Anmeldung gesperrt")
    else:
        p.warn("App-Daten ohne Anmeldung erreichbar", f"HTTP {st} (liegt die Loopback-Adresse im vertrauten Netz?)")
    if not p.token:
        p.warn("kein Selbsttest-Geheimnis", "Pruefungen mit Zugriff werden uebersprungen")
        return

    # --- Dienste (mit Zugriff)
    st, status = p.json("/api/status")
    p.pruefe("Rahmen-Status", st == 200 and isinstance(status, dict) and status.get("ok") is True, "", f"HTTP {st}")
    st, ziele = p.json("/api/tv/ziele")
    p.pruefe("Fernseher-Liste", st == 200 and isinstance(ziele, dict) and isinstance(ziele.get("ziele"), list), f"{len((ziele or {}).get('ziele', []))} Ziele", f"HTTP {st}")
    if cfg.get("rahmen"):
        st, rs = p.json("/api/rahmen/status")
        p.pruefe("Rahmen-Player-Status", st == 200 and isinstance(rs, dict) and len(rs.get("rahmen", [])) == len(cfg["rahmen"]), "", f"HTTP {st}")

    # --- Musik (nur wenn eingerichtet)
    musik = [m for m in (ziele or {}).get("musik", []) if m.get("id") != "alle"]
    if musik:
        st, liste = p.json("/api/tv/musikliste?k=" + musik[0]["id"])
        stuecke = (liste or {}).get("stuecke", [])
        if p.pruefe("Musikliste", st == 200 and stuecke, f"{len(musik)} Sammlung(en)", f"HTTP {st}"):
            st, _, body = p.hole(f"/api/tv/musikdatei/{musik[0]['id']}/{stuecke[0]['datei']}", bereich="bytes=0-199")
            p.pruefe("Musikdatei abspielbar", st in (200, 206) and len(body) > 50, "", f"HTTP {st}")
    else:
        p.ok("Musik", "keine eingerichtet (optional)")

    # --- Immich
    if not mit_immich:
        return
    st, fac = p.json("/api/facetten?typ=foto")
    if p.pruefe("Immich: Filter und Zaehler", st == 200 and isinstance(fac, dict) and "gesamt" in fac, f"{fac.get('gesamt')} Fotos sichtbar" if fac else "", f"HTTP {st} (Immich erreichbar? Schluessel gueltig?)"):
        if fac["gesamt"] == 0:
            p.warn("Immich: keine Fotos sichtbar", "Schluessel gehoert zu einem Konto ohne Fotos?")
    st, neu = p.json("/api/neueste?limit=10")
    fotos = (neu or {}).get("fotos", []) if isinstance(neu, dict) else []
    p.pruefe("Immich: neueste Fotos", st == 200 and isinstance(neu, dict) and "fotos" in neu, f"{len(fotos)} geladen", f"HTTP {st}")
    if fotos:
        st, kopf, body = p.hole(f"/api/vorschau/{fotos[0]['id']}?s=gross")
        p.pruefe("Immich: Vorschaubild", st == 200 and len(body) > 500 and str(kopf.get("Content-Type", "")).startswith("image/"), f"{len(body) // 1024} KB", f"HTTP {st}")
    st, such = p.json("/api/suche?text=2020")
    p.pruefe("Suche (Zeitraum)", st == 200 and isinstance(such, dict) and "fotos" in such, such.get("nachricht", "") if such else "", f"HTTP {st}")
    if cfg.get("rahmen") and fotos:
        st, zu = p.json("/api/rahmen/zufall?n=5")
        p.pruefe("Rahmen: Dauerprogramm liefert Fotos", st == 200 and isinstance(zu, dict) and len(zu.get("ids", [])) > 0, f"{len((zu or {}).get('ids', []))} Fotos", f"HTTP {st}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pruefungen nach dem Deploy")
    ap.add_argument("--url", default=os.environ.get("SHOWCASE_TEST_URL", "http://127.0.0.1:8090"))
    ap.add_argument("--version", default=None, help="erwartete Version")
    ap.add_argument("--ohne-immich", action="store_true")
    ap.add_argument("--token-datei", default=os.environ.get("SHOWCASE_SELBSTTEST_FILE", "/tmp/showcase-selbsttest"))
    arg = ap.parse_args(argv)
    try:
        token = open(arg.token_datei).read().strip()
    except OSError:
        token = ""
    p = Pruefer(arg.url, token)
    pruefungen(p, arg.version, not arg.ohne_immich)
    for stufe, name, detail in p.ergebnis:
        print(f"{stufe:<4} {name}" + (f" – {detail}" if detail else ""))
    fehler = sum(1 for e in p.ergebnis if e[0] == "FEHL")
    warn = sum(1 for e in p.ergebnis if e[0] == "WARN")
    print(f"\
{len(p.ergebnis)} Pruefungen: {len(p.ergebnis) - fehler - warn} ok, {warn} Warnung(en), {fehler} Fehler")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
