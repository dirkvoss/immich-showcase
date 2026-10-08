#!/usr/bin/env python3
"""Rahmen-Web: Weboberflaeche + Schnittstelle fuer den Bilderrahmen (angelegt 2026-10-03).

Wer die PIN kennt (oder im vertrauten Netz ist) sucht Fotos oder blaettert durch die neuesten, waehlt aus, gibt der
Show einen Namen und schickt sie auf den Bilderrahmen. Die Such- und Rahmenlogik kommt unveraendert aus
rahmen_helfer.py (gleicher Immich-Schluessel OHNE Loeschrecht). Geloescht werden hier nie Fotos.

Zugang: im vertrauten Netz (RAHMEN_WEB_LAN) ohne PIN, von aussen mit 6-stelliger PIN. Das Geraet wird 90 Tage
gemerkt (signierter Cookie). 5 Fehlversuche je IP -> 15 Minuten Sperre, viele Fehlversuche -> Pushover.
"""

import base64
import collections
import contextvars
import datetime
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import random
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid

EINSTELLUNGEN_FILE = os.environ.get("RAHMEN_WEB_EINSTELLUNGEN", "/data/einstellungen.json")


def _einstellungen_anwenden():
    """Einstellungen aus dem Einrichtungsassistenten (Datei) gelten, soweit die Umgebung (.env) sie nicht selbst setzt."""
    try:
        d = json.load(open(EINSTELLUNGEN_FILE))
    except (OSError, ValueError):
        return
    for k, v in d.items():
        if k.startswith("RAHMEN_") and not os.environ.get(k):
            os.environ[k] = str(v)


_einstellungen_anwenden()
sys.path.insert(0, os.environ.get("RAHMEN_HELFER_DIR", "/opt/bilderrahmen"))
import rahmen_helfer as H  # noqa: E402

from fastapi import Depends, FastAPI, HTTPException, Request, Response  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

PIN_FILE = os.environ.get("RAHMEN_WEB_PIN_FILE", "/root/.rahmen_web_pin")
SECRET_FILE = os.environ.get("RAHMEN_WEB_SECRET_FILE", "/root/.rahmen_web_secret")
AUTH_STATE = os.environ.get("RAHMEN_WEB_AUTH_STATE", "/var/lib/bilderrahmen/rahmen_web_auth.json")
SHOWS_FILE = os.environ.get("RAHMEN_WEB_SHOWS_FILE", "/var/lib/bilderrahmen/rahmen_web_shows.json")
PUSHOVER_FILE = os.environ.get("RAHMEN_WEB_PUSHOVER_FILE", "/root/.pushover_credentials")
STATIC_DIR = os.environ.get("RAHMEN_WEB_STATIC", os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"))
def _liste(name, default=""):
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


# Alles Installationsspezifische kommt aus Umgebungsvariablen (siehe .env.example); die Vorgaben sind bewusst sicher:
# ohne Angabe gibt es kein "vertrautes Netz" und keinen vertrauten Proxy - dann braucht jeder die PIN.
APP_NAME = os.environ.get("RAHMEN_WEB_NAME", "Immich Showcase")
VERSION = os.environ.get("SHOWCASE_VERSION", "dev")                       # beim Bauen des Images gesetzt
# Wofuer die Installation gedacht ist: rahmen (nur Bilderrahmen), tv (nur Fernseher) oder beides. Steuert, welche Knoepfe die App zeigt.
# Anmeldung: pin (gemeinsame PIN, Vorgabe), immich (Immich-Konto: E-Mail + Passwort, jeder sieht nur seine Fotos) oder beide
AUTH = os.environ.get("RAHMEN_WEB_AUTH", "pin").strip().lower()
if AUTH not in ("pin", "immich", "beide"):
    AUTH = "pin"
BENUTZER_FILE = os.environ.get("RAHMEN_WEB_BENUTZER_FILE", "/var/lib/bilderrahmen/rahmen_web_benutzer.json")
UID_CTX = contextvars.ContextVar("rahmen_uid", default=None)
KEY_NAME = "Immich Showcase"
KEY_RECHTE = ["asset.read", "asset.view", "asset.statistics", "timeline.read", "person.read", "album.create", "album.read", "album.update",
              "album.delete", "albumAsset.create", "albumAsset.delete", "map.read", "user.read"]       # keine Foto-Loeschrechte; user.read = eigenes Profil (Name)
MODUS = os.environ.get("RAHMEN_WEB_MODUS", "beides").strip().lower()
if MODUS not in ("rahmen", "tv", "beides"):
    MODUS = "beides"
TV_URL = os.environ.get("RAHMEN_WEB_TV_URL", "").strip().rstrip("/")            # z. B. tv.example.com (nur fuer Hinweistexte)
BEISPIELE = [b.strip() for b in os.environ.get("RAHMEN_WEB_BEISPIELE", "Sommer 2022; Geburtstag; Strand").split(";") if b.strip()]
BEISPIELE_EN = [b.strip() for b in os.environ.get("RAHMEN_WEB_BEISPIELE_EN", "Summer 2022; Birthday; Beach").split(";") if b.strip()]
# Bilderrahmen-Ziele: wie Fernseher, zeigen im Leerlauf aber selbst ein Dauerprogramm (Zufallsfotos). RAHMEN_WEB_RAHMEN_ZIELE="rahmen=Bilderrahmen"
RAHMEN_ZIELE = {k.strip(): v.strip() for k, _, v in (z.partition("=") for z in _liste("RAHMEN_WEB_RAHMEN_ZIELE")) if k.strip() and v.strip()}
RAHMEN_ALBEN = [a for a in _liste("RAHMEN_WEB_RAHMEN_ALBEN") if re.match(r"^[0-9a-f-]{36}$", a)]    # leer = ganze Bibliothek
# Marker-Alben: Alben, deren Beschreibung "#...rahmen..." enthaelt, kommen zum Dauerprogramm dazu; "#...nurrahmen..." zeigt NUR diese (exklusiv)
RAHMEN_MARKER = os.environ.get("RAHMEN_WEB_RAHMEN_MARKER", "").strip().lower() in ("1", "ja", "true", "an", "yes")
MARKER_RE = re.compile(r"#\S*(?:rahmen|frame)\S*", re.IGNORECASE)
MARKER_NUR_RE = re.compile(r"#\S*(?:nur|only)\S*(?:rahmen|frame)\S*", re.IGNORECASE)
RAHMEN_SEK = max(3, min(int(os.environ.get("RAHMEN_WEB_RAHMEN_SEK", "8")), 120))
# Quellen des Dauerprogramms mit Gewicht: "<album-id>:70, neu14:20, *:10"  (*=ganze Bibliothek, neuN=in den letzten N Tagen hochgeladen).
# Ohne Angabe: RAHMEN_WEB_RAHMEN_ALBEN gemeinsam bzw. die ganze Bibliothek.
RAHMEN_QUELLEN_ROH = _liste("RAHMEN_WEB_RAHMEN_QUELLEN")
# Anzeige am Rahmen: Fuellung (balken = schwarze Raender | unscharf = unscharfe Fortsetzung des Fotos | zuschnitt = Foto fuellt den Schirm),
# Zusatzangaben (datum, ort) und Nachtruhe "22:00-06:30" (dann bleibt der Schirm im Dauerprogramm schwarz)
def _wahl(name, erlaubt, default):
    w = os.environ.get(name, default).strip().lower()
    return w if w in erlaubt else default


RAHMEN_FUELLUNG = _wahl("RAHMEN_WEB_RAHMEN_FUELLUNG", ("balken", "unscharf", "zuschnitt"), "unscharf")
TV_FUELLUNG = _wahl("RAHMEN_WEB_TV_FUELLUNG", ("balken", "unscharf", "zuschnitt"), "balken")
RAHMEN_ANZEIGE = [x for x in _liste("RAHMEN_WEB_RAHMEN_ANZEIGE") if x in ("datum", "zeit", "ort")]
RAHMEN_NACHT = os.environ.get("RAHMEN_WEB_RAHMEN_NACHT", "").strip() if re.fullmatch(r"\d{1,2}:\d{2}-\d{1,2}:\d{2}", os.environ.get("RAHMEN_WEB_RAHMEN_NACHT", "").strip()) else ""
# Meldung (Pushover), wenn ein Rahmen laenger als so viele Minuten nicht erreichbar ist bzw. dasselbe Bild zeigt (0 = aus)
RAHMEN_ALARM_MIN = max(0, int(os.environ.get("RAHMEN_WEB_RAHMEN_ALARM_MIN", "15")))
LAN_NETS = [ipaddress.ip_network(n) for n in _liste("RAHMEN_WEB_LAN")]
# Nur von diesen Reverse-Proxys wird X-Real-IP geglaubt; sonst zaehlt die Verbindungs-IP. Achtung: kommt Internetverkehr ueber einen
# Tunnel/Proxy mit interner Adresse an, darf diese Adresse NICHT in RAHMEN_WEB_LAN stehen (sonst waere das Internet "vertrautes Netz").
TRUSTED_PROXIES = set(_liste("RAHMEN_WEB_PROXIES"))
LAND_DE = {"Austria": "Österreich", "Belgium": "Belgien", "Bosnia and Herzegovina": "Bosnien und Herzegowina",
           "Croatia": "Kroatien", "Denmark": "Dänemark", "France": "Frankreich", "Germany": "Deutschland",
           "India": "Indien", "Italy": "Italien", "Kenya": "Kenia", "Netherlands": "Niederlande", "Poland": "Polen",
           "Qatar": "Katar", "Romania": "Rumänien", "Serbia": "Serbien", "Slovenia": "Slowenien", "Sweden": "Schweden",
           "Switzerland": "Schweiz", "United Republic of Tanzania": "Tansania", "United States of America": "USA",
           "Spain": "Spanien", "Greece": "Griechenland", "Turkey": "Türkei", "Portugal": "Portugal",
           "Czechia": "Tschechien", "Hungary": "Ungarn", "Norway": "Norwegen", "Finland": "Finnland",
           "United Kingdom": "Vereinigtes Königreich", "Ireland": "Irland", "Egypt": "Ägypten", "Morocco": "Marokko"}
COOKIE = "rw_session"
COOKIE_TAGE = 90
FEHLVERSUCHE = 5
SPERRE_SEK = 15 * 60
GLOBAL_ALARM = 20          # Fehlversuche pro Stunde (alle IPs) -> Pushover
MAX_IDS = 1000
ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

AUTH_LOCK = threading.Lock()
CACHE = {}

app = FastAPI(title="Rahmen-Web", docs_url=None, redoc_url=None, openapi_url=None)


# --------------------------------------------------------------------------- Hilfen

def lies_json(pfad, default):
    try:
        return json.load(open(pfad))
    except (OSError, ValueError):
        return default


def schreibe_json(pfad, daten):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    tmp = pfad + ".tmp"
    json.dump(daten, open(tmp, "w"), indent=1, ensure_ascii=False)
    os.chmod(tmp, 0o600)
    os.replace(tmp, pfad)


def thread_mit_kontext(ziel, *args):
    """Startet einen Hintergrund-Thread, der die angemeldete Person (Immich-Schluessel) mitbekommt."""
    ctx = contextvars.copy_context()
    t = threading.Thread(target=ctx.run, args=(ziel, *args), daemon=True)
    t.start()
    return t


def zwischenspeicher(schluessel, sekunden, holen):
    schluessel = (UID_CTX.get(), schluessel)             # jede angemeldete Person hat eigene Listen/Zaehler
    eintrag = CACHE.get(schluessel)
    if eintrag and time.time() - eintrag[0] < sekunden:
        return eintrag[1]
    wert = holen()
    CACHE[schluessel] = (time.time(), wert)
    return wert


def pushover_senden(titel, text, prio=0):
    """Schickt eine Pushover-Nachricht; wirft bei Fehlern. Zugang: App-Einstellungen, sonst Umgebung, sonst Datei."""
    pe = EINST.get("pushover") if "EINST" in globals() else None
    if isinstance(pe, dict) and pe.get("user") and pe.get("token"):
        cred = {"PUSHOVER_API_KEY": pe["token"], "PUSHOVER_USER_KEY": pe["user"], "PUSHOVER_DEVICE": pe.get("device", "")}
    elif os.environ.get("RAHMEN_WEB_PUSHOVER_API_KEY") and os.environ.get("RAHMEN_WEB_PUSHOVER_USER_KEY"):      # bequem ueber die Umgebung
        cred = {"PUSHOVER_API_KEY": os.environ["RAHMEN_WEB_PUSHOVER_API_KEY"], "PUSHOVER_USER_KEY": os.environ["RAHMEN_WEB_PUSHOVER_USER_KEY"],
                "PUSHOVER_DEVICE": os.environ.get("RAHMEN_WEB_PUSHOVER_DEVICE", "")}
    else:
        cred = dict(z.strip().split("=", 1) for z in open(PUSHOVER_FILE) if "=" in z and not z.startswith("#"))
    daten = {"token": cred["PUSHOVER_API_KEY"].strip('"'), "user": cred["PUSHOVER_USER_KEY"].strip('"'),
             "title": titel, "message": text, "priority": prio}
    if cred.get("PUSHOVER_DEVICE"):
        daten["device"] = cred["PUSHOVER_DEVICE"].strip('"')
    urllib.request.urlopen("https://api.pushover.net/1/messages.json", urllib.parse.urlencode(daten).encode(), timeout=10).read()


def pushover(titel, text, prio=0):
    try:
        pushover_senden(titel, text, prio)
    except Exception as e:  # noqa: BLE001 - Alarm darf nie den Login stoeren
        H.log.warning("Pushover fehlgeschlagen: %s", e)


# --------------------------------------------------------------------------- PIN / Sitzung

def pin_hash(pin, salz=None):
    salz = salz or secrets.token_bytes(16)
    h = hashlib.scrypt(pin.encode(), salt=salz, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salz.hex()}${h.hex()}"


def pin_pruefen(pin):
    try:
        _, salz, h = open(PIN_FILE).read().strip().split("$")
    except (OSError, ValueError):
        return False
    return hmac.compare_digest(pin_hash(pin, bytes.fromhex(salz)).split("$")[2], h)


def pin_version():
    try:
        return hashlib.sha256(open(PIN_FILE, "rb").read()).hexdigest()[:8]
    except OSError:
        return "none"


def geheimnis():
    if not os.path.exists(SECRET_FILE):
        os.makedirs(os.path.dirname(SECRET_FILE), exist_ok=True)
        fd = os.open(SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, secrets.token_hex(32).encode())
        os.close(fd)
    return open(SECRET_FILE).read().strip().encode()


def benutzer_lesen():
    return lies_json(BENUTZER_FILE, {})


def sitzung_ausstellen(uid=None):
    """Signierter Cookie. PIN-Sitzung: bindet an die PIN-Version; Immich-Sitzung: 'u<Benutzer-ID>' (gilt nur, solange der Benutzer bekannt ist)."""
    nutzlast = f"{int(time.time()) + COOKIE_TAGE * 86400}.{('u' + uid) if uid else pin_version()}"
    sig = hmac.new(geheimnis(), nutzlast.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{nutzlast}.{sig}".encode()).decode()


def sitzung_lesen(wert):
    """None oder {'typ': 'pin'} oder {'typ': 'immich', 'uid', 'name'}."""
    try:
        exp, ver, sig = base64.urlsafe_b64decode(wert.encode()).decode().split(".")
    except (ValueError, UnicodeError):
        return None
    soll = hmac.new(geheimnis(), f"{exp}.{ver}".encode(), hashlib.sha256).hexdigest()
    if not (hmac.compare_digest(sig, soll) and int(exp) > time.time()):
        return None
    if ver.startswith("u"):
        b = benutzer_lesen().get(ver[1:])
        if AUTH == "pin" or not b:
            return None
        return {"typ": "immich", "uid": ver[1:], "name": b.get("name", "")}
    if AUTH == "immich" or ver != pin_version():
        return None
    return {"typ": "pin"}


def sitzung_gueltig(wert):
    return sitzung_lesen(wert) is not None


def client_ip(request):
    peer = request.client.host if request.client else "0.0.0.0"
    if peer in TRUSTED_PROXIES:
        return (request.headers.get("x-real-ip") or peer).strip()
    return peer


def ist_lan(ip):
    try:
        return any(ipaddress.ip_address(ip) in netz for netz in LAN_NETS)
    except ValueError:
        return False


SELBSTTEST_FILE = os.environ.get("SHOWCASE_SELBSTTEST_FILE", "/tmp/showcase-selbsttest")


def selbsttest_ok(request: Request):
    """Pruefungen nach dem Deploy (postdeploy.py, per docker exec im Container): lesender Zugriff NUR von der eigenen Loopback-Adresse UND mit dem
    beim Start erzeugten Geheimnis aus einer nur im Container lesbaren Datei. Von aussen (auch ueber einen Proxy im selben Netz) nicht erreichbar."""
    if request.method not in ("GET", "HEAD") or not request.client or request.client.host not in ("127.0.0.1", "::1"):
        return False
    gesendet = request.headers.get("x-selbsttest", "")
    try:
        soll = open(SELBSTTEST_FILE).read().strip()
    except OSError:
        return False
    return bool(soll) and hmac.compare_digest(gesendet, soll)


@app.on_event("startup")
def selbsttest_geheimnis():
    try:
        fd = os.open(SELBSTTEST_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.write(fd, secrets.token_hex(24).encode())
        os.close(fd)
    except OSError as e:
        H.log.warning("Selbsttest-Geheimnis nicht schreibbar: %s", e)


def anmeldung(request: Request):
    """App-Zugriff. PIN-Betrieb: vertrautes Netz oder PIN-Sitzung. Immich-Betrieb: nur Sitzung (das vertraute Netz gilt dort nur fuer Geraete)."""
    ip = client_ip(request)
    wert = request.cookies.get(COOKIE)
    sitzung = sitzung_lesen(wert) if wert else None
    if sitzung:
        return {"lan": False, "ip": ip, **sitzung}
    if AUTH == "pin" and ist_lan(ip):
        return {"lan": True, "ip": ip}
    if selbsttest_ok(request):
        return {"lan": False, "ip": ip, "typ": "selbsttest"}
    raise HTTPException(401, "Anmeldung erforderlich" if AUTH != "pin" else "PIN erforderlich")


def geraet(request: Request):
    """Fernseher/Rahmen-Seiten (kein Login moeglich): vertrautes Netz oder Sitzung."""
    ip = client_ip(request)
    wert = request.cookies.get(COOKIE)
    sitzung = sitzung_lesen(wert) if wert else None
    if sitzung:
        return {"lan": False, "ip": ip, **sitzung}
    if ist_lan(ip) or selbsttest_ok(request):
        return {"lan": True, "ip": ip}
    raise HTTPException(401, "Anmeldung erforderlich" if AUTH != "pin" else "PIN erforderlich")


@app.middleware("http")
async def person_zuordnen(request: Request, call_next):
    """Setzt vor jedem Aufruf den Immich-Schluessel der angemeldeten Person (sonst gilt der Dienstschluessel)."""
    wert = request.cookies.get(COOKIE)
    sitzung = sitzung_lesen(wert) if wert and AUTH != "pin" else None
    if sitzung and sitzung["typ"] == "immich":
        b = benutzer_lesen().get(sitzung["uid"]) or {}
        UID_CTX.set(sitzung["uid"])
        H.KEY_CTX.set(b.get("key"))
    return await call_next(request)


def csrf(request: Request):
    """Schreibende Aufrufe nur mit eigenem Header (Browser-Formulare anderer Seiten koennen ihn nicht setzen)."""
    if request.headers.get("x-rahmen") != "1":
        raise HTTPException(403, "Anfrage nicht zugelassen")


# --------------------------------------------------------------------------- Immich-Zugriff

def immich_roh(pfad, timeout=60, schluessel=None):
    req = urllib.request.Request(H.IMMICH + pfad, headers={"x-api-key": schluessel or H.schluessel()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "application/octet-stream")


def dauer_sek(a):
    """Dauer eines Videos in Sekunden (Immich liefert Millisekunden oder 'h:mm:ss.fff')."""
    d = a.get("duration")
    try:
        if isinstance(d, str) and ":" in d:
            h, m, sek = d.split(":")
            return int(float(h) * 3600 + float(m) * 60 + float(sek))
        return int(round(float(d) / 1000))
    except (TypeError, ValueError):
        return 0


def foto_dict(a):
    tag = (a.get("localDateTime") or a.get("fileCreatedAt") or "")[:10]
    r = {"id": a["id"], "tag": tag, "fav": bool(a.get("isFavorite"))}
    if a.get("type") == "VIDEO":
        r.update(v=1, dauer=dauer_sek(a))
    return r


def personen_karte():
    named, alias = zwischenspeicher("personen", 300, H.lade_personen)
    return {H.norm(n): (n, pid) for n, pid in named}


def orte_karte():
    return zwischenspeicher("orte", 3600, H.lade_orte)


# --------------------------------------------------------------------------- Anmeldung

@app.post("/api/login")
def login(request: Request, response: Response, daten: dict, _=Depends(csrf)):
    if AUTH != "pin" and daten.get("schluessel"):
        return login_schluessel(request, response, daten)
    if AUTH != "pin" and "email" in daten:
        return login_immich(request, response, daten)
    if AUTH == "immich":
        raise HTTPException(400, "Bitte mit dem Immich-Konto anmelden")
    ip = client_ip(request)
    pin = str(daten.get("pin", ""))
    jetzt = time.time()
    with AUTH_LOCK:
        st = lies_json(AUTH_STATE, {"fehl": {}, "global": [], "alarm": 0})
        fehl = [t for t in st["fehl"].get(ip, []) if jetzt - t < SPERRE_SEK]
        if len(fehl) >= FEHLVERSUCHE:
            rest = int(SPERRE_SEK - (jetzt - fehl[0]))
            raise HTTPException(429, f"Zu viele Versuche. Bitte in {max(rest // 60, 1)} Minuten erneut versuchen.")
        if re.fullmatch(r"\d{6}", pin) and pin_pruefen(pin):
            st["fehl"].pop(ip, None)
            schreibe_json(AUTH_STATE, st)
            response.set_cookie(COOKIE, sitzung_ausstellen(), max_age=COOKIE_TAGE * 86400, httponly=True,
                                samesite="strict", secure=request.headers.get("x-forwarded-proto") == "https")
            H.log.info("Login ok von %s", ip)
            return {"ok": True}
        fehl.append(jetzt)
        st["fehl"][ip] = fehl
        st["global"] = [t for t in st.get("global", []) if jetzt - t < 3600] + [jetzt]
        alarm = len(st["global"]) >= GLOBAL_ALARM and jetzt - st.get("alarm", 0) > 3600
        if alarm:
            st["alarm"] = jetzt
        schreibe_json(AUTH_STATE, st)
    H.log.warning("Falsche PIN von %s (%d/%d)", ip, len(fehl), FEHLVERSUCHE)
    if alarm:
        pushover("Rahmen-Web: viele falsche PINs", f"{len(st['global'])} Fehlversuche in der letzten Stunde, zuletzt von {ip}", 1)
    time.sleep(1)  # bremst automatisierte Versuche zusaetzlich
    raise HTTPException(401, "PIN falsch")


def immich_aufruf(methode, pfad, daten=None, token=None, schluessel=None, basis=None):
    req = urllib.request.Request((basis or H.IMMICH) + pfad, method=methode, data=json.dumps(daten).encode() if daten is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {}),
                                          **({"x-api-key": schluessel} if schluessel else {})})
    raw = urllib.request.urlopen(req, timeout=30).read()
    return json.loads(raw) if raw else None


def login_schluessel(request: Request, response: Response, daten: dict):
    """Anmeldung mit einem selbst in Immich angelegten API-Schluessel (fuer Konten ohne Passwort, z. B. bei Anmeldung ueber OIDC/SSO)."""
    ip = client_ip(request)
    schluessel = str(daten.get("schluessel", "")).strip()[:300]
    jetzt = time.time()
    with AUTH_LOCK:
        st = lies_json(AUTH_STATE, {"fehl": {}, "global": [], "alarm": 0})
        fehl = [t for t in st["fehl"].get(ip, []) if jetzt - t < SPERRE_SEK]
        if len(fehl) >= FEHLVERSUCHE:
            raise HTTPException(429, "Zu viele Versuche. Bitte spaeter erneut versuchen.")
    try:
        ich = immich_aufruf("GET", "/users/me", schluessel=schluessel)
        uid = ich["id"]
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise HTTPException(400, "Dem Schluessel fehlt das Recht user.read (eigenes Profil lesen)")
        ich = None
    except (OSError, KeyError, ValueError):
        raise HTTPException(502, "Immich ist gerade nicht erreichbar")
    if not ich:
        with AUTH_LOCK:
            st = lies_json(AUTH_STATE, {"fehl": {}, "global": [], "alarm": 0})
            st["fehl"][ip] = [t for t in st["fehl"].get(ip, []) if jetzt - t < SPERRE_SEK] + [jetzt]
            schreibe_json(AUTH_STATE, st)
        time.sleep(1)
        raise HTTPException(401, "Der Schluessel wird von Immich nicht akzeptiert")
    with AUTH_LOCK:
        alle = benutzer_lesen()
        alle[uid] = {"name": ich.get("name") or ich.get("email", ""), "email": ich.get("email", ""), "key": schluessel, "zuletzt": jetzt}
        schreibe_json(BENUTZER_FILE, alle)
    response.set_cookie(COOKIE, sitzung_ausstellen(uid), max_age=COOKIE_TAGE * 86400, httponly=True,
                        samesite="strict", secure=request.headers.get("x-forwarded-proto") == "https")
    H.log.info("Schluessel-Login ok: %s von %s", ich.get("email", "?"), ip)
    return {"ok": True, "name": alle[uid]["name"]}


def login_immich(request: Request, response: Response, daten: dict):
    """Anmeldung mit dem Immich-Konto. Das Passwort wird nur an Immich weitergereicht; gespeichert wird ein eigener, widerrufbarer
    API-Schluessel 'Immich Showcase' (ohne Loeschrechte) dieser Person. Die Immich-Sitzung wird sofort wieder beendet."""
    ip = client_ip(request)
    email = str(daten.get("email", "")).strip().lower()[:200]
    passwort = str(daten.get("passwort", ""))[:200]
    jetzt = time.time()
    schluessel_ip, schluessel_mail = ip, "mail:" + email
    with AUTH_LOCK:
        st = lies_json(AUTH_STATE, {"fehl": {}, "global": [], "alarm": 0})
        for k in (schluessel_ip, schluessel_mail):
            fehl = [t for t in st["fehl"].get(k, []) if jetzt - t < SPERRE_SEK]
            if len(fehl) >= FEHLVERSUCHE:
                rest = int(SPERRE_SEK - (jetzt - fehl[0]))
                raise HTTPException(429, f"Zu viele Versuche. Bitte in {max(rest // 60, 1)} Minuten erneut versuchen.")
    antwort = None
    if email and passwort:
        try:
            antwort = immich_aufruf("POST", "/auth/login", {"email": email, "password": passwort})
        except urllib.error.HTTPError as e:
            if e.code not in (400, 401):
                H.log.warning("Immich-Login: HTTP %s", e.code)
                raise HTTPException(502, "Immich ist gerade nicht erreichbar")
        except OSError as e:
            H.log.warning("Immich-Login: %s", e)
            raise HTTPException(502, "Immich ist gerade nicht erreichbar")
    if not antwort or not antwort.get("accessToken"):
        with AUTH_LOCK:
            st = lies_json(AUTH_STATE, {"fehl": {}, "global": [], "alarm": 0})
            for k in (schluessel_ip, schluessel_mail):
                st["fehl"][k] = [t for t in st["fehl"].get(k, []) if jetzt - t < SPERRE_SEK] + [jetzt]
            st["global"] = [t for t in st.get("global", []) if jetzt - t < 3600] + [jetzt]
            alarm = len(st["global"]) >= GLOBAL_ALARM and jetzt - st.get("alarm", 0) > 3600
            if alarm:
                st["alarm"] = jetzt
            schreibe_json(AUTH_STATE, st)
        H.log.warning("Falsche Immich-Anmeldung von %s", ip)
        if alarm:
            pushover("Immich Showcase: viele falsche Anmeldungen", f"{len(st['global'])} Fehlversuche in der letzten Stunde, zuletzt von {ip}", 1)
        time.sleep(1)
        raise HTTPException(401, "E-Mail oder Passwort falsch")
    token, uid = antwort["accessToken"], antwort["userId"]
    try:
        b = benutzer_lesen().get(uid) or {}
        schluessel = b.get("key")
        if schluessel:                                             # gespeicherter Schluessel noch gueltig?
            try:
                immich_aufruf("GET", "/api-keys/me", schluessel=schluessel)
            except urllib.error.HTTPError:
                schluessel = None
        if not schluessel:
            schluessel = immich_aufruf("POST", "/api-keys", {"name": KEY_NAME, "permissions": KEY_RECHTE}, token)["secret"]
        with AUTH_LOCK:
            alle = benutzer_lesen()
            alle[uid] = {"name": antwort.get("name") or email, "email": email, "key": schluessel, "zuletzt": jetzt}
            schreibe_json(BENUTZER_FILE, alle)
    finally:
        try:
            immich_aufruf("POST", "/auth/logout", {}, token)       # Immich-Sitzung nicht offen lassen
        except Exception:  # noqa: BLE001
            pass
    with AUTH_LOCK:
        st = lies_json(AUTH_STATE, {"fehl": {}, "global": [], "alarm": 0})
        st["fehl"].pop(schluessel_ip, None)
        st["fehl"].pop(schluessel_mail, None)
        schreibe_json(AUTH_STATE, st)
    response.set_cookie(COOKIE, sitzung_ausstellen(uid), max_age=COOKIE_TAGE * 86400, httponly=True,
                        samesite="strict", secure=request.headers.get("x-forwarded-proto") == "https")
    H.log.info("Immich-Login ok: %s von %s", email, ip)
    return {"ok": True, "name": antwort.get("name") or email}


@app.post("/api/logout")
def logout(response: Response, _=Depends(csrf)):
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/config")
def konfig(ziel: str = ""):
    """Oeffentliche Darstellung der Installation (kein Geheimnis): Name, Beispiele fuer die Suche, Adresse der Fernseher-Seite. Mit ?ziel= gelten die Einstellungen dieses Geraets."""
    z = ziel if ziel in GERAETE else None
    return {"name": APP_NAME, "version": VERSION, "modus": MODUS, "auth": AUTH, "musik_upload": MUSIK_UPLOAD, "konfiguriert": konfiguriert(), "tv_url": tv_url(), "beispiele": BEISPIELE, "beispiele_en": BEISPIELE_EN,
            "ziele": {k: v for k, v in TV_ZIELE.items() if k not in TV_VERSTECKT and k not in RAHMEN_ZIELE},
            "rahmen": list(RAHMEN_ZIELE), "rahmen_namen": dict(RAHMEN_ZIELE), "rahmen_sek": gwert(z, "sek", std_sek()), "rahmen_fuellung": gwert(z, "fuellung", std_fuellung_rahmen()), "tv_fuellung": gwert(z, "fuellung", std_fuellung_tv()),
            "rahmen_anzeige": gwert(z, "anzeige", std_anzeige()), "rahmen_nacht": rahmen_nacht(z), "rahmen_zusatz": zusatz_liste(), "koppeln": True,
            "alle_ziele": {k: v for k, v in TV_ZIELE.items() if k not in TV_VERSTECKT}}


# --------------------------------------------------------------------------- Einrichtungsassistent (nur solange nicht eingerichtet)

def konfiguriert():
    return bool(os.environ.get("RAHMEN_IMMICH_URL") and os.environ.get("RAHMEN_IMMICH_KEY"))


SETUP_CODE = {"wert": None}


def setup_code_erzeugen():
    """Ohne Einrichtung: Einmal-Code im Protokoll (nur wer das Protokoll lesen kann, darf den Server einrichten)."""
    if konfiguriert():
        return
    SETUP_CODE["wert"] = "%06d" % secrets.randbelow(10 ** 6)
    H.log.warning("=" * 66)
    H.log.warning(" Immich Showcase ist noch nicht eingerichtet. Oeffne  http://<server>:8090/setup/")
    H.log.warning(" und gib diesen Einrichtungs-Code ein: %s", SETUP_CODE["wert"])
    H.log.warning("=" * 66)


@app.on_event("startup")
def setup_start():
    setup_code_erzeugen()


def neu_starten():
    """Prozess neu starten, damit gespeicherte Einstellungen gelten (im Container: gleicher Aufruf, kein Containerneustart noetig)."""
    os.execv(sys.executable, [sys.executable] + sys.argv)


def setup_pruefen_code(request: Request, code: str):
    if konfiguriert():
        raise HTTPException(404, "nicht gefunden")
    ip = client_ip(request)
    jetzt = time.time()
    with AUTH_LOCK:
        st = lies_json(AUTH_STATE, {"fehl": {}, "global": [], "alarm": 0})
        k = "setup:" + ip
        fehl = [t for t in st["fehl"].get(k, []) if jetzt - t < SPERRE_SEK]
        if len(fehl) >= FEHLVERSUCHE:
            raise HTTPException(429, "Zu viele Versuche. Bitte spaeter erneut versuchen.")
        if SETUP_CODE["wert"] and hmac.compare_digest(str(code), SETUP_CODE["wert"]):
            return
        st["fehl"][k] = fehl + [jetzt]
        schreibe_json(AUTH_STATE, st)
    time.sleep(1)
    raise HTTPException(403, "Der Einrichtungs-Code stimmt nicht (er steht im Protokoll: docker compose logs)")


def immich_basis(url):
    url = str(url or "").strip().rstrip("/")
    if not re.match(r"^https?://[^\s/@]+(:\d+)?(/.*)?$", url):
        raise HTTPException(400, "Bitte eine Adresse wie http://192.168.1.10:2283 eingeben")
    return url if url.endswith("/api") else url + "/api"


@app.post("/api/setup/pruefen")
def setup_pruefen(request: Request, daten: dict, _=Depends(csrf)):
    setup_pruefen_code(request, daten.get("code", ""))
    basis = immich_basis(daten.get("url"))
    try:
        v = immich_aufruf("GET", "/server/version", basis=basis)
        return {"ok": True, "immich_version": f"{v['major']}.{v['minor']}.{v['patch']}", "url": basis}
    except urllib.error.HTTPError:
        raise HTTPException(400, "Unter dieser Adresse antwortet kein Immich")
    except (OSError, KeyError, ValueError, TypeError):
        raise HTTPException(400, "Immich ist unter dieser Adresse nicht erreichbar")


@app.post("/api/setup/speichern")
def setup_speichern(request: Request, daten: dict, _=Depends(csrf)):
    setup_pruefen_code(request, daten.get("code", ""))
    basis = immich_basis(daten.get("url"))
    schluessel = str(daten.get("schluessel") or "").strip()
    konto = ""
    token = angelegt = None
    try:
        if not schluessel:                                                     # Schluessel mit dem Immich-Konto selbst anlegen
            antwort = immich_aufruf("POST", "/auth/login", {"email": str(daten.get("email", "")).strip(), "password": str(daten.get("passwort", ""))}, basis=basis)
            token, konto = antwort["accessToken"], antwort.get("name") or antwort.get("userEmail", "")
            neu = immich_aufruf("POST", "/api-keys", {"name": KEY_NAME + " (Dienst)", "permissions": KEY_RECHTE}, token, basis=basis)
            schluessel, angelegt = neu["secret"], neu["apiKey"]["id"]
        ich = immich_aufruf("GET", "/api-keys/me", schluessel=schluessel, basis=basis)       # gueltig? (braucht keine Zusatzrechte)
        konto = konto or ich.get("name", "")
        rechte = set(ich.get("permissions") or [])
        if rechte and "all" not in rechte and not {"asset.read", "asset.view"} <= rechte:
            raise HTTPException(400, "Dem Schluessel fehlen Rechte (mindestens asset.read und asset.view, siehe Anleitung)")
    except urllib.error.HTTPError as e:
        if angelegt:                                                           # nichts Halbes in Immich zuruecklassen
            try:
                immich_aufruf("DELETE", "/api-keys/" + angelegt, token=token, basis=basis)
            except Exception:  # noqa: BLE001
                pass
        raise HTTPException(400, "E-Mail oder Passwort falsch" if e.code in (400, 401) and not daten.get("schluessel") else "Der Schluessel wird von Immich nicht akzeptiert")
    except (OSError, KeyError, ValueError, TypeError):
        raise HTTPException(400, "Immich ist unter dieser Adresse nicht erreichbar")
    finally:
        if token:
            try:
                immich_aufruf("POST", "/auth/logout", {}, token, basis=basis)
            except Exception:  # noqa: BLE001
                pass
    pin = str(daten.get("pin") or "").strip()
    erzeugt = None
    if AUTH != "immich":
        if not pin:
            pin = erzeugt = "%06d" % secrets.randbelow(10 ** 6)
        if not re.fullmatch(r"\d{6}", pin):
            raise HTTPException(400, "Die PIN muss genau 6 Ziffern haben")
        os.makedirs(os.path.dirname(PIN_FILE) or ".", exist_ok=True)
        fd = os.open(PIN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.write(fd, pin_hash(pin).encode())
        os.close(fd)
    einst = lies_json(EINSTELLUNGEN_FILE, {})
    einst.update({"RAHMEN_IMMICH_URL": basis, "RAHMEN_IMMICH_KEY": schluessel})
    name = str(daten.get("name") or "").strip()[:40]
    if name:
        einst["RAHMEN_WEB_NAME"] = name
    schreibe_json(EINSTELLUNGEN_FILE, einst)
    H.log.warning("Einrichtung abgeschlossen (Konto %s); Dienst startet neu", konto or "?")
    threading.Timer(1.5, neu_starten).start()
    return {"ok": True, "konto": konto, **({"pin": erzeugt} if erzeugt else {})}


@app.middleware("http")
async def einrichtung_noetig(request: Request, call_next):
    if not konfiguriert() and request.url.path.startswith("/api/") and not request.url.path.startswith(("/api/setup/", "/api/config", "/api/version", "/api/me")):
        return JSONResponse({"ok": False, "nachricht": "Einrichtung erforderlich", "setup": True}, status_code=503)
    return await call_next(request)


# --------------------------------------------------------------------------- Diagnose ("Support-Paket" ohne Geheimnisse)

LOGRING = collections.deque(maxlen=300)


class _RingHandler(logging.Handler):
    def emit(self, record):
        try:
            LOGRING.append(self.format(record))
        except Exception:  # noqa: BLE001
            pass


_ring = _RingHandler()
_ring.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logging.getLogger().addHandler(_ring)
for _n in ("uvicorn.error", "rahmen-helfer"):
    logging.getLogger(_n).addHandler(_ring)


def schwaerzen(text):
    """Entfernt alles, was wie ein Geheimnis aussieht (konfigurierte Schluessel, lange Zeichenketten, Adressen mit Zugangsdaten)."""
    for k in ("RAHMEN_IMMICH_KEY", "RAHMEN_DB_DSN", "RAHMEN_WEB_PUSHOVER_API_KEY", "RAHMEN_WEB_PUSHOVER_USER_KEY", "SHOWCASE_PIN"):
        v = os.environ.get(k, "")
        if len(v) >= 4:
            text = text.replace(v, "***")
    text = re.sub(r"://[^/@\s]+@", "://***@", text)
    return re.sub(r"[A-Za-z0-9_\-]{32,}", "***", text)


@app.get("/api/diagnose")
def diagnose(_=Depends(anmeldung)):
    """Alles, was bei einem Fehlerbericht hilft - ohne Schluessel, PIN oder Passwoerter."""
    jetzt = time.time()
    immich = {"adresse": re.sub(r"^(https?://)[^/]*@", r"\1", H.IMMICH)}
    try:
        v = immich_aufruf("GET", "/server/version")
        immich.update(erreichbar=True, version=f"{v['major']}.{v['minor']}.{v['patch']}")
    except Exception as e:  # noqa: BLE001
        immich.update(erreichbar=False, fehler=schwaerzen(str(e))[:200])
    try:
        immich["sichtbare_fotos"] = int(H.api("POST", "/search/statistics", {"type": "IMAGE", "visibility": "timeline"})["total"])
    except Exception as e:  # noqa: BLE001
        immich["schluessel_problem"] = schwaerzen(str(e))[:200]
    bib = {k: len(v["stuecke"]) for k, v in musik_bibliothek().items() if k != "alle"}
    return {
        "erstellt": datetime.datetime.now().isoformat(timespec="seconds"), "version": VERSION, "python": sys.version.split()[0],
        "immich": immich,
        "einstellungen": {"auth": AUTH, "modus": MODUS, "name": APP_NAME, "datenbank_aktiv": DB_AKTIV, "musik_upload": MUSIK_UPLOAD, "tv_ziele": list(TV_ZIELE), "rahmen_ziele": list(RAHMEN_ZIELE),
                          "vertraute_netze": [str(n) for n in LAN_NETS], "proxys": sorted(TRUSTED_PROXIES), "rahmen_quellen": len(RAHMEN_QUELLEN_ROH), "rahmen_fuellung": RAHMEN_FUELLUNG,
                          "rahmen_anzeige": RAHMEN_ANZEIGE, "rahmen_nacht": RAHMEN_NACHT, "alarm_minuten": std_alarm_min(), "konfiguriert": konfiguriert()},
        "musik_sammlungen": bib,
        "geraete": [{"id": z, "name": n, "zuletzt_gesehen_vor_s": int(jetzt - TV[z]["hb"]) if TV[z]["hb"] else None, "spielt": TV[z]["tv_name"] if TV[z]["tv_laeuft"] else None} for z, n in TV_ZIELE.items() if z not in TV_VERSTECKT],
        "protokoll": [schwaerzen(z) for z in LOGRING],
    }


@app.get("/api/me")
def me(request: Request):
    ip = client_ip(request)
    wert = request.cookies.get(COOKIE)
    sitzung = sitzung_lesen(wert) if wert else None
    if sitzung:
        return {"angemeldet": True, "lan": False, "auth": AUTH, "name": sitzung.get("name", "")}
    if AUTH == "pin" and ist_lan(ip):
        return {"angemeldet": True, "lan": True, "auth": AUTH}
    return {"angemeldet": False, "lan": False, "auth": AUTH}


# --------------------------------------------------------------------------- Filter / Listen

@app.get("/api/filter")
def filter_liste(_=Depends(anmeldung)):
    def holen():
        personen = sorted(n for n, _ in personen_karte().values())
        laender = sorted(({"wert": name, "name": LAND_DE.get(name, name)}
                          for typ, name in orte_karte().values() if typ == "country"), key=lambda l: l["name"])
        alben = [{"id": a["id"], "name": a["albumName"], "anzahl": a.get("assetCount", 0)}
                 for a in H.api("GET", "/albums") if not H.ist_helfer_album(a)]
        jahr = time.localtime().tm_year
        return {"personen": personen, "laender": laender, "alben": sorted(alben, key=lambda a: a["name"].lower()),
                "jahre": list(range(jahr, 1999, -1))}
    return zwischenspeicher("filter", 300, holen)


# --------------------------------------------------------------------------- verkoppelte Filter (Facetten)
# Jede Auswahl (Jahr, Land, Person, Medientyp) schraenkt die Moeglichkeiten der anderen ein: angeboten wird nur, wofuer es
# mit allen uebrigen Filtern mindestens ein Foto gibt. Abfrage direkt in der Immich-Datenbank (Nur-Lese-Rolle), ~10 ms.

# Datenbankzugriff ist OPTIONAL (nur Beschleunigung/Genauigkeit). Ohne RAHMEN_DB_DSN laeuft alles ueber die Immich-API.
DB_AKTIV = bool(os.environ.get("RAHMEN_DB_DSN")) and os.environ.get("RAHMEN_FACETTEN", "") != "api"


def db_lesen(sql, params=()):
    import psycopg
    with psycopg.connect(os.environ["RAHMEN_DB_DSN"], connect_timeout=10, autocommit=True) as c:
        return c.execute(sql, params).fetchall()


def facetten_bedingung(typ, jahr, ort, person, ohne=""):
    teile = ['a."deletedAt" is null', "a.visibility = 'timeline'",
             {"foto": "a.type = 'IMAGE'", "video": "a.type = 'VIDEO'", "alle": "a.type in ('IMAGE', 'VIDEO')"}[typ]]
    params = []
    if jahr and ohne != "jahr":
        teile.append('extract(year from a."localDateTime") = %s')
        params.append(jahr)
    if ort and ohne != "ort":
        teile.append('exists (select 1 from asset_exif e where e."assetId" = a.id and e.country = %s)')
        params.append(ort)
    if person and ohne != "person":
        teile.append('exists (select 1 from asset_face f join person p on p."personGroupId" = f."personGroupId" '
                     'where f."assetId" = a.id and f."deletedAt" is null and p.name = %s and not p."isHidden")')
        params.append(person)
    return " and ".join(teile), params


def _stat(**filt):
    return int(H.api("POST", "/search/statistics", filt)["total"])


def facetten_api(typ, jahr, ort, person):
    """Gleiche Zaehler wie facetten_db, nur ueber die Immich-API (/search/statistics). Parallel, Ergebnis wird zwischengespeichert."""
    from concurrent.futures import ThreadPoolExecutor
    pk = personen_karte()
    pid = {n: i for n, i in pk.values()}
    laender = zwischenspeicher(("laenderliste",), 3600, lambda: H.api("GET", "/search/suggestions?type=country") or [])
    erstes = zwischenspeicher(("erstesjahr", typ), 3600, lambda: int(((H.api("POST", "/search/metadata", dict(
        ({"type": "IMAGE"} if typ == "foto" else {"type": "VIDEO"} if typ == "video" else {}), order="asc", size=1))["assets"]["items"] or [{"localDateTime": "2000"}])[0].get("localDateTime") or "2000")[:4]))
    jahre = list(range(erstes, datetime.date.today().year + 1))
    basis = {"visibility": "timeline"}                  # wie die Datenbankvariante: keine versteckten/archivierten Medien (z. B. Live-Foto-Videos)
    if typ != "alle":
        basis["type"] = "IMAGE" if typ == "foto" else "VIDEO"

    def fenster(y):
        # Immich filtert nach UTC-Aufnahmezeit, die Datenbankvariante nach Ortszeit: an der Jahreswende weichen wenige Fotos ab (gemessen: 4 von 29.282)
        return {"takenAfter": f"{y}-01-01T00:00:00.000Z", "takenBefore": f"{y + 1}-01-01T00:00:00.000Z"}

    def mit(ohne, **extra):
        f = dict(basis)
        if person and ohne != "person":
            f["personIds"] = [pid[person]]
        if ort and ohne != "ort":
            f["country"] = ort
        if jahr and ohne != "jahr":
            f.update(fenster(jahr))
        f.update(extra)
        return f

    with ThreadPoolExecutor(8) as ex:
        fj = {y: ex.submit(contextvars.copy_context().run, _stat, **mit("jahr", **fenster(y))) for y in jahre}
        fl = {c: ex.submit(contextvars.copy_context().run, _stat, **mit("ort", country=c)) for c in laender}
        fp = {n: ex.submit(contextvars.copy_context().run, _stat, **mit("person", personIds=[i])) for n, i in pid.items()}
        fg = ex.submit(contextvars.copy_context().run, _stat, **mit(""))
        zj = {y: f.result() for y, f in fj.items()}
        zl = {c: f.result() for c, f in fl.items()}
        zp = {n: f.result() for n, f in fp.items()}
        gesamt = fg.result()
    return {"jahre": [{"wert": y, "anzahl": n} for y, n in sorted(zj.items(), reverse=True) if n],
            "laender": sorted(({"wert": c, "name": LAND_DE.get(c, c), "anzahl": n} for c, n in zl.items() if n), key=lambda x: x["name"].lower()),
            "personen": [{"name": n, "anzahl": c} for n, c in sorted(zp.items()) if c], "gesamt": gesamt}


@app.get("/api/facetten")
def facetten(typ: str = "foto", jahr: int = 0, ort: str = "", person: str = "", _=Depends(anmeldung)):
    if typ not in ("foto", "alle", "video") or len(ort) > 80 or len(person) > 100 or not (jahr == 0 or 1900 <= jahr <= 2100):
        raise HTTPException(400, "Ungueltige Filter")

    def holen():
        b, p = facetten_bedingung(typ, jahr, ort, person, "jahr")
        jahre = db_lesen(f'select extract(year from a."localDateTime")::int, count(*) from asset a where {b} group by 1 order by 1 desc', p)
        b, p = facetten_bedingung(typ, jahr, ort, person, "ort")
        laender = db_lesen(f"select e.country, count(*) from asset a join asset_exif e on e.\"assetId\" = a.id where {b} "
                           f"and e.country is not null and e.country <> '' group by 1 order by 1", p)
        b, p = facetten_bedingung(typ, jahr, ort, person, "person")
        personen = db_lesen(f'select p.name, count(distinct a.id) from asset a join asset_face f on f."assetId" = a.id and f."deletedAt" is null '
                            f'join person p on p."personGroupId" = f."personGroupId" where {b} and p.name <> \'\' and not p."isHidden" group by 1 order by 1', p)
        b, p = facetten_bedingung(typ, jahr, ort, person)
        gesamt = db_lesen(f"select count(*) from asset a where {b}", p)[0][0]
        return {"jahre": [{"wert": j, "anzahl": n} for j, n in jahre],
                "laender": sorted(({"wert": c, "name": LAND_DE.get(c, c), "anzahl": n} for c, n in laender), key=lambda x: x["name"].lower()),
                "personen": [{"name": n, "anzahl": c} for n, c in personen], "gesamt": gesamt}
    return zwischenspeicher(("facetten", typ, jahr, ort, person), 60, holen if DB_AKTIV else (lambda: facetten_api(typ, jahr, ort, person)))


@app.get("/api/neueste")
def neueste(cursor: int = 1, limit: int = 90, person: str = "", jahr: int = 0, ort: str = "", album: str = "",
            favoriten: int = 0, typ: str = "foto", _=Depends(anmeldung)):
    limit = max(10, min(limit, 200))
    body = {"order": "desc", "size": limit, "page": max(cursor, 1), "withExif": True}
    if typ == "foto":
        body["type"] = "IMAGE"
    elif typ == "video":
        body["type"] = "VIDEO"
    elif typ != "alle":
        raise HTTPException(400, "Unbekannter Medientyp")
    if person:
        treffer = personen_karte().get(H.norm(person))
        if not treffer:
            raise HTTPException(400, "Person unbekannt")
        body["personIds"] = [treffer[1]]
    if jahr:
        body["takenAfter"] = f"{jahr}-01-01T00:00:00.000Z"
        body["takenBefore"] = f"{jahr + 1}-01-01T00:00:00.000Z"
    if ort:
        schluessel = H.norm(ort)
        eintrag = orte_karte().get(H.norm(H.ORT_DE.get(schluessel, ort)))
        if not eintrag:
            raise HTTPException(400, "Ort unbekannt")
        body[eintrag[0]] = eintrag[1]
    if album:
        if not ID_RE.match(album):
            raise HTTPException(400, "Album ungueltig")
        body["albumIds"] = [album]
    if favoriten:
        body["isFavorite"] = True
    d = H.api("POST", "/search/metadata", body)["assets"]
    fotos = [foto_dict(a) for a in d["items"]
             if (a.get("type") == "VIDEO") or (a.get("type") == "IMAGE" and not H.ist_screenshot(a))]
    return {"fotos": fotos, "weiter": int(d["nextPage"]) if d.get("nextPage") else None}


@app.get("/api/suche")
def suchen(text: str, maximum: int = 400, lang: str = "de", _=Depends(anmeldung)):
    text = text.strip()
    if not text or len(text) > 200:
        raise HTTPException(400, "Suchtext fehlt oder ist zu lang")
    personen, alias = zwischenspeicher("personen", 300, H.lade_personen)
    erg = H.parse(text, personen, alias, orte_karte(), lang if lang in H.SPRACHEN else "de")
    info = {"personen": [n for n, _ in erg["personen"]], "ort": erg["ort"][1] if erg["ort"] else None,
            "zeitraeume": len(erg["zeit"]), "favoriten": erg["favoriten"], "motiv": erg["motiv"]}
    if erg["rueckfrage"]:
        return {"ok": False, "nachricht": erg["rueckfrage"], "erkannt": info, "fotos": []}
    if not any([erg["personen"], erg["zeit"], erg["ort"], erg["favoriten"], erg["motiv"]]):
        return {"ok": False, "erkannt": info, "fotos": [],
                "nachricht": "Das habe ich nicht verstanden. Beispiel: " + H.BEISPIEL_TEXT + "."}
    grenze = max(20, min(maximum, 800))
    hinweis = ""
    try:
        roh = H.suche(erg)
    except (urllib.error.HTTPError, OSError) as e:
        if not erg["motiv"] or isinstance(e, urllib.error.HTTPError) and e.code in (401, 403):
            raise
        # Bildsuche (Immich Machine Learning) nicht verfuegbar: ohne Motiv weitersuchen statt nur einen Fehler zu zeigen
        H.log.warning("Motivsuche nicht moeglich (%s) - Suche ohne Motiv", e)
        motiv, erg["motiv"] = erg["motiv"], ""
        info["motiv"] = ""
        if not any([erg["personen"], erg["zeit"], erg["ort"], erg["favoriten"]]):
            return {"ok": False, "erkannt": info, "fotos": [], "nachricht": "Die Bildsuche (Immich Machine Learning) ist gerade nicht verfuegbar. Suchen nach Person, Zeit oder Ort geht weiter."}
        roh = H.suche(erg)
        hinweis = f" (Die Motivsuche nach \"{motiv}\" ist gerade nicht verfuegbar – ohne Motiv gesucht)"
    fotos = H.auswahl(roh, maximum=grenze)
    if not fotos and erg["favoriten"]:
        erg["favoriten"] = False
        roh = H.suche(erg)
        fotos = H.auswahl(roh, maximum=grenze)
        hinweis = " (keine Favoriten markiert – ich zeige alle passenden)"
    if not fotos:
        return {"ok": True, "nachricht": "Dazu habe ich keine Fotos gefunden.", "erkannt": info, "gesamt": 0, "fotos": []}
    return {"ok": True, "nachricht": H.beschreibe(erg, len(fotos)) + hinweis, "erkannt": info,
            "gesamt": len(roh), "fotos": [foto_dict(a) for a in fotos]}


@app.get("/api/vorschau/{asset_id}")
def vorschau(asset_id: str, s: str = "thumb", _=Depends(geraet)):
    if not ID_RE.match(asset_id):
        raise HTTPException(400, "ungueltig")
    groesse = "preview" if s == "gross" else "thumbnail"
    try:
        roh, typ = immich_roh(f"/assets/{asset_id}/thumbnail?size={groesse}", schluessel=None if UID_CTX.get() else geraete_schluessel(asset_id))
    except urllib.error.HTTPError as e:
        raise HTTPException(404 if e.code in (400, 403, 404) else 502, "Foto nicht verfuegbar")
    return Response(roh, media_type=typ, headers={"Cache-Control": "private, max-age=604800, immutable"})


# --------------------------------------------------------------------------- Shows / Verlauf / Zurueck

VERLAUF_MAX = 25      # nicht gemerkte Eintraege ("Zuletzt gezeigt")
GEMERKT_MAX = 50


def shows_datei():
    uid = UID_CTX.get()
    return SHOWS_FILE if not uid else os.path.splitext(SHOWS_FILE)[0] + f"-{uid}.json"          # jede Person hat eigene Shows


def daten_lesen():
    d = lies_json(shows_datei(), {})
    d.setdefault("shows", [])
    d.setdefault("zurueck", None)
    for s in d["shows"]:
        s.setdefault("gemerkt", True)       # Eintraege aus der ersten Fassung
    return d


def daten_schreiben(d):
    gem = ver = 0
    behalten = []
    for s in d["shows"]:                    # Liste ist neueste-zuerst
        if s.get("gemerkt"):
            gem += 1
            if gem <= GEMERKT_MAX:
                behalten.append(s)
        else:
            ver += 1
            if ver <= VERLAUF_MAX:
                behalten.append(s)
    d["shows"] = behalten
    schreibe_json(shows_datei(), d)


def jetzt():
    return time.strftime("%Y-%m-%dT%H:%M")


# --------------------------------------------------------------------------- Rahmen: Player oder immich-kiosk
# Mit RAHMEN_WEB_RAHMEN_ZIELE laeuft der Rahmen ueber den eigenen Player (Seite /tv/?ziel=...): Shows sind Ereignisse fuer dieses Ziel.
# Ohne laeuft er wie bisher ueber ein temporaeres Immich-Album, das immich-kiosk anzeigt (Helfer + Sync-Skript auf dem Host).
PLAYER = next(iter(RAHMEN_ZIELE), None)          # Standard-Rahmen (der erste); weitere Rahmen werden mit 'ziel' angesprochen
PLAYER_REIHE = {}                                # Rahmen -> "alt" | "neu" | "zufall"


def reihe_von(z):
    return PLAYER_REIHE.get(z or PLAYER, "alt")


def rahmen_pruefen(z):
    """Kennung eines Rahmens pruefen; leer = Standard-Rahmen. Ohne Eigenplayer (Kiosk-Weg) gibt es nur den einen Rahmen: None."""
    if not PLAYER:
        return None
    z = str(z or "").strip() or PLAYER
    if z not in RAHMEN_ZIELE:
        raise HTTPException(400, "Unbekannter Rahmen")
    return z


def rahmen_liste_pruefen(daten):
    """'ziele': [...] (oder 'ziel': '...') -> Liste gueltiger Rahmen ohne Doppelte; leer = Standard-Rahmen."""
    roh = daten.get("ziele")
    if roh is None:
        roh = [daten.get("ziel")]
    if not isinstance(roh, list):
        raise HTTPException(400, "Ungueltige Rahmen-Auswahl")
    liste = list(dict.fromkeys(rahmen_pruefen(z) for z in roh if z or len(roh) == 1))
    return liste or [rahmen_pruefen(None)]


def rahmen_namen(liste):
    namen = [RAHMEN_ZIELE.get(z, "Bilderrahmen") for z in liste if z]
    return ", ".join(namen) if namen else "dem Bilderrahmen"


AKTIV_BESITZER = {}        # Ziel -> (Menge der Medien-IDs, Benutzer-ID): Geraete holen Fotos mit dem Schluessel dessen, der die Show geschickt hat


def geraete_schluessel(asset_id):
    for ids, uid in list(AKTIV_BESITZER.values()):
        if uid and asset_id in ids:
            return (benutzer_lesen().get(uid) or {}).get("key")
    return None


def player_ereignis(z, felder):
    t = TV[z]
    AKTIV_BESITZER[z] = (set(felder.get("ids") or []), UID_CTX.get())
    with TV_EV:
        t["seq"] += 1
        ev = {"seq": t["seq"], "typ": "start", "seit": datetime.datetime.now().isoformat(timespec="seconds"), **felder}
        t["events"] = (t["events"] + [ev])[-30:]
        t["aktiv"] = ev
    aktiv_speichern()


def player_zeigen(name, ids, reihe="alt", ziel=None):
    ziel = ziel or PLAYER
    PLAYER_REIHE[ziel] = reihe
    geordnet = nach_datum(ids, reihe == "alt") if reihe != "zufall" and len(ids) > 1 else list(ids)
    player_ereignis(ziel, {"ids": geordnet, "name": name, "sek": rahmen_sek(ziel), "zufall": reihe == "zufall", "musik": "", "laut": 0.3, "videos": [], "maxv": 0})
    return len(ids)


def rahmen_anzeigen(name, ids, ziel=None):
    if not PLAYER and REGISTER["aktiv"]:
        raise ValueError("Es ist noch kein Bilderrahmen eingerichtet (Geräte → Gerät hinzufügen).")
    return player_zeigen(name, ids, ziel=ziel) if PLAYER else H.album_anzeigen(name, ids)


def rahmen_normal(ziel=None):
    if PLAYER:
        ziel = ziel or PLAYER
        t = TV[ziel]
        with TV_EV:
            t["seq"] += 1
            t["events"] = (t["events"] + [{"seq": t["seq"], "typ": "steuer", "aktion": "stopp", "wert": ""}])[-30:]
            t["aktiv"] = None
        AKTIV_BESITZER.pop(ziel, None)
        aktiv_speichern()
        return {"ok": True, "nachricht": "Der Bilderrahmen zeigt wieder das normale Programm." if len(RAHMEN_ZIELE) < 2 else f"{RAHMEN_ZIELE[ziel]} zeigt wieder das normale Programm."}
    return H.normal()


def rahmen_state(ziel=None):
    """Was laeuft gerade auf dem Rahmen? {'wunsch','ids','seit','anzahl','reihenfolge','album'} (wunsch None = normales Programm)."""
    if PLAYER:
        ziel = ziel or PLAYER
        ev = TV[ziel]["aktiv"]
        if ev and ev.get("typ") == "start":
            return {"wunsch": ev["name"], "ids": ev["ids"], "seit": ev.get("seit"), "anzahl": len(ev["ids"]), "reihenfolge": reihe_von(ziel), "album": None}
        return {"wunsch": None, "ids": [], "seit": None, "anzahl": None, "reihenfolge": reihe_von(ziel), "album": None}
    st = H.lade_state()
    return {"wunsch": st.get("wunsch") if st.get("album") else None, "ids": None, "seit": st.get("seit"), "anzahl": st.get("anzahl"),
            "reihenfolge": st.get("reihenfolge", "alt"), "album": st.get("album")}


def neue_show(name, ids, gemerkt):
    return {"id": uuid.uuid4().hex[:12], "name": name, "ids": ids, "zeit": jetzt(), "gemerkt": bool(gemerkt)}


def album_ids(album_id):
    ids, seite = [], 1
    while seite:
        d = H.api("POST", "/search/metadata", {"albumIds": [album_id], "size": 1000, "page": seite})["assets"]
        ids += [a["id"] for a in d["items"]]
        seite = int(d["nextPage"]) if d.get("nextPage") else None
    return ids


def name_pruefen(name):
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    if not 1 <= len(name) <= 60:
        raise HTTPException(400, "Bitte einen Namen (1-60 Zeichen) eingeben")
    return name


def ids_pruefen(ids):
    if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_IDS:
        raise HTTPException(400, f"Bitte 1 bis {MAX_IDS} Fotos auswaehlen")
    sauber = list(dict.fromkeys(str(i) for i in ids))
    if not all(ID_RE.match(i) for i in sauber):
        raise HTTPException(400, "Ungueltige Foto-ID")
    return sauber


def finde(d, show_id):
    return next((s for s in d["shows"] if s["id"] == show_id), None)


def zurueck_holen(d, ziel=None):
    """'Zurueck'-Merker eines Rahmens: der Standard-Rahmen nutzt das alte Feld 'zurueck', weitere stehen in 'zurueck_je'."""
    if not ziel or ziel == PLAYER:
        return d.get("zurueck")
    return (d.get("zurueck_je") or {}).get(ziel)


def zurueck_setzen(d, ziel, wert):
    if not ziel or ziel == PLAYER:
        d["zurueck"] = wert
    else:
        d.setdefault("zurueck_je", {})[ziel] = wert


def aktuelle_erfassen(d, ziel=None):
    """Was laeuft gerade auf dem Rahmen? Gibt {'typ':'normal'} oder {'typ':'show','id':...} zurueck und legt bei
    Bedarf einen Verlaufseintrag an (auch fuer Shows, die ueber HA/Siri gestartet wurden)."""
    st = rahmen_state(ziel)
    if not st["wunsch"]:
        return {"typ": "normal"}
    name = (st["wunsch"] or "Unbenannt").strip()
    try:
        ids = st["ids"] if st["ids"] is not None else album_ids(st["album"])
    except Exception:  # noqa: BLE001 - Album weg oder nicht lesbar: dann gilt es als normales Programm
        return {"typ": "normal"}
    if not ids:
        return {"typ": "normal"}
    for s in d["shows"]:
        if H.norm(s["name"]) == H.norm(name) and set(s["ids"]) == set(ids):
            return {"typ": "show", "id": s["id"]}
    titel = name if not any(H.norm(s["name"]) == H.norm(name) for s in d["shows"]) else f"{name} ({(st.get('seit') or jetzt())[:16].replace('T', ' ')})"
    e = neue_show(titel[:60], ids, False)
    d["shows"].insert(0, e)
    return {"typ": "show", "id": e["id"]}


def zeigen(d, name, ids, gemerkt=None, show_id=None, ziel=None):
    """Zeigt eine Auswahl auf dem Rahmen, fuehrt Verlauf und 'Zurueck' mit. Aufrufer haelt H.LOCK."""
    vorher = aktuelle_erfassen(d, ziel)
    anzahl = rahmen_anzeigen(name, ids, ziel)
    e = finde(d, show_id) if show_id else next((s for s in d["shows"] if H.norm(s["name"]) == H.norm(name)), None)
    if e:
        e.update({"ids": ids, "zeit": jetzt(), "name": name})
        if gemerkt:
            e["gemerkt"] = True
        d["shows"].remove(e)
    else:
        e = neue_show(name, ids, bool(gemerkt))
    d["shows"].insert(0, e)
    if not (vorher.get("typ") == "show" and vorher.get("id") == e["id"]):
        zurueck_setzen(d, ziel, vorher)
    daten_schreiben(d)
    return anzahl, e


def zurueck_name(d, ziel=None):
    z = zurueck_holen(d, ziel)
    if not z:
        return None
    if z.get("typ") == "normal":
        return "Normales Programm"
    e = finde(d, z.get("id"))
    return e["name"] if e else None


@app.post("/api/anzeigen")
def anzeigen(daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    """Schickt eine Auswahl auf den Rahmen. 'dry': nur pruefen. 'speichern': zusaetzlich dauerhaft merken (Stern)."""
    name = name_pruefen(daten.get("name"))
    ids = ids_pruefen(daten.get("ids"))
    ziele = rahmen_liste_pruefen(daten)
    if daten.get("dry"):
        return {"ok": True, "nachricht": f"(Test) {len(ids)} Fotos als \"{name}\" wuerden auf den Rahmen gehen.", "anzahl": len(ids), "ziele": ziele}
    with H.LOCK:
        d = daten_lesen()
        try:
            for z in ziele:
                anzahl, e = zeigen(d, name, ids, gemerkt=bool(daten.get("speichern")), ziel=z)
        except ValueError as ex:
            raise HTTPException(400, str(ex))
    H.log.info("Rahmen-Web: '%s' mit %d Fotos auf %s", name, anzahl, ", ".join(z or "den Rahmen" for z in ziele))
    return {"ok": True, "anzahl": anzahl, "show": e["id"], "zurueck": zurueck_name(d, ziele[0]), "ziele": ziele,
            "nachricht": f"\"{name}\" mit {anzahl} Fotos läuft gleich auf {'dem Bilderrahmen' if len(RAHMEN_ZIELE) < 2 else rahmen_namen(ziele)}."}


@app.get("/api/shows")
def shows(_=Depends(anmeldung)):
    d = daten_lesen()
    je = {z: H.norm(rahmen_state(z)["wunsch"] or "") for z in (RAHMEN_ZIELE or [None])}
    return {"zurueck": zurueck_name(d),
            "shows": [{"id": s["id"], "name": s["name"], "anzahl": len(s["ids"]), "zeit": s.get("zeit"),
                       "gemerkt": s.get("gemerkt", True), "laeuft": H.norm(s["name"]) in je.values(),
                       "laeuft_auf": [z for z, n in je.items() if z and H.norm(s["name"]) == n]} for s in d["shows"]]}


@app.get("/api/shows/{show_id}")
def show_holen(show_id: str, _=Depends(anmeldung)):
    s = finde(daten_lesen(), show_id)
    if not s:
        raise HTTPException(404, "Show nicht gefunden")
    return {"id": s["id"], "name": s["name"], "zeit": s.get("zeit"), "gemerkt": s.get("gemerkt", True),
            "fotos": [{"id": i} for i in s["ids"]]}


@app.put("/api/shows/{show_id}")
def show_aendern(show_id: str, daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    with H.LOCK:
        d = daten_lesen()
        s = finde(d, show_id)
        if not s:
            raise HTTPException(404, "Show nicht gefunden")
        if "name" in daten:
            s["name"] = name_pruefen(daten["name"])
        if "ids" in daten:
            s["ids"] = ids_pruefen(daten["ids"])
        if "gemerkt" in daten:
            s["gemerkt"] = bool(daten["gemerkt"])
        daten_schreiben(d)
    return {"ok": True}


@app.delete("/api/shows/{show_id}")
def show_loeschen(show_id: str, _=Depends(anmeldung), __=Depends(csrf)):
    with H.LOCK:
        d = daten_lesen()
        s = finde(d, show_id)
        if not s:
            raise HTTPException(404, "Show nicht gefunden")
        d["shows"].remove(s)
        if (d.get("zurueck") or {}).get("id") == show_id:
            d["zurueck"] = None
        daten_schreiben(d)
    return {"ok": True}


@app.post("/api/shows/{show_id}/anzeigen")
def show_anzeigen(show_id: str, daten: dict = None, _=Depends(anmeldung), __=Depends(csrf)):
    with H.LOCK:
        d = daten_lesen()
        s = finde(d, show_id)
        if not s:
            raise HTTPException(404, "Show nicht gefunden")
        ziele = rahmen_liste_pruefen(daten or {})
        if (daten or {}).get("dry"):
            return {"ok": True, "nachricht": f"(Test) \"{s['name']}\" mit {len(s['ids'])} Fotos wuerde laufen.", "anzahl": len(s["ids"]), "ziele": ziele}
        try:
            for z in ziele:
                anzahl, _e = zeigen(d, s["name"], list(s["ids"]), show_id=show_id, ziel=z)
        except ValueError as ex:
            raise HTTPException(400, str(ex))
    return {"ok": True, "anzahl": anzahl, "zurueck": zurueck_name(d, ziele[0]), "ziele": ziele,
            "nachricht": f"\"{s['name']}\" mit {anzahl} Fotos läuft gleich auf {'dem Bilderrahmen' if len(RAHMEN_ZIELE) < 2 else rahmen_namen(ziele)}."}


@app.post("/api/zurueck")
def zurueck(daten: dict = None, _=Depends(anmeldung), __=Depends(csrf)):
    """Springt auf das zuvor gezeigte Album (oder das normale Programm) zurueck; nochmal tippen wechselt wieder."""
    rz = rahmen_pruefen((daten or {}).get("ziel"))
    with H.LOCK:
        d = daten_lesen()
        z = zurueck_holen(d, rz)
        if not z:
            raise HTTPException(404, "Es gibt noch nichts, wohin ich zurückgehen könnte.")
        ziel = None if z.get("typ") == "normal" else finde(d, z.get("id"))
        if z.get("typ") != "normal" and not ziel:
            zurueck_setzen(d, rz, None)
            daten_schreiben(d)
            raise HTTPException(404, "Die vorherige Show gibt es nicht mehr.")
        if (daten or {}).get("dry"):
            return {"ok": True, "nachricht": f"(Test) Zurück zu: {zurueck_name(d, rz)}", "ziel": zurueck_name(d, rz)}
        vorher = aktuelle_erfassen(d, rz)
        if ziel is None:
            text = rahmen_normal(rz)["nachricht"]
        else:
            try:
                rahmen_anzeigen(ziel["name"], list(ziel["ids"]), rz)
            except ValueError as ex:
                raise HTTPException(400, str(ex))
            ziel["zeit"] = jetzt()
            d["shows"].remove(ziel)
            d["shows"].insert(0, ziel)
            text = f"Zurück bei \"{ziel['name']}\" ({len(ziel['ids'])} Fotos) – läuft gleich auf dem Rahmen."
        zurueck_setzen(d, rz, vorher if vorher != z else None)
        daten_schreiben(d)
    return {"ok": True, "nachricht": text, "zurueck": zurueck_name(d, rz)}


@app.get("/api/status")
def status(ziel: str = "", _=Depends(anmeldung)):
    rz = rahmen_pruefen(ziel)
    st = rahmen_state(rz)
    titelbild = None
    if st["album"]:
        try:
            titelbild = H.api("GET", f"/albums/{st['album']}").get("albumThumbnailAssetId")
        except Exception:  # noqa: BLE001 - Titelbild ist nur Zierde
            titelbild = None
    if st["wunsch"]:
        nachricht = f"Läuft gerade: \"{st['wunsch']}\" ({st['anzahl']} Fotos, seit {st['seit']})"
    else:
        nachricht = "Der Bilderrahmen zeigt das normale Programm."
    d = daten_lesen()
    return {"ok": True, "nachricht": nachricht, "laeuft": st["wunsch"], "anzahl": st["anzahl"],
            "seit": st["seit"], "zurueck": zurueck_name(d, rz), "titelbild": titelbild,
            "reihenfolge": st["reihenfolge"], "ziel": rz,
            "rahmen": [{"id": z, "name": n, "laeuft": rahmen_state(z)["wunsch"], "online": time.time() - TV[z]["hb"] < 10} for z, n in RAHMEN_ZIELE.items()]}


@app.post("/api/reihenfolge")
def reihenfolge(daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    r = str(daten.get("reihenfolge", ""))
    if r not in ("alt", "neu", "zufall"):
        raise HTTPException(400, "Unbekannte Reihenfolge")
    if PLAYER:
        rz = rahmen_pruefen(daten.get("ziel"))
        st = rahmen_state(rz)
        if st["wunsch"]:
            player_zeigen(st["wunsch"], list(st["ids"]), r, rz)      # gleiche Show, neu geordnet, beginnt von vorn
        else:
            PLAYER_REIHE[rz] = r
    else:
        try:
            H.reihenfolge_setzen(r)
        except ValueError as e:
            raise HTTPException(400, str(e))
    return {"ok": True, "nachricht": {"alt": "Der Rahmen zeigt jetzt zeitlich: ältestes zuerst.", "neu": "Der Rahmen zeigt jetzt zeitlich: neuestes zuerst.", "zufall": "Der Rahmen zeigt jetzt in zufälliger Reihenfolge."}[r]}


@app.post("/api/normal")
def normal(daten: dict = None, _=Depends(anmeldung), __=Depends(csrf)):
    rz = rahmen_pruefen((daten or {}).get("ziel"))
    with H.LOCK:
        d = daten_lesen()
        vorher = aktuelle_erfassen(d, rz)
        r = rahmen_normal(rz)
        if vorher.get("typ") == "show":
            zurueck_setzen(d, rz, vorher)
        daten_schreiben(d)
    r["zurueck"] = zurueck_name(d, rz)
    return r


# --------------------------------------------------------------------------- Fernseher (Video fuer AirPlay)
# Der Server baut aus der Auswahl ein Video (jedes Foto n Sekunden, Hintergrund weichgezeichnet). Das Geraet des
# Nutzers (iPhone/Mac, Safari) schickt es per AirPlay an LG TV oder Shield - der Server selbst erreicht diese
# Geraete nicht (andere Netzsegmente) und muss es auch nicht.

TV_DIR = os.environ.get("RAHMEN_WEB_TV_DIR", "/data/tv")
TV_MAX = 150
TV_JOBS = {}
TV_LOCK = threading.Lock()                 # nur ein Video gleichzeitig (schont den Host)
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
TV_FILTER = ("[0:v]split[a][b];[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=40:6[bg];"
             "[b]scale=1920:1080:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
TV_DATEI_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}\.mp4$")


def tv_aufraeumen():
    jetzt_ = time.time()
    try:
        for n in os.listdir(TV_DIR):
            p = os.path.join(TV_DIR, n)
            if jetzt_ - os.path.getmtime(p) > 12 * 3600:
                shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
    except OSError:
        pass


def tv_bauen(job, ids, sek):
    tok = job["token"]
    arbeit = os.path.join(TV_DIR, "tmp-" + tok)
    try:
        os.makedirs(arbeit)
        with TV_LOCK:
            n = len(ids)
            for i, aid in enumerate(ids, 1):
                roh, _typ = immich_roh(f"/assets/{aid}/thumbnail?size=preview", timeout=60)
                src, dst = os.path.join(arbeit, f"src{i}.jpg"), os.path.join(arbeit, f"{i:04d}.jpg")
                with open(src, "wb") as f:
                    f.write(roh)
                r = subprocess.run(["nice", "-n", "15", FFMPEG, "-nostdin", "-v", "error", "-y", "-i", src, "-filter_complex", TV_FILTER,
                                    "-frames:v", "1", "-q:v", "3", dst], capture_output=True, timeout=90)
                os.remove(src)
                if r.returncode or not os.path.exists(dst):
                    raise RuntimeError("Ein Foto liess sich nicht aufbereiten")
                job["fortschritt"] = round(0.85 * i / n, 3)
            out = os.path.join(TV_DIR, tok + ".mp4")
            # Standard-Video (High-Profil, BT.709, normaler Farbbereich, stille Tonspur) - damit auch Fernseher/AirPlay-Empfaenger sicher damit klarkommen
            r = subprocess.run(["nice", "-n", "15", FFMPEG, "-nostdin", "-v", "error", "-y", "-framerate", f"1/{sek}", "-i", os.path.join(arbeit, "%04d.jpg"),
                                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                                "-vf", "fps=10,scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
                                "-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-preset", "veryfast", "-crf", "27", "-threads", "2",
                                "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                                "-c:a", "aac", "-b:a", "32k", "-shortest", "-movflags", "+faststart", out], capture_output=True, timeout=1800)
            if r.returncode or not os.path.exists(out):
                raise RuntimeError("Das Video liess sich nicht erzeugen")
            job.update(status="fertig", fortschritt=1.0, dauer=n * sek, groesse=os.path.getsize(out))
    except Exception as e:  # noqa: BLE001
        H.log.warning("TV-Video fehlgeschlagen: %s", e)
        job.update(status="fehler", nachricht="Das Video konnte nicht vorbereitet werden. Bitte nochmal versuchen.")
    finally:
        shutil.rmtree(arbeit, ignore_errors=True)


@app.post("/api/tv/video")
def tv_video(daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    ids = ids_pruefen(daten.get("ids"))
    if len(ids) > TV_MAX:
        raise HTTPException(400, f"Für den Fernseher höchstens {TV_MAX} Fotos pro Video.")
    try:
        sek = max(3, min(int(daten.get("sekunden", 5)), 30))
    except (TypeError, ValueError):
        sek = 5
    if any(j["status"] == "laeuft" for j in TV_JOBS.values()):
        raise HTTPException(429, "Es wird gerade schon ein Video vorbereitet. Bitte kurz warten.")
    tv_aufraeumen()
    tok = secrets.token_urlsafe(24)
    job = {"token": tok, "status": "laeuft", "fortschritt": 0.0, "anzahl": len(ids), "sekunden": sek}
    for alt in list(TV_JOBS)[:-9]:
        TV_JOBS.pop(alt, None)
    TV_JOBS[tok] = job
    thread_mit_kontext(tv_bauen, job, ids, sek)
    return {"ok": True, "job": tok}


@app.get("/api/tv/job/{job_id}")
def tv_job(job_id: str, _=Depends(anmeldung)):
    j = TV_JOBS.get(job_id)
    if not j:
        raise HTTPException(404, "Auftrag nicht gefunden")
    r = {"status": j["status"], "fortschritt": j["fortschritt"], "anzahl": j["anzahl"]}
    if j["status"] == "fertig":
        r.update(url=f"/api/tv/v/{j['token']}.mp4", dauer=j["dauer"], groesse=j.get("groesse"))
    if j["status"] == "fehler":
        r["nachricht"] = j.get("nachricht")
    return r


@app.get("/api/tv/v/{datei}")
def tv_datei(datei: str):
    """Ohne PIN abrufbar, weil der Fernseher keine Anmeldung mitschicken kann - geschuetzt durch den
    unratbaren Dateinamen (24 Zufallsbytes); Dateien werden nach 12 Stunden geloescht."""
    if not TV_DATEI_RE.match(datei):
        raise HTTPException(404, "nicht gefunden")
    pfad = os.path.join(TV_DIR, datei)
    if not os.path.isfile(pfad):
        raise HTTPException(404, "nicht gefunden")
    return FileResponse(pfad, media_type="video/mp4", headers={"Cache-Control": "private, max-age=3600", "Accept-Ranges": "bytes"})


# --------------------------------------------------------------------------- TV-Empfaenger (Seite /tv/ laeuft im Browser des Fernsehers)
# Der Fernseher oeffnet /tv/?ziel=lg und fragt alle 2 s nach Befehlen. Die App schickt "start" (Fotos) oder
# "steuer" (pause/weiter/vor/zurueck/stopp). Kein Video, kein AirPlay, laeuft in jedem Browser.

# Fernseher/Geraete: RAHMEN_WEB_TV_ZIELE="lg=LG TV,shield=Shield" (Kennung=Anzeigename); "test" ist ein verstecktes Entwicklungsziel
TV_ZIELE = {k.strip(): v.strip() for k, _, v in (z.partition("=") for z in _liste("RAHMEN_WEB_TV_ZIELE", "lg=LG TV,shield=Shield")) if k.strip() and v.strip()}
TV_ZIELE.update(RAHMEN_ZIELE)
TV_ZIELE["test"] = "Test (nur Entwicklung)"
TV_VERSTECKT = {"test"}          # Ziele, die in der App nicht erscheinen (Automatiktests laufen auf /tv/?ziel=test statt auf dem echten Fernseher)
TV = {z: {"hb": 0.0, "seq": 0, "events": [], "aktiv": None, "tv_laeuft": False, "tv_name": "", "tv_musik": ""} for z in TV_ZIELE}

# --------------------------------------------------------------------------- Geraete-Verwaltung (Rahmen und Fernseher in der App anlegen/einstellen)
# Die Liste der Geraete steht in GERAETE_FILE. Solange es die Datei nicht gibt, gelten die Umgebungsvariablen (RAHMEN_WEB_RAHMEN_ZIELE, RAHMEN_WEB_TV_ZIELE,
# RAHMEN_WEB_FULLY_<ID>); die erste Aenderung in der App legt die Datei an, danach hat sie Vorrang. Einstellungen je Geraet ueberschreiben die
# allgemeinen Werte (RAHMEN_WEB_RAHMEN_SEK, ..._FUELLUNG, ..._ANZEIGE, ..._NACHT, ..._QUELLEN, ..._ZEITPLAN); leer = allgemeiner Wert.
ENV_RAHMEN = dict(RAHMEN_ZIELE)
ENV_TV = {k: v for k, v in TV_ZIELE.items() if k not in RAHMEN_ZIELE and k not in TV_VERSTECKT}
GERAETE_FILE = os.environ.get("RAHMEN_WEB_GERAETE_FILE", os.path.join(os.path.dirname(SHOWS_FILE), "rahmen_web_geraete.json"))
GERAETE = {}                                   # Kennung -> {"art": "rahmen"|"tv", "name": ..., optionale Einstellungen}
GERAETE_LOCK = threading.RLock()
REGISTER = {"aktiv": False}                    # True, sobald die Datei gilt (dann gibt es auch ohne Rahmen keinen Kiosk-Weg mehr)
FULLY = {}
FULLY_RE = re.compile(r"[A-Za-z0-9.-]+(:\d{1,5})?")
GERAET_ID_RE = re.compile(r"[a-z0-9]{1,20}")


def geraete_aus_env():
    g = {z: {"art": "tv", "name": n} for z, n in ENV_TV.items()}
    g.update({z: {"art": "rahmen", "name": n} for z, n in ENV_RAHMEN.items()})
    for z, e in g.items():
        h = os.environ.get(f"RAHMEN_WEB_FULLY_{z.upper()}", "").strip()
        if FULLY_RE.fullmatch(h):
            e["fully_host"] = h
            e["fully_pw"] = os.environ.get(f"RAHMEN_WEB_FULLY_PASSWORT_{z.upper()}") or os.environ.get("RAHMEN_WEB_FULLY_PASSWORT", "")
    return g


def geraete_laden():
    d = lies_json(GERAETE_FILE, None)
    if isinstance(d, dict) and isinstance(d.get("geraete"), list):
        g = {}
        for e in d["geraete"]:
            if isinstance(e, dict) and GERAET_ID_RE.fullmatch(str(e.get("id", ""))) and e.get("art") in ("rahmen", "tv") and e.get("name"):
                g[e["id"]] = {k: v for k, v in e.items() if k != "id"}
        return g, True
    return geraete_aus_env(), False


def geraete_speichern():
    schreibe_json(GERAETE_FILE, {"version": 1, "geraete": [{"id": z, **e} for z, e in GERAETE.items()]})
    REGISTER["aktiv"] = True


def geraete_anwenden(g):
    """Setzt Rahmen-/Fernseherlisten, Zustand und Fully-Zuordnung nach g. Die Verzeichnisse werden ersetzt (nicht veraendert), damit laufende Abfragen heil bleiben."""
    global RAHMEN_ZIELE, TV_ZIELE, TV, FULLY, PLAYER, GERAETE
    rahmen = {z: e["name"] for z, e in g.items() if e["art"] == "rahmen"}
    tv = {z: e["name"] for z, e in g.items() if e["art"] == "tv"}
    ziele = {**tv, **rahmen, "test": "Test (nur Entwicklung)"}
    fully = {}
    for z, e in g.items():
        h = str(e.get("fully_host") or "").strip()
        if FULLY_RE.fullmatch(h):
            fully[z] = {"host": h if ":" in h else h + ":2323", "pw": e.get("fully_pw") or os.environ.get("RAHMEN_WEB_FULLY_PASSWORT", "")}
    neu_tv = {z: TV.get(z) or {"hb": 0.0, "seq": 0, "events": [], "aktiv": None, "tv_laeuft": False, "tv_name": "", "tv_musik": ""} for z in ziele}
    GERAETE = g
    TV, TV_ZIELE, RAHMEN_ZIELE, FULLY = neu_tv, ziele, rahmen, fully
    PLAYER = next(iter(rahmen), None)


_g, _aktiv = geraete_laden()
REGISTER["aktiv"] = _aktiv
geraete_anwenden(_g)


# --------------------------------------------------------------------------- Einstellungen der Installation (in der App statt in der .env)
# Werte aus der App liegen in EINST_FILE und haben Vorrang vor den Umgebungsvariablen (die dann nur Startwerte sind). Sicherheitsrelevantes
# (Anmeldeart, vertrautes Netz, Proxys, Immich-Schluessel) bleibt bewusst in der Umgebung.
EINST_FILE = os.environ.get("RAHMEN_WEB_EINSTELLUNGEN_FILE", os.path.join(os.path.dirname(SHOWS_FILE), "rahmen_web_einstellungen.json"))
EINST = lies_json(EINST_FILE, {})
if not isinstance(EINST, dict):
    EINST = {}


def einst(key, default=None):
    v = EINST.get(key)
    return default if v in (None, "", [], {}) else v


def std_sek():
    return einst("sek", RAHMEN_SEK)


def std_fuellung_rahmen():
    return einst("fuellung_rahmen", RAHMEN_FUELLUNG)


def std_fuellung_tv():
    return einst("fuellung_tv", TV_FUELLUNG)


def std_anzeige():
    return einst("anzeige", RAHMEN_ANZEIGE)


def std_alarm_min():
    return einst("alarm_min", RAHMEN_ALARM_MIN) if "alarm_min" in EINST else RAHMEN_ALARM_MIN


def tv_url():
    return einst("tv_url", TV_URL)


def gwert(z, feld, standard=None):
    """Einstellung eines Geraets; leer/fehlend = allgemeiner Wert."""
    v = (GERAETE.get(z) or {}).get(feld)
    return standard if v in (None, "", []) else v


def rahmen_sek(z=None):
    return gwert(z or PLAYER, "sek", std_sek())


def rahmen_nacht(z=None):
    return gwert(z, "nacht", RAHMEN_NACHT) or ""


AKTIV_FILE = os.environ.get("RAHMEN_WEB_AKTIV_FILE", os.path.join(os.path.dirname(SHOWS_FILE), "rahmen_web_aktiv.json"))


def aktiv_speichern():
    """Welche Show laeuft auf welchem Geraet - damit ein Neustart/Update des Servers sie nicht vergisst (die Seite am Geraet spielt sie ja weiter)."""
    try:
        daten = {z: {"ev": t["aktiv"], "uid": (AKTIV_BESITZER.get(z) or (None, None))[1]} for z, t in TV.items() if t.get("aktiv")}
        os.makedirs(os.path.dirname(AKTIV_FILE), exist_ok=True)
        tmp = AKTIV_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(daten, f)
        os.replace(tmp, AKTIV_FILE)
    except (OSError, TypeError, ValueError) as e:
        H.log.warning("Laufende Show konnte nicht gespeichert werden: %s", e)


def aktiv_laden():
    try:
        with open(AKTIV_FILE) as f:
            daten = json.load(f)
    except (OSError, ValueError):
        return
    for z, eintrag in (daten or {}).items():
        ev = (eintrag or {}).get("ev")
        if z in TV and isinstance(ev, dict) and ev.get("typ") == "start":
            TV[z]["aktiv"] = ev
            TV[z]["seq"] = max(TV[z]["seq"], int(ev.get("seq", 0)))
            AKTIV_BESITZER[z] = (set(ev.get("ids") or []), eintrag.get("uid"))
            H.log.info("Laufende Show '%s' auf %s nach dem Start wiederhergestellt", ev.get("name"), z)


aktiv_laden()
# Hintergrundmusik: KEINE Musik im Lieferumfang. Eigene Dateien (mp3, ogg, m4a) in MUSIK_DIR/<sammlung>/ legen (oder bei aktiviertem
# Hochladen in der App hinzufuegen). Titel/Kuenstler kommen aus den Dateimarken (ID3), sonst aus dem Dateinamen; eine optionale
# info.json je Ordner ("name", "stuecke": [{"datei","titel","urheber","lizenz"}]) ueberschreibt das. Wird als Wiedergabeliste abgespielt.
MUSIK_DIR = os.environ.get("RAHMEN_WEB_MUSIK_DIR", "/data/musik")
MUSIK_UPLOAD = os.environ.get("RAHMEN_WEB_MUSIK_UPLOAD", "").strip().lower() in ("1", "true", "ja", "yes", "an")
MUSIK_MAX_MB = max(1, int(os.environ.get("RAHMEN_WEB_MUSIK_MAX_MB", "100")))              # je Datei
MUSIK_GESAMT_MB = max(1, int(os.environ.get("RAHMEN_WEB_MUSIK_GESAMT_MB", "2000")))       # ganze Sammlung
MUSIK_TYPEN = {".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".m4a": "audio/mp4"}            # was Fernseher-Browser abspielen koennen
KAT_RE = re.compile(r"^[a-z0-9_-]{1,30}$")
DATEI_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}\.(mp3|ogg|m4a)$")
MUSIK_CACHE = {"zeit": 0.0, "lib": {}}
MUSIK_TAGS = {}


def kat_slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode()).strip("-")[:30].strip("-")
    return s or "musik"


def schoener_name(dateiname):
    n = os.path.splitext(dateiname)[0].replace("_", " ").strip()
    n = re.sub(r"^\d{1,3}\s*[-.)]?\s+", "", n)                 # fuehrende Titelnummer weg
    return n or dateiname


def musik_marken(pfad):
    """(titel, kuenstler) aus den Dateimarken (ffprobe); Ergebnis wird je Datei/Aenderung zwischengespeichert."""
    try:
        st = os.stat(pfad)
    except OSError:
        return "", ""
    schluessel = f"{pfad}|{st.st_size}|{int(st.st_mtime)}"
    if not MUSIK_TAGS:
        MUSIK_TAGS.update(lies_json(os.path.join(H.STATE_DIR, "musik_marken.json"), {}))
    if schluessel in MUSIK_TAGS:
        return tuple(MUSIK_TAGS[schluessel])
    titel = kuenstler = ""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=title,artist", "-of", "json", pfad], capture_output=True, text=True, timeout=15)
        tags = {k.lower(): v for k, v in (json.loads(r.stdout or "{}").get("format", {}).get("tags") or {}).items()}
        titel, kuenstler = str(tags.get("title", ""))[:120], str(tags.get("artist", ""))[:120]
    except Exception:  # noqa: BLE001 - ohne ffprobe/Marken gilt der Dateiname
        pass
    MUSIK_TAGS[schluessel] = [titel, kuenstler]
    try:
        schreibe_json(os.path.join(H.STATE_DIR, "musik_marken.json"), MUSIK_TAGS)
    except OSError:
        pass
    return titel, kuenstler


def musik_scannen():
    lib, belegt = {}, set()
    try:
        eintraege = [(d, os.path.join(MUSIK_DIR, d)) for d in sorted(os.listdir(MUSIK_DIR)) if os.path.isdir(os.path.join(MUSIK_DIR, d)) and not d.startswith(".")]
        eintraege.append(("", MUSIK_DIR))                           # Dateien direkt im Musikordner: Sammlung "Eigene Musik"
    except OSError:
        return {}
    for ordner, pfad in eintraege:
        try:
            dateien = sorted(f for f in os.listdir(pfad) if os.path.splitext(f)[1].lower() in MUSIK_TYPEN and not f.startswith(".") and os.path.isfile(os.path.join(pfad, f)))
        except OSError:
            continue
        if not dateien:
            continue
        kat = kat_slug(ordner) if ordner else "eigene"
        while kat in belegt:
            kat = (kat[:26] + "-2") if not kat.endswith("-2") else kat + "x"
        belegt.add(kat)
        info = lies_json(os.path.join(pfad, "info.json"), {}) if ordner else {}
        meta = {st.get("datei"): st for st in info.get("stuecke", [])}
        stuecke = []
        for f in dateien:
            ext = os.path.splitext(f)[1].lower()
            m = meta.get(f) or {}
            rel = os.path.join(ordner, f) if ordner else f
            datei = f if (m and DATEI_RE.match(f)) else hashlib.sha1(f"{kat}/{f}".encode()).hexdigest()[:10] + ext
            titel, kuenstler = (m.get("titel"), m.get("urheber")) if m.get("titel") else musik_marken(os.path.join(pfad, f))
            stuecke.append({"datei": datei, "pfad": rel, "titel": titel or schoener_name(f), "urheber": (m.get("urheber") or kuenstler or ""), "lizenz": m.get("lizenz", ""),
                            "kat": ""})
        lib[kat] = {"name": info.get("name") or (schoener_name(ordner) if ordner else "Eigene Musik"), "ordner": ordner, "stuecke": stuecke}
    return lib


def musik_bibliothek():
    jetzt = time.time()
    if jetzt - MUSIK_CACHE["zeit"] > 15:
        MUSIK_CACHE.update(zeit=jetzt, lib=musik_scannen())
    lib = MUSIK_CACHE["lib"]
    if len(lib) > 1:                                  # Mischung ueber alle Sammlungen (Stuecke tragen ihre Sammlung in "kat")
        lib = {"alle": {"name": "🎲 Alles bunt gemischt", "stuecke": [dict(st, kat=k) for k, v in lib.items() for st in v["stuecke"]]}, **lib}
    return lib


def musik_neu_einlesen():
    MUSIK_CACHE["zeit"] = 0.0


TV_EV = threading.Lock()


def tv_ziel(z):
    if z not in TV_ZIELE:
        raise HTTPException(400, "Unbekanntes Ziel")
    return TV[z]


TAGE = {"mo": 0, "di": 1, "mi": 2, "do": 3, "fr": 4, "sa": 5, "so": 6, "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _tage_lesen(text):
    """'Mo-Fr' | 'Sa,So' | 'taeglich' -> Menge von Wochentagen (0 = Montag); None bei Unsinn."""
    text = text.strip().lower().replace("ä", "ae")
    if text in ("taeglich", "daily", "alle", "*"):
        return set(range(7))
    tage = set()
    for teil in text.split(","):
        teil = teil.strip()
        if "-" in teil:
            a, _, b = teil.partition("-")
            if a.strip() not in TAGE or b.strip() not in TAGE:
                return None
            i, j = TAGE[a.strip()], TAGE[b.strip()]
            while True:
                tage.add(i)
                if i == j:
                    break
                i = (i + 1) % 7
        elif teil in TAGE:
            tage.add(TAGE[teil])
        else:
            return None
    return tage or None


def zeitplan_lesen(text):
    """'Mo-Fr 18:00-22:00 = <quellen>; Sa,So 08:00-20:00 = *' -> [(tage, von_minuten, bis_minuten, [quellen])]. Unlesbare Eintraege werden uebersprungen."""
    regeln = []
    for eintrag in (text or "").split(";"):
        links, _, rechts = eintrag.partition("=")
        m = re.fullmatch(r"\s*(?P<t>[^\d]+?)\s+(?P<v>\d{1,2}):(?P<vm>\d{2})\s*-\s*(?P<b>\d{1,2}):(?P<bm>\d{2})\s*", links)
        quellen = [x.strip() for x in rechts.split(",") if x.strip()]
        tage = _tage_lesen(m.group("t")) if m else None
        if not m or not tage or not quellen:
            if eintrag.strip():
                H.log.warning("Zeitplan: Eintrag nicht lesbar: %r", eintrag.strip())
            continue
        regeln.append((tage, int(m.group("v")) * 60 + int(m.group("vm")), int(m.group("b")) * 60 + int(m.group("bm")), quellen))
    return regeln


def zeitplan_quellen(regeln, jetzt):
    """Quellen der ersten passenden Regel (Bereiche ueber Mitternacht zaehlen zum Starttag) oder None."""
    tag, minute = jetzt.weekday(), jetzt.hour * 60 + jetzt.minute
    for tage, von, bis, quellen in regeln:
        if von <= bis:
            ok = tag in tage and von <= minute < bis
        else:
            ok = (tag in tage and minute >= von) or (((tag - 1) % 7) in tage and minute < bis)
        if ok:
            return quellen
    return None


def _je_rahmen(basis, ziel):
    """Einstellung fuer einen bestimmten Rahmen (RAHMEN_WEB_..._<ZIEL>), sonst die allgemeine."""
    feld = {"RAHMEN_WEB_RAHMEN_ZEITPLAN": "zeitplan", "RAHMEN_WEB_RAHMEN_QUELLEN": "quellen"}.get(basis)
    if feld and gwert(ziel, feld):
        return gwert(ziel, feld)
    if ziel and re.fullmatch(r"[a-z0-9]+", ziel):
        wert = os.environ.get(f"{basis}_{ziel.upper()}")
        if wert is not None and wert.strip():
            return wert
    return os.environ.get(basis, "")


def quelle_lesen(e):
    """Eine Quelle ('<album-id>:70', 'neu14', 'heute', '*', 'person=Anna+Ben:60') -> Beschreibung oder None bei Unsinn."""
    if e.lower().startswith("person="):                              # person=Anna Muster  |  person=oma:60  |  person=Anna+Ben (beide zusammen)
        rest = e[7:]
        teil, sep, gw = rest.rpartition(":")
        if not sep or not re.fullmatch(r"\d+(\.\d+)?", gw):
            teil, gw = rest, ""
        namen = [n.strip() for n in teil.split("+") if n.strip()]
        return {"typ": "person", "namen": namen, "gewicht": float(gw) if gw else 1.0} if namen else None
    name, _, gw = e.partition(":")
    try:
        gewicht = max(0.0, float(gw)) if gw else 1.0
    except ValueError:
        return None
    if name == "*":
        return {"typ": "alle", "gewicht": gewicht}
    if re.fullmatch(r"neu\d{1,3}", name):
        return {"typ": "neu", "tage": int(name[3:]), "gewicht": gewicht}
    if re.fullmatch(r"heute\d{0,2}", name):
        return {"typ": "heute", "tage": int(name[5:] or 2), "gewicht": gewicht}
    if re.fullmatch(r"[0-9a-f-]{36}", name):
        return {"typ": "album", "id": name, "gewicht": gewicht}
    return None


def rahmen_quellen(ziel=None, jetzt=None):
    """[{'typ': 'album'|'neu'|'heute'|'alle'|'alben', 'gewicht': float, ...}] aus der Konfiguration (je Rahmen und nach Zeitplan)."""
    roh = None
    plan = zeitplan_lesen(_je_rahmen("RAHMEN_WEB_RAHMEN_ZEITPLAN", ziel))
    if plan:
        roh = zeitplan_quellen(plan, jetzt or datetime.datetime.now())
    if roh is None:
        eigene = ""
        if ziel and re.fullmatch(r"[a-z0-9]+", ziel):
            eigene = gwert(ziel, "quellen") or os.environ.get(f"RAHMEN_WEB_RAHMEN_QUELLEN_{ziel.upper()}", "")
        roh = [x.strip() for x in eigene.split(",") if x.strip()] if eigene.strip() else RAHMEN_QUELLEN_ROH
    quellen = [q for q in (quelle_lesen(e) for e in roh) if q]
    quellen = [q for q in quellen if q["gewicht"] > 0]
    if not quellen:
        quellen = [{"typ": "alben", "gewicht": 1.0}] if (RAHMEN_ALBEN or RAHMEN_MARKER) else [{"typ": "alle", "gewicht": 1.0}]
    return quellen


PERSONEN_CACHE = {"t": 0.0, "named": [], "alias": {}}


def person_ids(namen):
    """Immich-Personen-IDs zu Namen oder Spitznamen (RAHMEN_WEB_ALIASE); unbekannte Namen -> None."""
    if time.time() - PERSONEN_CACHE["t"] > 600:
        try:
            PERSONEN_CACHE["named"], PERSONEN_CACHE["alias"] = H.lade_personen()
            PERSONEN_CACHE["t"] = time.time()
        except Exception as e:  # noqa: BLE001 - mit dem letzten Stand weiterarbeiten
            H.log.warning("Personen laden: %s", e)
    ids = []
    for name in namen:
        ziel = H.norm(PERSONEN_CACHE["alias"].get(H.norm(name), name))
        treffer = [i for n, i in PERSONEN_CACHE["named"] if H.norm(n) == ziel] or [i for n, i in PERSONEN_CACHE["named"] if H.norm(n).startswith(ziel)]
        if not treffer:
            H.log.warning("Rahmen-Quelle person=%s: unbekannt in Immich", name)
            return None
        ids.append(treffer[0])
    return ids


HEUTE_CACHE = {"key": None, "ids": []}


def heute_ids(tage, heute=None):
    """Fotos von 'heute vor 1..20 Jahren' (+/- tage), einmal je Tag ermittelt."""
    heute = heute or datetime.date.today()
    if HEUTE_CACHE["key"] == (heute, tage):
        return HEUTE_CACHE["ids"]
    ids = []
    for jahr in range(heute.year - 1, heute.year - 21, -1):
        try:
            mitte = heute.replace(year=jahr)
        except ValueError:                                              # 29. Februar
            mitte = datetime.date(jahr, 2, 28)
        von = datetime.datetime.combine(mitte - datetime.timedelta(days=tage), datetime.time.min)
        bis = datetime.datetime.combine(mitte + datetime.timedelta(days=tage + 1), datetime.time.min)
        body = {"size": 30, "type": "IMAGE", "withExif": True, "visibility": "timeline",
                "takenAfter": von.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "takenBefore": bis.strftime("%Y-%m-%dT%H:%M:%S.000Z")}
        try:
            items = H.api("POST", "/search/random", body) or []
        except Exception as e:  # noqa: BLE001 - ein Jahr ohne Antwort stoert die anderen nicht
            H.log.warning("Heute-Quelle %s: %s", jahr, e)
            continue
        ids += [a["id"] for a in items if not H.ist_screenshot(a)]
    HEUTE_CACHE.update(key=(heute, tage), ids=ids)
    return ids


MARKER_CACHE = {"t": 0.0, "v": ([], [])}


def marker_alben():
    """(markierte Alben, exklusiv markierte Alben) - Beschreibung per Immich lesen, 2 Minuten zwischengespeichert; leere Alben zaehlen nicht."""
    if time.time() - MARKER_CACHE["t"] < 120:
        return MARKER_CACHE["v"]
    try:
        alben = H.api("GET", "/albums") or []
    except Exception as e:  # noqa: BLE001 - ohne Albumliste weiter mit dem letzten Stand
        H.log.warning("Marker-Alben: %s", e)
        return MARKER_CACHE["v"]
    normal, nur = [], []
    for a in alben:
        beschr = a.get("description") or ""
        if a["id"] in RAHMEN_ALBEN or not a.get("assetCount") or not MARKER_RE.search(beschr):
            continue
        (nur if MARKER_NUR_RE.search(beschr) else normal).append(a["id"])
    MARKER_CACHE.update(t=time.time(), v=(sorted(normal), sorted(nur)))
    return MARKER_CACHE["v"]


def rahmen_alben():
    """(Album-IDs des Dauerprogramms, exklusiv?)"""
    if not RAHMEN_MARKER:
        return RAHMEN_ALBEN, False
    normal, nur = marker_alben()
    return (nur, True) if nur else (RAHMEN_ALBEN + normal, False)


EXKLUSIV_ZEIGER = {}


def rahmen_exklusiv(ids, n, ziel=None):
    """Exklusiv-Modus (#nurrahmen): nur diese Alben; Reihenfolge wie bei Wunsch-Shows (alt/neu/zufall), laufend weiter statt immer von vorn."""
    reihe = reihe_von(ziel)
    basis = {"type": "IMAGE", "albumIds": ids, "visibility": "timeline", "withExif": True}
    if reihe == "zufall":
        items = H.api("POST", "/search/random", {**basis, "size": max(10, n * 3)}) or []
        ergebnis = [a["id"] for a in items if not H.ist_screenshot(a)][:n]
        random.shuffle(ergebnis)
        return ergebnis
    schluessel = (tuple(ids), reihe)
    seite = EXKLUSIV_ZEIGER.get(schluessel, 1)
    for _ in range(2):
        antwort = (H.api("POST", "/search/metadata", {**basis, "order": "desc" if reihe == "neu" else "asc", "size": n, "page": seite}) or {}).get("assets") or {}
        items = antwort.get("items") or []
        if items:
            break
        seite = 1                                                      # Ende erreicht: wieder von vorn
    EXKLUSIV_ZEIGER[schluessel] = int(antwort["nextPage"]) if items and antwort.get("nextPage") else 1
    return [a["id"] for a in items if not H.ist_screenshot(a)]


def verteilen(gewichte, n):
    """Teilt n Plaetze nach Gewicht auf (groesster Rest); Summe ist immer n."""
    summe = sum(gewichte) or 1.0
    exakt = [g / summe * n for g in gewichte]
    anzahl = [int(x) for x in exakt]
    for i in sorted(range(len(exakt)), key=lambda i: exakt[i] - anzahl[i], reverse=True)[: n - sum(anzahl)]:
        anzahl[i] += 1
    return anzahl


AMBIENT_GESEHEN = collections.deque(maxlen=600)          # zuletzt gezeigte Fotos des Dauerprogramms: kommen nicht gleich wieder
AMBIENT_PRO_ZIEL = {}


def rahmen_auswahl(n, ziel=None):
    alben_ids, exklusiv = rahmen_alben()
    if exklusiv:
        try:
            ergebnis = rahmen_exklusiv(alben_ids, n, ziel)
        except Exception as e:  # noqa: BLE001 - Dauerprogramm faellt auf die normalen Quellen zurueck
            H.log.warning("Exklusiv-Album: %s", e)
            ergebnis = []
        if ergebnis:
            return ergebnis
    quellen = rahmen_quellen(ziel)
    gedaechtnis = AMBIENT_GESEHEN if ziel is None else AMBIENT_PRO_ZIEL.setdefault(ziel, collections.deque(maxlen=600))
    gesehen = set(gedaechtnis)
    ergebnis, bereits, reste = [], set(), []
    for q, k in zip(quellen, verteilen([q["gewicht"] for q in quellen], n)):
        if k <= 0:
            continue
        if q["typ"] == "heute":
            kandidaten = list(heute_ids(q["tage"]))
            random.shuffle(kandidaten)
            frisch = [i for i in kandidaten if i not in bereits]
            neu = [i for i in frisch if i not in gesehen] or frisch
            for i in neu[:k]:
                ergebnis.append(i)
                bereits.add(i)
            reste.append((q["gewicht"], neu[k:]))
            continue
        body = {"size": max(10, k * 3), "type": "IMAGE", "withExif": True, "visibility": "timeline"}
        if q["typ"] == "album":
            body["albumIds"] = [q["id"]]
        elif q["typ"] == "alben":
            body["albumIds"] = alben_ids or RAHMEN_ALBEN
        elif q["typ"] == "person":
            pids = person_ids(q["namen"])
            if not pids:
                continue
            body["personIds"] = pids
        elif q["typ"] == "neu":
            body["createdAfter"] = (datetime.datetime.utcnow() - datetime.timedelta(days=q["tage"])).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        try:
            items = H.api("POST", "/search/random", body) or []
        except Exception as e:  # noqa: BLE001 - eine kaputte Quelle (z. B. geloeschtes Album) legt das Dauerprogramm nicht lahm
            H.log.warning("Rahmen-Quelle %s: %s", q, e)
            continue
        frisch = [a["id"] for a in items if not H.ist_screenshot(a) and a["id"] not in bereits]
        neu = [i for i in frisch if i not in gesehen] or frisch          # lieber ein Wiederholer als eine leere Quelle
        for i in neu[:k]:
            ergebnis.append(i)
            bereits.add(i)
        reste.append((q["gewicht"], neu[k:]))
    if len(ergebnis) < n:                                              # eine Quelle hat zu wenig (kleines Album): Rest aus den anderen
        for _, uebrig in sorted(reste, key=lambda r: -r[0]):
            for i in uebrig:
                if len(ergebnis) >= n:
                    break
                if i not in bereits:
                    ergebnis.append(i)
                    bereits.add(i)
    random.shuffle(ergebnis)
    gedaechtnis.extend(ergebnis)
    return ergebnis


@app.get("/api/rahmen/zufall")
def rahmen_zufall(n: int = 40, ziel: str = "", _=Depends(geraet)):
    """Dauerprogramm des Rahmens: zufaellige Fotos nach Quellen und Gewicht (ohne Screenshots, ohne kuerzlich gezeigte); je Rahmen und nach Zeitplan."""
    return {"ids": rahmen_auswahl(max(5, min(n, 100)), ziel if ziel in RAHMEN_ZIELE else None)}


BILDINFO = {}


@app.get("/api/bildinfo/{asset_id}")
def bildinfo(asset_id: str, lang: str = "de", _=Depends(geraet)):
    """Datum, Uhrzeit und Ort eines Fotos fuer die Bildunterschrift am Rahmen."""
    if not ID_RE.match(asset_id):
        raise HTTPException(400, "ungueltig")
    if asset_id in BILDINFO:
        a = BILDINFO[asset_id]
    else:
        key = None if UID_CTX.get() else geraete_schluessel(asset_id)
        tok = H.KEY_CTX.set(key) if key else None
        try:
            a = H.api("GET", f"/assets/{asset_id}") or {}
        except Exception:  # noqa: BLE001 - Unterschrift ist Zierde
            a = {}
        finally:
            if tok is not None:
                H.KEY_CTX.reset(tok)
        if len(BILDINFO) > 500:
            BILDINFO.clear()
        BILDINFO[asset_id] = a
    exif = a.get("exifInfo") or {}
    land = exif.get("country") or ""
    if lang == "de":
        land = LAND_DE.get(land, land)
    ort = ", ".join(x for x in (exif.get("city"), land) if x)
    wann = a.get("localDateTime") or a.get("fileCreatedAt") or ""
    return {"datum": wann[:10], "zeit": wann[11:16] if re.fullmatch(r"\d\d:\d\d", wann[11:16]) else "", "ort": ort}


@app.get("/api/rahmen/status")
def rahmen_status(_=Depends(geraet)):
    """Zustand der Rahmen-Player fuer Ueberwachung (Home Assistant, Uptime Kuma ...)."""
    jetzt = time.time()
    return {"version": VERSION, "rahmen": [{"id": z, "name": n, "online": jetzt - TV[z]["hb"] < 10, "zuletzt_vor_s": int(jetzt - TV[z]["hb"]) if TV[z]["hb"] else None,
            "spielt": TV[z]["tv_name"] if TV[z]["tv_laeuft"] else None, "dauerprogramm": TV[z].get("ambient", False), "bild_alter_s": TV[z].get("bild_alter")}
            for z, n in RAHMEN_ZIELE.items()]}


# --------------------------------------------------------------------------- Zusatzanzeige am Rahmen: Wetter und Termine (beides optional)
# Wetter: Open-Meteo (kostenlos, ohne Schluessel). Der SERVER fragt ab (Koordinaten verlassen nur ihn, nicht die Geraete).
WETTER_ORT = None
_m = re.fullmatch(r"\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*", os.environ.get("RAHMEN_WEB_WETTER_ORT", ""))
if _m:
    WETTER_ORT = (float(_m.group(1)), float(_m.group(2)))
KALENDER_URL = os.environ.get("RAHMEN_WEB_KALENDER_URL", "").strip()
if not re.match(r"^https?://", KALENDER_URL):
    KALENDER_URL = ""
def wetter_ort():
    w = EINST.get("wetter")
    return (float(w["lat"]), float(w["lon"])) if isinstance(w, dict) and "lat" in w and "lon" in w else WETTER_ORT


def kalender_url():
    return einst("kalender_url", KALENDER_URL)


def zusatz_liste():
    return [k for k in _liste("RAHMEN_WEB_RAHMEN_ZUSATZ", "wetter,kalender") if (k == "wetter" and wetter_ort()) or (k == "kalender" and kalender_url())]
ZUSATZ_CACHE = {}


def http_text(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "immich-showcase"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(2_000_000).decode("utf-8", "replace")


WETTER_SYMBOLE = [((0,), "☀️"), ((1, 2), "🌤️"), ((3,), "☁️"), ((45, 48), "🌫️"), ((51, 53, 55, 56, 57), "🌦️"), ((61, 63, 65, 66, 67), "🌧️"),
                  ((71, 73, 75, 77), "🌨️"), ((80, 81, 82), "🌦️"), ((85, 86), "🌨️"), ((95, 96, 99), "⛈️")]


def wetter_symbol(code):
    return next((sym for codes, sym in WETTER_SYMBOLE if code in codes), "🌡️")


def zusatz_gecacht(name, sekunden, holen):
    eintrag = ZUSATZ_CACHE.get(name)
    if eintrag and time.time() - eintrag[0] < sekunden:
        return eintrag[1]
    try:
        wert = holen()
    except Exception as e:  # noqa: BLE001 - ohne Zusatz laeuft der Rahmen trotzdem; letzter Stand bleibt
        H.log.warning("Zusatzanzeige %s: %s", name, e)
        return eintrag[1] if eintrag else None
    ZUSATZ_CACHE[name] = (time.time(), wert)
    return wert


def wetter_holen():
    lat, lon = wetter_ort()
    d = json.loads(http_text(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&timezone=auto"))
    cur = d["current"]
    return {"temp": round(float(cur["temperature_2m"])), "symbol": wetter_symbol(int(cur["weather_code"]))}


def _ics_zeile_entfalten(text):
    zeilen = []
    for z in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if z[:1] in (" ", "\t") and zeilen:
            zeilen[-1] += z[1:]
        else:
            zeilen.append(z)
    return zeilen


def _ics_zeit(wert, params):
    """-> (datum, uhrzeit|None) in Ortszeit. 'YYYYMMDD' = ganztaegig, '...Z' = UTC (wird umgerechnet), sonst Ortszeit."""
    wert = wert.strip()
    if re.fullmatch(r"\d{8}", wert):
        return datetime.date(int(wert[:4]), int(wert[4:6]), int(wert[6:])), None
    m = re.fullmatch(r"(\d{8})T(\d{2})(\d{2})(\d{2})?(Z?)", wert)
    if not m:
        return None
    dt = datetime.datetime(int(m.group(1)[:4]), int(m.group(1)[4:6]), int(m.group(1)[6:]), int(m.group(2)), int(m.group(3)))
    if m.group(5) == "Z":
        dt = dt.replace(tzinfo=datetime.timezone.utc).astimezone().replace(tzinfo=None)
    return dt.date(), dt.time()


def ics_termine(text, heute, tage=2, maximum=4):
    """Termine von heute (und morgen ...) aus einer iCalendar-Datei. Einfache Wiederholungen (taeglich, woechentlich, jaehrlich) werden verstanden."""
    fenster = [heute + datetime.timedelta(days=i) for i in range(tage)]
    ergebnis = []
    ereignis = None
    for zeile in _ics_zeile_entfalten(text):
        if zeile == "BEGIN:VEVENT":
            ereignis = {}
        elif zeile == "END:VEVENT" and ereignis is not None:
            start = ereignis.get("DTSTART")
            if start:
                beginn = _ics_zeit(start[1], start[0])
                if beginn:
                    d0, uhr = beginn
                    regel = dict(p.split("=", 1) for p in (ereignis.get("RRULE", ("", ""))[1]).split(";") if "=" in p)
                    for tag in fenster:
                        if tag < d0:
                            continue
                        frq, intervall = regel.get("FREQ"), int(regel.get("INTERVAL", "1") or 1)
                        if not frq:
                            treffer = tag == d0
                        elif frq == "DAILY":
                            treffer = (tag - d0).days % intervall == 0
                        elif frq == "WEEKLY":
                            tage_liste = [{"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}.get(x[-2:]) for x in regel.get("BYDAY", "").split(",") if x] or [d0.weekday()]
                            treffer = tag.weekday() in tage_liste and ((tag - d0).days // 7) % intervall == 0
                        elif frq == "YEARLY":
                            treffer = (tag.month, tag.day) == (d0.month, d0.day)
                        else:
                            treffer = False
                        ende = regel.get("UNTIL")
                        if treffer and ende:
                            bis = _ics_zeit(ende, {})
                            treffer = not bis or tag <= bis[0]
                        if treffer:
                            titel = (ereignis.get("SUMMARY", ("", ""))[1]).replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").strip()
                            ergebnis.append({"tag": "heute" if tag == heute else "morgen" if tag == heute + datetime.timedelta(days=1) else tag.isoformat(),
                                             "zeit": uhr.strftime("%H:%M") if uhr else "", "titel": titel[:60], "_k": (tag, uhr or datetime.time.min)})
            ereignis = None
        elif ereignis is not None and ":" in zeile:
            kopf, _, wert = zeile.partition(":")
            name, _, params = kopf.partition(";")
            ereignis[name.upper()] = (params, wert)
    ergebnis.sort(key=lambda e: e["_k"])
    return [{k: v for k, v in e.items() if k != "_k"} for e in ergebnis if e["titel"]][:maximum]


def kalender_holen():
    return ics_termine(http_text(kalender_url()), datetime.date.today())


@app.get("/api/rahmen/zusatz")
def rahmen_zusatz(_=Depends(geraet)):
    """Wetter und Termine fuer die Zusatzanzeige am Rahmen (nur was eingerichtet ist)."""
    out = {}
    zusatz = zusatz_liste()
    if "wetter" in zusatz:
        w = zusatz_gecacht("wetter", 900, wetter_holen)
        if w:
            out["wetter"] = w
    if "kalender" in zusatz:
        t = zusatz_gecacht("kalender", 600, kalender_holen)
        if t is not None:
            out["termine"] = t
    return out


# --------------------------------------------------------------------------- Geraete: Uebersicht und Kopplung per Code
# Fully Kiosk (Android-Tablet) fernsteuern: Bildschirm zur Nachtruhe aus/an, Akku melden. RAHMEN_WEB_FULLY_<KENNUNG>=<Adresse[:Port]> und
# RAHMEN_WEB_FULLY_PASSWORT[_<KENNUNG>] (Fully: Einstellungen -> Remote Admin -> aktivieren, Passwort setzen)
FULLY_HELLIGKEIT = int(os.environ["RAHMEN_WEB_FULLY_HELLIGKEIT"]) if re.fullmatch(r"\d{1,3}", os.environ.get("RAHMEN_WEB_FULLY_HELLIGKEIT", "")) and int(os.environ["RAHMEN_WEB_FULLY_HELLIGKEIT"]) <= 255 else None
FULLY_AKKU_MIN = int(os.environ.get("RAHMEN_WEB_FULLY_AKKU_MIN", "20") or 20)
FULLY_STATE = {}


def fully_get(url, timeout=6):
    return http_text(url, timeout)


def fully_befehl(z, cmd, **params):
    f = FULLY[z]
    return fully_get(f"http://{f['host']}/?" + urllib.parse.urlencode({"cmd": cmd, "password": f["pw"], "type": "json", **params}))


def in_nacht(jetzt=None, ziel=None):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", rahmen_nacht(ziel) or "")
    if not m:
        return False
    von, bis = int(m[1]) * 60 + int(m[2]), int(m[3]) * 60 + int(m[4])
    jetzt = jetzt or datetime.datetime.now()
    minute = jetzt.hour * 60 + jetzt.minute
    return von <= minute < bis if von <= bis else (minute >= von or minute < bis)


def fully_bildschirm(z, an):
    fully_befehl(z, "screenOn" if an else "screenOff")
    if an and FULLY_HELLIGKEIT is not None:
        fully_befehl(z, "setStringSetting", key="screenBrightness", value=str(FULLY_HELLIGKEIT))
    FULLY_STATE.setdefault(z, {})["bildschirm"] = "an" if an else "aus"


def akku_melden(z, akku, laedt):
    """Merkt den Akkustand eines Tablets und warnt einmal, wenn er niedrig ist und das Tablet nicht laedt (egal ob es ihn selbst meldet oder ueber Fully abgefragt wurde)."""
    st = FULLY_STATE.setdefault(z, {})
    st["akku"], st["laedt"] = akku, laedt
    if akku <= FULLY_AKKU_MIN and not laedt and not st.get("akku_gemeldet"):
        st["akku_gemeldet"] = True
        threading.Thread(target=pushover, args=(f"{TV_ZIELE.get(z, z)}: Akku niedrig", f"Akku {akku} % und das Tablet laedt nicht.", 1), daemon=True).start()
    elif laedt or akku >= FULLY_AKKU_MIN + 10:
        st["akku_gemeldet"] = False


def meldet_selbst(z):
    """Das Tablet steuert sich selbst (Fully-JavaScript-Schnittstelle), solange es sich so meldet."""
    t = TV.get(z) or {}
    return bool(t.get("fully_js") and time.time() - t.get("hb", 0) < 60)


def fully_wache_pruefen(jetzt=None):
    """Einmal pro Minute: Nachtruhe (Bildschirm aus/an nur beim Wechsel, damit Handeingriffe nicht ueberstimmt werden) und Akku (alle 5 Minuten)."""
    for z in FULLY:
        st = FULLY_STATE.setdefault(z, {})
        if rahmen_nacht(z) and not meldet_selbst(z):               # meldet sich das Tablet selbst, schaltet es den Bildschirm selbst
            soll = "aus" if in_nacht(jetzt, z) else "an"
            if st.get("soll") != soll:
                try:
                    fully_bildschirm(z, soll == "an")
                    st["soll"] = soll
                except Exception as e:  # noqa: BLE001 - naechste Minute noch einmal
                    H.log.warning("Fully %s: %s", z, e)
        if time.time() - st.get("info_t", 0) > 300:
            st["info_t"] = time.time()
            try:
                info = json.loads(fully_befehl(z, "deviceInfo"))
                st["akku"], st["laedt"] = int(info.get("batteryLevel")), bool(info.get("isPlugged"))
            except Exception as e:  # noqa: BLE001
                H.log.warning("Fully %s Akku: %s", z, e)
                continue
            akku_melden(z, st["akku"], st["laedt"])


def fully_wache_schleife():
    while True:
        try:
            fully_wache_pruefen()
        except Exception as e:  # noqa: BLE001
            H.log.warning("Fully-Wache: %s", e)
        time.sleep(60)


@app.on_event("startup")
def fully_wache_starten():
    threading.Thread(target=fully_wache_schleife, daemon=True).start()


def geraete_liste():
    jetzt = time.time()
    liste = []
    for z, n in TV_ZIELE.items():
        if z in TV_VERSTECKT:
            continue
        d = TV[z]
        online = jetzt - d["hb"] < 10
        spielt = (d["tv_name"] or "Wiedergabe") if (online and d["tv_laeuft"] and not d.get("ambient")) else None
        dauer = bool(online and d.get("ambient"))
        st = FULLY_STATE.get(z, {})
        liste.append({"id": z, "name": n, "art": "rahmen" if z in RAHMEN_ZIELE else "tv", "online": online,
                      "zustand": "offline" if not online else "spielt" if spielt else "dauerprogramm" if dauer else "bereit",
                      "zuletzt_vor_s": int(jetzt - d["hb"]) if d["hb"] else None, "spielt": spielt, "dauerprogramm": dauer,
                      "bild_alter_s": d.get("bild_alter") if online else None,
                      "fully": z in FULLY, "selbst": meldet_selbst(z), "bildschirm": st.get("bildschirm"), "akku": st.get("akku"), "laedt": st.get("laedt")})
    return liste


@app.get("/api/geraete")
def geraete_uebersicht(_=Depends(anmeldung)):
    """Alle Fernseher und Rahmen mit Zustand (fuer die Geraete-Ansicht in der App)."""
    return {"geraete": geraete_liste()}


# --------------------------------------------------------------------------- Verwaltung: Rahmen und Fernseher anlegen, einstellen, loeschen
FUELLUNGEN = ("balken", "unscharf", "zuschnitt")
NACHT_RE = re.compile(r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})")


def geraet_ansicht(z, e):
    t = TV.get(z) or {}
    return {"selbst": meldet_selbst(z), "ip": t.get("ip") or "", "akku": (FULLY_STATE.get(z) or {}).get("akku"), "id": z, "art": e["art"], "name": e["name"], "sek": e.get("sek"), "fuellung": e.get("fuellung") or "", "anzeige": e.get("anzeige") or [],
            "nacht": e.get("nacht") or "", "quellen": e.get("quellen") or "", "zeitplan": e.get("zeitplan") or "",
            "fully_host": e.get("fully_host") or "", "fully_pw_gesetzt": bool(e.get("fully_pw"))}


def geraet_kennung(name):
    t = str(name).lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    t = re.sub(r"[^a-z0-9]", "", t)[:16] or "geraet"
    k, n = t, 2
    while k in GERAETE or k in TV_ZIELE:
        k, n = f"{t}{n}", n + 1
    return k


def geraet_felder(daten, art):
    """Prueft die Eingaben; Rueckgabe: (zu setzen, zu entfernen). Leere Werte entfernen die Einstellung (dann gilt der allgemeine Wert)."""
    setzen, weg = {}, []
    if "name" in daten:
        setzen["name"] = name_pruefen(daten["name"])
    if "fuellung" in daten:
        v = str(daten["fuellung"] or "")
        if v and v not in FUELLUNGEN:
            raise HTTPException(400, "Unbekannte Hintergrund-Füllung")
        (setzen.__setitem__("fuellung", v) if v else weg.append("fuellung"))
    if art == "rahmen":
        if "sek" in daten:
            if daten["sek"] in (None, ""):
                weg.append("sek")
            else:
                try:
                    setzen["sek"] = max(3, min(int(daten["sek"]), 120))
                except (TypeError, ValueError):
                    raise HTTPException(400, "Sekunden pro Foto: bitte eine Zahl zwischen 3 und 120")
        if "anzeige" in daten:
            a = daten["anzeige"] if isinstance(daten["anzeige"], list) else []
            if any(x not in ("datum", "zeit", "ort") for x in a):
                raise HTTPException(400, "Unbekannte Bildunterschrift")
            (setzen.__setitem__("anzeige", [x for x in ("datum", "zeit", "ort") if x in a]) if a else weg.append("anzeige"))
        if "nacht" in daten:
            v = str(daten["nacht"] or "").strip()
            m = NACHT_RE.fullmatch(v)
            if v and not (m and int(m[1]) < 24 and int(m[3]) < 24 and int(m[2]) < 60 and int(m[4]) < 60):
                raise HTTPException(400, "Nachtruhe bitte als von-bis, z. B. 22:00-06:30")
            (setzen.__setitem__("nacht", v) if v else weg.append("nacht"))
        if "quellen" in daten:
            v = str(daten["quellen"] or "").strip()
            for tok in [x.strip() for x in v.split(",") if x.strip()]:
                if not quelle_lesen(tok):
                    raise HTTPException(400, f"Unbekannte Quelle: {tok}")
            (setzen.__setitem__("quellen", v) if v else weg.append("quellen"))
        if "zeitplan" in daten:
            v = str(daten["zeitplan"] or "").strip()
            if v and len(zeitplan_lesen(v)) != len([x for x in v.split(";") if x.strip()]):
                raise HTTPException(400, "Zeitplan nicht lesbar – Beispiel: Mo-Fr 18:00-22:00 = neu14:70, *:30; Sa,So 08:00-20:00 = *")
            (setzen.__setitem__("zeitplan", v) if v else weg.append("zeitplan"))
    if "fully_host" in daten:
        v = str(daten["fully_host"] or "").strip()
        if v and not FULLY_RE.fullmatch(v):
            raise HTTPException(400, "Fully-Adresse bitte als Name oder IP, optional mit :Port")
        if v:
            setzen["fully_host"] = v
        else:
            weg += ["fully_host", "fully_pw"]
    if daten.get("fully_pw"):
        setzen["fully_pw"] = str(daten["fully_pw"])[:200]
    return setzen, weg


def geraete_aendern(g):
    """Neue Geraeteliste dauerhaft speichern und in Kraft setzen."""
    try:
        schreibe_json(GERAETE_FILE, {"version": 1, "geraete": [{"id": z, **e} for z, e in g.items()]})
    except OSError as e:
        H.log.error("Geraeteliste nicht speicherbar: %s", e)
        raise HTTPException(500, "Die Geräteliste konnte nicht gespeichert werden.")
    REGISTER["aktiv"] = True
    geraete_anwenden(g)


def geraet_aufraeumen(z):
    AKTIV_BESITZER.pop(z, None)
    PLAYER_REIHE.pop(z, None)
    FULLY_STATE.pop(z, None)
    WACHE["gemeldet"].pop(z, None)
    AMBIENT_PRO_ZIEL.pop(z, None)
    aktiv_speichern()


@app.get("/api/verwaltung")
def verwaltung(_=Depends(anmeldung)):
    return {"geraete": [geraet_ansicht(z, e) for z, e in GERAETE.items()], "register_aktiv": REGISTER["aktiv"],
            "standard": {"sek": std_sek(), "fuellung_rahmen": std_fuellung_rahmen(), "fuellung_tv": std_fuellung_tv(), "anzeige": std_anzeige(), "nacht": RAHMEN_NACHT}}


@app.post("/api/verwaltung/geraete")
def geraet_anlegen(daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    art = str(daten.get("art", ""))
    if art not in ("rahmen", "tv"):
        raise HTTPException(400, "Bitte Rahmen oder Fernseher wählen")
    name = name_pruefen(daten.get("name"))
    setzen, _weg = geraet_felder({**daten, "name": name}, art)
    with GERAETE_LOCK:
        z = geraet_kennung(name)
        g = {k: dict(v) for k, v in GERAETE.items()}
        g[z] = {"art": art, **setzen}
        geraete_aendern(g)
    H.log.info("Geraet angelegt: %s (%s) '%s'", z, art, name)
    return {"ok": True, "id": z, "geraet": geraet_ansicht(z, GERAETE[z]), "nachricht": f"„{name}“ wurde angelegt. Öffne am Gerät die Seite /tv/ und koppele es mit dem Code."}


@app.put("/api/verwaltung/geraete/{z}")
def geraet_aendern(z: str, daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    with GERAETE_LOCK:
        if z not in GERAETE:
            raise HTTPException(404, "Gerät nicht gefunden")
        setzen, weg = geraet_felder(daten, GERAETE[z]["art"])
        g = {k: dict(v) for k, v in GERAETE.items()}
        g[z].update(setzen)
        for k in weg:
            g[z].pop(k, None)
        geraete_aendern(g)
    return {"ok": True, "geraet": geraet_ansicht(z, GERAETE[z])}


@app.delete("/api/verwaltung/geraete/{z}")
def geraet_loeschen(z: str, _=Depends(anmeldung), __=Depends(csrf)):
    with GERAETE_LOCK:
        if z not in GERAETE:
            raise HTTPException(404, "Gerät nicht gefunden")
        name = GERAETE[z]["name"]
        geraete_aendern({k: dict(v) for k, v in GERAETE.items() if k != z})
        geraet_aufraeumen(z)
    H.log.info("Geraet geloescht: %s '%s'", z, name)
    return {"ok": True, "nachricht": f"„{name}“ wurde entfernt. Gespeicherte Shows bleiben erhalten."}


@app.post("/api/verwaltung/fully-test")
def fully_test(daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    """Prueft die Verbindung zu Fully Kiosk (Adresse und Passwort aus der Anfrage, sonst die gespeicherten)."""
    z = str(daten.get("id", ""))
    host = str(daten.get("fully_host") or (GERAETE.get(z) or {}).get("fully_host") or "").strip()
    pw = str(daten.get("fully_pw") or (GERAETE.get(z) or {}).get("fully_pw") or os.environ.get("RAHMEN_WEB_FULLY_PASSWORT", ""))
    if not FULLY_RE.fullmatch(host):
        raise HTTPException(400, "Bitte die Adresse des Tablets eintragen")
    try:
        info = json.loads(fully_get(f"http://{host if ':' in host else host + ':2323'}/?" + urllib.parse.urlencode({"cmd": "deviceInfo", "password": pw, "type": "json"})))
    except (OSError, ValueError) as e:
        raise HTTPException(502, "Das Tablet ist von diesem Server aus nicht erreichbar (Adresse falsch, Tablet aus, „Remote Admin“ in Fully nicht eingeschaltet oder eine Firewall/ein anderes Netz dazwischen). "
                                 f"Technisch: {e}")
    if str(info.get("status", "")).lower() == "error":
        raise HTTPException(401 if "login" in str(info.get("statustext", "")).lower() else 502,
                            "Das Passwort stimmt nicht – es ist das „Remote Admin Password“ aus den Fully-Einstellungen." if "login" in str(info.get("statustext", "")).lower() else f"Fully meldet: {info.get('statustext')}")
    return {"ok": True, "akku": info.get("batteryLevel"), "laedt": bool(info.get("isPlugged")), "nachricht": f"Verbunden – Akku {info.get('batteryLevel')} %"}


# --------------------------------------------------------------------------- Einstellungen in der App
_lade_personen_orig = H.lade_personen


def _lade_personen_mit_app():
    named, alias = _lade_personen_orig()
    for e in EINST.get("aliase") or []:                                   # Spitznamen aus der App ("oma" -> "Erika Muster")
        if e.get("name") and e.get("person"):
            alias[H.norm(e["name"])] = e["person"]
    return named, alias


H.lade_personen = _lade_personen_mit_app


def einst_speichern():
    try:
        schreibe_json(EINST_FILE, EINST)
    except OSError as e:
        H.log.error("Einstellungen nicht speicherbar: %s", e)
        raise HTTPException(500, "Die Einstellungen konnten nicht gespeichert werden.")
    ZUSATZ_CACHE.clear()
    PERSONEN_CACHE["t"] = 0.0


def einst_ansicht():
    pe = EINST.get("pushover") or {}
    namen = []
    try:
        namen = sorted({n for n, _i in H.lade_personen()[0]})
    except Exception:  # noqa: BLE001 - ohne Immich keine Personenliste
        pass
    return {"sek": EINST.get("sek"), "fuellung_rahmen": EINST.get("fuellung_rahmen") or "", "fuellung_tv": EINST.get("fuellung_tv") or "",
            "anzeige": EINST.get("anzeige") or [], "alarm_min": EINST.get("alarm_min"), "tv_url": EINST.get("tv_url") or "",
            "wetter": EINST.get("wetter") or None, "wetter_env": bool(WETTER_ORT) and not EINST.get("wetter"),
            "kalender_gesetzt": bool(EINST.get("kalender_url")), "kalender_env": bool(KALENDER_URL) and not EINST.get("kalender_url"),
            "pushover_gesetzt": bool(pe.get("user") and pe.get("token")), "pushover_geraet": pe.get("device") or "",
            "aliase": EINST.get("aliase") or [], "personen": namen,
            "standard": {"sek": RAHMEN_SEK, "fuellung_rahmen": RAHMEN_FUELLUNG, "fuellung_tv": TV_FUELLUNG, "anzeige": RAHMEN_ANZEIGE, "alarm_min": RAHMEN_ALARM_MIN, "tv_url": TV_URL}}


@app.get("/api/einstellungen")
def einstellungen_lesen(_=Depends(anmeldung)):
    return einst_ansicht()


@app.put("/api/einstellungen")
def einstellungen_aendern(daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    neu = dict(EINST)

    def setzen(key, wert):
        if wert in (None, "", [], {}):
            neu.pop(key, None)
        else:
            neu[key] = wert
    if "sek" in daten:
        try:
            setzen("sek", None if daten["sek"] in (None, "") else max(3, min(int(daten["sek"]), 120)))
        except (TypeError, ValueError):
            raise HTTPException(400, "Sekunden pro Foto: bitte eine Zahl zwischen 3 und 120")
    for k in ("fuellung_rahmen", "fuellung_tv"):
        if k in daten:
            v = str(daten[k] or "")
            if v and v not in FUELLUNGEN:
                raise HTTPException(400, "Unbekannte Hintergrund-Füllung")
            setzen(k, v)
    if "anzeige" in daten:
        a = daten["anzeige"] if isinstance(daten["anzeige"], list) else []
        if any(x not in ("datum", "zeit", "ort") for x in a):
            raise HTTPException(400, "Unbekannte Bildunterschrift")
        setzen("anzeige", [x for x in ("datum", "zeit", "ort") if x in a])
    if "alarm_min" in daten:
        if daten["alarm_min"] in (None, ""):
            neu.pop("alarm_min", None)
        else:
            try:
                neu["alarm_min"] = max(0, min(int(daten["alarm_min"]), 1440))
            except (TypeError, ValueError):
                raise HTTPException(400, "Minuten bis zum Alarm: bitte eine Zahl (0 = aus)")
    if "tv_url" in daten:
        v = str(daten["tv_url"] or "").strip().rstrip("/")
        if v and not re.fullmatch(r"[A-Za-z0-9.:/_-]{1,200}", v):
            raise HTTPException(400, "Adresse der Fernseher-Seite ungültig")
        setzen("tv_url", v)
    if "wetter" in daten:
        w = daten["wetter"]
        if w:
            try:
                lat, lon = float(w["lat"]), float(w["lon"])
                assert -90 <= lat <= 90 and -180 <= lon <= 180
            except (KeyError, TypeError, ValueError, AssertionError):
                raise HTTPException(400, "Wetter-Ort ungültig")
            setzen("wetter", {"lat": lat, "lon": lon, "name": str(w.get("name") or "")[:80]})
        else:
            setzen("wetter", None)
    if "kalender_url" in daten:
        v = daten["kalender_url"]
        if v is None:
            neu.pop("kalender_url", None)
        elif str(v).strip():
            v = str(v).strip()
            if not re.match(r"^https?://\S{4,1000}$", v):
                raise HTTPException(400, "Kalender-Link bitte als https://… eintragen")
            neu["kalender_url"] = v
    if "pushover" in daten:
        pz = daten["pushover"]
        if pz is None:
            neu.pop("pushover", None)
        elif isinstance(pz, dict):
            alt = neu.get("pushover") or {}
            user, token = str(pz.get("user") or alt.get("user") or "").strip(), str(pz.get("token") or alt.get("token") or "").strip()
            if (user or token) and not (re.fullmatch(r"[A-Za-z0-9]{20,40}", user) and re.fullmatch(r"[A-Za-z0-9]{20,40}", token)):
                raise HTTPException(400, "Pushover: User-Key und App-Token bitte vollständig eintragen (je 30 Zeichen)")
            if user and token:
                neu["pushover"] = {"user": user, "token": token, "device": str(pz.get("device") or "").strip()[:25]}
    if "aliase" in daten:
        liste = daten["aliase"] if isinstance(daten["aliase"], list) else []
        sauber = []
        for e in liste[:50]:
            n, pn = re.sub(r"[;=]", "", str((e or {}).get("name") or "")).strip()[:40], str((e or {}).get("person") or "").strip()[:80]
            if n and pn:
                sauber.append({"name": n, "person": pn})
        setzen("aliase", sauber)
    with GERAETE_LOCK:
        EINST.clear()
        EINST.update(neu)
        einst_speichern()
    return {"ok": True, "einstellungen": einst_ansicht()}


@app.get("/api/einstellungen/ort-suche")
def ort_suche(q: str, _=Depends(anmeldung)):
    """Sucht einen Ort fuer das Wetter (Open-Meteo, ohne Konto). Es wird nur der Suchbegriff uebertragen."""
    q = q.strip()[:80]
    if len(q) < 2:
        return {"orte": []}
    try:
        d = json.loads(http_text("https://geocoding-api.open-meteo.com/v1/search?count=6&language=de&name=" + urllib.parse.quote(q)))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Ortssuche nicht erreichbar: {e}")
    return {"orte": [{"name": o.get("name", ""), "land": o.get("country", ""), "region": o.get("admin1", ""), "lat": o["latitude"], "lon": o["longitude"]}
                     for o in (d.get("results") or [])]}


@app.post("/api/einstellungen/test")
def einstellungen_testen(daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    was = str(daten.get("was", ""))
    try:
        if was == "wetter":
            if not wetter_ort():
                raise ValueError("Kein Ort eingestellt")
            w = wetter_holen()
            return {"ok": True, "nachricht": f"Wetter gelesen: {w['symbol']} {w['temp']} °C"}
        if was == "kalender":
            if not kalender_url():
                raise ValueError("Kein Kalender-Link eingestellt")
            return {"ok": True, "nachricht": f"Kalender gelesen: {len(kalender_holen())} Termin(e) in den nächsten Tagen"}
        if was == "pushover":
            pushover_senden("Immich Showcase", "Test: Benachrichtigungen funktionieren.", 0)
            return {"ok": True, "nachricht": "Test-Nachricht gesendet"}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Test fehlgeschlagen: {e}")
    raise HTTPException(400, "Unbekannter Test")


@app.post("/api/geraete/bildschirm")
def geraete_bildschirm(daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    return bildschirm_schalten(daten)


def bildschirm_schalten(daten):
    z = str(daten.get("ziel", ""))
    if z not in FULLY:
        raise HTTPException(400, "Dieses Geraet ist nicht fuer Fully Kiosk eingerichtet")
    try:
        fully_bildschirm(z, bool(daten.get("an")))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Fully Kiosk antwortet nicht: {e}")
    return {"ok": True, "bildschirm": FULLY_STATE[z]["bildschirm"]}


# --------------------------------------------------------------------------- Home Assistant (und andere Automationen): Zustand lesen, steuern
# Zugriff wie bei den Geraeteseiten: aus dem vertrauten Netz (RAHMEN_WEB_LAN muss die Adresse von Home Assistant enthalten) oder mit Sitzung.
@app.get("/api/ha/status")
def ha_status(_=Depends(geraet)):
    return {"version": VERSION, "geraete": geraete_liste(), "shows": [x["name"] for x in daten_lesen()["shows"]]}


@app.post("/api/ha/steuer")
def ha_steuer(daten: dict, _=Depends(geraet), __=Depends(csrf)):
    if str(daten.get("aktion", "")) not in ("pause", "weiter", "vor", "zurueck", "stopp", "lauter", "leiser", "naechster"):
        raise HTTPException(400, "Unbekannte Aktion")
    return steuer_senden({"ziel": daten.get("ziel"), "aktion": daten.get("aktion")})


@app.post("/api/ha/show")
def ha_show(daten: dict, _=Depends(geraet), __=Depends(csrf)):
    """Eine gespeicherte Show (nach Name) auf einem Fernseher/Rahmen starten."""
    name = H.norm(str(daten.get("show", "")))
    show = next((x for x in daten_lesen()["shows"] if H.norm(x["name"]) == name), None)
    if not show:
        raise HTTPException(404, "Show nicht gefunden")
    senden = {"ziel": daten.get("ziel"), "ids": show["ids"], "name": show["name"]}
    for k in ("sekunden", "musik", "laut", "reihenfolge"):
        if k in daten:
            senden[k] = daten[k]
    return tv_senden(senden, None, None)


@app.post("/api/ha/bildschirm")
def ha_bildschirm(daten: dict, _=Depends(geraet), __=Depends(csrf)):
    return bildschirm_schalten(daten)


KOPPEL = {}                       # code -> {"t": Zeit, "ziel": None|Kennung, "ip": ...}
KOPPEL_LOCK = threading.Lock()
KOPPEL_ZEICHEN = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"        # ohne leicht verwechselbare Zeichen (0/O, 1/I)
KOPPEL_LEBEN = 900


def koppel_aufraeumen(jetzt):
    for c in [c for c, v in KOPPEL.items() if jetzt - v["t"] > KOPPEL_LEBEN]:
        del KOPPEL[c]


@app.post("/api/koppeln/neu")
def koppeln_neu(request: Request, _=Depends(csrf)):
    """Ein noch nicht gekoppeltes Geraet (Fernseher/Tablet) holt sich einen Code, der am Handy eingegeben wird. Ohne Anmeldung, aber begrenzt."""
    ip, jetzt = client_ip(request), time.time()
    with KOPPEL_LOCK:
        koppel_aufraeumen(jetzt)
        if len(KOPPEL) >= 30 or sum(1 for v in KOPPEL.values() if v["ip"] == ip) >= 5:
            raise HTTPException(429, "Zu viele offene Codes - bitte kurz warten")
        code = "".join(secrets.choice(KOPPEL_ZEICHEN) for _ in range(6))
        KOPPEL[code] = {"t": jetzt, "ziel": None, "ip": ip}
    return {"code": code, "gueltig_s": KOPPEL_LEBEN}


@app.get("/api/koppeln/status")
def koppeln_status(code: str = ""):
    with KOPPEL_LOCK:
        koppel_aufraeumen(time.time())
        eintrag = KOPPEL.get(code.strip().upper())
    if not eintrag:
        raise HTTPException(404, "Code unbekannt oder abgelaufen")
    z = eintrag["ziel"]
    return {"ziel": z, "name": TV_ZIELE.get(z) if z else None}


@app.post("/api/koppeln")
def koppeln_setzen(daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    """Die App weist dem Geraet mit diesem Code einen Fernseher/Rahmen zu; das Geraet merkt es sich."""
    code, ziel = str(daten.get("code", "")).strip().upper(), str(daten.get("ziel", ""))
    if ziel not in TV_ZIELE or ziel in TV_VERSTECKT:
        raise HTTPException(400, "Unbekanntes Ziel")
    with KOPPEL_LOCK:
        koppel_aufraeumen(time.time())
        if code not in KOPPEL:
            raise HTTPException(404, "Code unbekannt oder abgelaufen")
        KOPPEL[code]["ziel"] = ziel
    return {"ok": True, "name": TV_ZIELE[ziel]}


# Ueberwachung: meldet (Pushover), wenn ein Rahmen nicht mehr erreichbar ist oder dasselbe Bild haengt, und wenn er zurueck ist
WACHE = {"gemeldet": {}, "start": time.time()}


def rahmen_wache_pruefen(jetzt=None):
    jetzt = jetzt or time.time()
    meldungen = []
    for z, name in RAHMEN_ZIELE.items():
        t = TV[z]
        zuletzt = max(t["hb"], WACHE["start"])
        offline_min = (jetzt - zuletzt) / 60
        alter = t.get("bild_alter")
        haengt = (jetzt - t["hb"] < 20 and t.get("ambient") and alter is not None and alter > max(std_sek() * 6, 180) + std_alarm_min() * 60)
        gemeldet = WACHE["gemeldet"].get(z)
        if std_alarm_min() and offline_min >= std_alarm_min() and gemeldet != "offline":
            WACHE["gemeldet"][z] = "offline"
            meldungen.append((f"{name} nicht erreichbar", f"Der Rahmen meldet sich seit {int(offline_min)} Minuten nicht mehr (Tablet aus, WLAN oder Browser beendet?)."))
        elif haengt and gemeldet != "haengt":
            WACHE["gemeldet"][z] = "haengt"
            meldungen.append((f"{name} zeigt dasselbe Bild", f"Seit {int(alter // 60)} Minuten kein Bildwechsel."))
        elif gemeldet and offline_min < 1 and not haengt:
            WACHE["gemeldet"].pop(z, None)
            meldungen.append((f"{name} wieder da", "Der Rahmen zeigt wieder sein Programm."))
    for titel, text in meldungen:
        H.log.warning("Rahmen-Ueberwachung: %s - %s", titel, text)
        pushover(titel, text)
    return meldungen


def rahmen_wache_schleife():
    while True:
        time.sleep(60)
        try:
            rahmen_wache_pruefen()
        except Exception as e:  # noqa: BLE001
            H.log.warning("Rahmen-Ueberwachung: %s", e)


@app.on_event("startup")
def rahmen_wache_starten():
    threading.Thread(target=rahmen_wache_schleife, daemon=True).start()


@app.get("/api/tv/ziele")
def tv_ziele(alle: int = 0, _=Depends(anmeldung)):
    t = time.time()
    def zeile(z, n):
        online = t - TV[z]["hb"] < 10
        # online: was der Fernseher WIRKLICH zeigt (er meldet es bei jeder Abfrage); offline: letzter Befehl
        spielt = (TV[z]["tv_name"] or "Wiedergabe") if (online and TV[z]["tv_laeuft"]) else (None if online else (TV[z]["aktiv"] or {}).get("name"))
        return {"id": z, "name": n, "online": online, "spielt": spielt, "musik": TV[z]["tv_musik"] if online else ""}
    return {"ziele": [zeile(z, n) for z, n in TV_ZIELE.items() if alle or (z not in TV_VERSTECKT and z not in RAHMEN_ZIELE)],
            "musik": [{"id": k, "name": v.get("name", k), "anzahl": len(v["stuecke"])} for k, v in musik_bibliothek().items()]}


def nach_datum(ids, aufsteigend):
    """Sortiert Medien nach Aufnahmedatum (Ortszeit). Mit Datenbank sofort, sonst per Immich-API (parallel, ca. 3 s je 1000)."""
    try:
        if DB_AKTIV:
            zeilen = db_lesen('select a.id::text from asset a where a.id = any(%s::uuid[]) order by a."localDateTime" ' + ("asc" if aufsteigend else "desc") + ', a."fileCreatedAt"', (ids,))
            geordnet = [r[0] for r in zeilen]
        else:
            from concurrent.futures import ThreadPoolExecutor

            def datum(i):
                try:
                    a = H.api("GET", f"/assets/{i}")
                    return (a.get("localDateTime") or a.get("fileCreatedAt") or "", a.get("fileCreatedAt") or "", i)
                except Exception:  # noqa: BLE001 - einzelnes Foto nicht lesbar: ans Ende
                    return ("9999", "9999", i)
            with ThreadPoolExecutor(8) as ex:
                kontexte = [contextvars.copy_context() for _ in ids]
                zeilen = sorted(ex.map(lambda c, i: c.run(datum, i), kontexte, ids), reverse=not aufsteigend)
            geordnet = [z[2] for z in zeilen]
        return geordnet + [i for i in ids if i not in set(geordnet)]
    except Exception as e:  # noqa: BLE001
        H.log.warning("Sortierung nach Datum nicht moeglich, Reihenfolge bleibt: %s", e)
        return ids


@app.post("/api/tv/senden")
def tv_senden(daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    z = str(daten.get("ziel", ""))
    t = tv_ziel(z)
    ids = ids_pruefen(daten.get("ids"))
    name = name_pruefen(daten.get("name") or "Auswahl")
    try:
        sek = max(3, min(int(daten.get("sekunden", 5)), 60))
    except (TypeError, ValueError):
        sek = 5
    musik = str(daten.get("musik") or "")
    if musik and musik not in musik_bibliothek():
        raise HTTPException(400, "Unbekannte Musikauswahl")
    try:
        laut = max(0.05, min(float(daten.get("laut", 0.3)), 1.0))
    except (TypeError, ValueError):
        laut = 0.3
    videos = [v for v in dict.fromkeys(str(x) for x in (daten.get("videos") or [])) if v in set(ids)][:30]
    try:
        maxv = max(10, min(int(daten.get("maxv", 60)), 300))
    except (TypeError, ValueError):
        maxv = 60
    reihe = str(daten.get("reihenfolge") or "alt")           # alt = aeltestes zuerst (Standard), neu = neuestes zuerst, zufall = gemischt
    if reihe not in ("alt", "neu", "zufall"):
        reihe = "alt"
    if reihe != "zufall" and len(ids) > 1:
        ids = nach_datum(ids, reihe == "alt")
    if MODUS == "tv":                                  # reine Fernseher-Installation: die Show erscheint unter "Meine Shows"
        with H.LOCK:
            d = daten_lesen()
            e = next((x for x in d["shows"] if H.norm(x["name"]) == H.norm(name)), None)
            if e:
                e.update({"ids": ids, "zeit": jetzt()})
                d["shows"].remove(e)
            else:
                e = neue_show(name, ids, False)
            d["shows"].insert(0, e)
            daten_schreiben(d)
    felder = {"ids": ids, "name": name, "sek": sek, "zufall": reihe == "zufall", "musik": musik, "laut": laut, "videos": videos, "maxv": maxv}

    def veroeffentlichen():
        player_ereignis(z, felder)

    fehlen = [v for v in videos if not os.path.isfile(os.path.join(VIDEO_DIR, f"v-{v}.mp4"))]
    online = time.time() - t["hb"] < 10
    H.log.info("TV %s: '%s' mit %d Fotos, %d Videos (%d noch umzuwandeln, online=%s, musik=%s)", z, name, len(ids), len(videos), len(fehlen), online, musik or "-")
    if fehlen:
        # Start erst, wenn alle ausgewaehlten Videos im Fernsehformat bereitliegen - dann muss der Fernseher nirgends warten
        def vorbereiten():
            for v in fehlen:
                tv_video_bereiten_still(v, H.schluessel())
            veroeffentlichen()
        thread_mit_kontext(vorbereiten)
        return {"ok": True, "online": online, "wartet": len(fehlen),
                "nachricht": f"{len(fehlen)} Video(s) werden für den Fernseher vorbereitet – \"{name}\" startet gleich auf {TV_ZIELE[z]}."}
    veroeffentlichen()
    return {"ok": True, "online": online, "nachricht": f"\"{name}\" ({len(ids)} Medien) wurde an {TV_ZIELE[z]} geschickt."
            + ("" if online else f" {TV_ZIELE[z]} ist gerade nicht bereit – es startet, sobald die Seite {tv_url() or 'des Fernsehers (…/tv/)'} dort geöffnet ist.")}


@app.post("/api/tv/steuer")
def tv_steuer(daten: dict, _=Depends(anmeldung), __=Depends(csrf)):
    return steuer_senden(daten)


def steuer_senden(daten):
    z = str(daten.get("ziel", ""))
    t = tv_ziel(z)
    aktion = str(daten.get("aktion", ""))
    if aktion not in ("pause", "weiter", "vor", "zurueck", "stopp", "musik", "lauter", "leiser", "naechster", "titel"):
        raise HTTPException(400, "Unbekannte Aktion")
    wert = str(daten.get("wert") or "")
    if aktion == "musik" and wert and wert not in musik_bibliothek():
        raise HTTPException(400, "Unbekannte Musikauswahl")
    if aktion == "titel" and not DATEI_RE.match(wert):
        raise HTTPException(400, "Unbekannter Titel")
    with TV_EV:
        t["seq"] += 1
        t["events"] = (t["events"] + [{"seq": t["seq"], "typ": "steuer", "aktion": aktion, "wert": wert}])[-30:]
        if aktion == "stopp":
            t["aktiv"] = None
    if aktion == "stopp":
        aktiv_speichern()
    return {"ok": True}


@app.get("/api/tv/abfrage")
def tv_abfrage(request: Request, ziel: str, seq: int = -1, s: int = 0, n: str = "", m: str = "", ra: int = -1, a: int = 0, fj: int = 0, ak: int = -1, pl: int = -1, _=Depends(geraet)):
    """Vom Fernseher alle 2 s aufgerufen (zaehlt zugleich als 'online'). s/n/m = was der Fernseher gerade wirklich tut."""
    t = tv_ziel(ziel)
    t["hb"] = time.time()
    t["tv_laeuft"], t["tv_name"], t["tv_musik"] = bool(s), n[:60], (m if KAT_RE.match(m or "") else "")
    t["ambient"], t["bild_alter"] = bool(a), (ra if ra >= 0 else None)       # Dauerprogramm aktiv / Sekunden seit dem letzten Bildwechsel
    t["fully_js"] = bool(fj)                                                  # die Seite laeuft in Fully Kiosk mit aktiver JavaScript-Schnittstelle
    ip = client_ip(request)
    try:
        t["ip"] = ip if ipaddress.ip_address(ip).is_private else ""
    except ValueError:
        t["ip"] = ""
    if fj and 0 <= ak <= 100:
        akku_melden(ziel, ak, pl == 1)
    if seq < 0:                                   # Seite neu geladen: laufende Show fortsetzen
        return {"seq": t["seq"], "events": [t["aktiv"]] if t["aktiv"] else []}
    if seq > t["seq"]:                            # Server wurde neu gestartet
        return {"seq": t["seq"], "events": []}
    return {"seq": t["seq"], "events": [e for e in t["events"] if e["seq"] > seq]}


VIDEO_LOCK = threading.Lock()
VIDEO_DIR = os.environ.get("RAHMEN_WEB_VIDEO_DIR", "/data/videos")      # dauerhafter Zwischenspeicher (nicht die 12-h-Ablage der AirPlay-Videos)
VIDEO_CACHE_MAX = int(os.environ.get("RAHMEN_WEB_VIDEO_CACHE_MB", "3000")) * 1024 * 1024


def tv_video_bereiten(aid, schluessel=None):
    """Wandelt ein Immich-Video einmal in ein Standardformat (H.264/AAC, max. 1080p) um und legt es dauerhaft zwischen."""
    ziel = os.path.join(VIDEO_DIR, f"v-{aid}.mp4")
    if os.path.isfile(ziel):
        os.utime(ziel)
        return ziel
    os.makedirs(VIDEO_DIR, exist_ok=True)
    with VIDEO_LOCK:
        if os.path.isfile(ziel):
            return ziel
        quelle, tmp = ziel + ".src", ziel + ".tmp.mp4"
        try:
            req = urllib.request.Request(H.IMMICH + f"/assets/{aid}/video/playback", headers={"x-api-key": schluessel or H.schluessel()})
            with urllib.request.urlopen(req, timeout=120) as r, open(quelle, "wb") as f:
                shutil.copyfileobj(r, f)
            r = subprocess.run(["nice", "-n", "15", FFMPEG, "-nostdin", "-v", "error", "-y", "-i", quelle,
                                "-vf", "scale=w=1920:h=1080:force_original_aspect_ratio=decrease:force_divisible_by=2,scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
                                "-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-preset", "veryfast", "-crf", "23", "-threads", "2",
                                "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                                "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-movflags", "+faststart", tmp], capture_output=True, timeout=900)
            if r.returncode or not os.path.isfile(tmp):
                raise RuntimeError("ffmpeg: " + r.stderr.decode(errors="replace")[:200])
            os.replace(tmp, ziel)
        finally:
            for f in (quelle, tmp):
                try:
                    os.remove(f)
                except OSError:
                    pass
    return ziel


def video_cache_begrenzen():
    """Haelt den Zwischenspeicher unter der Grenze: aelteste (zuletzt nicht genutzte) Videos zuerst entfernen."""
    try:
        dateien = [(os.path.getmtime(p), os.path.getsize(p), p) for p in (os.path.join(VIDEO_DIR, n) for n in os.listdir(VIDEO_DIR)) if p.endswith(".mp4")]
    except OSError:
        return
    gesamt = sum(d[1] for d in dateien)
    for _m, groesse, pfad in sorted(dateien):
        if gesamt <= VIDEO_CACHE_MAX:
            break
        try:
            os.remove(pfad)
            gesamt -= groesse
        except OSError:
            pass


def video_cache_groesse():
    try:
        return sum(os.path.getsize(os.path.join(VIDEO_DIR, n)) for n in os.listdir(VIDEO_DIR) if n.endswith(".mp4"))
    except OSError:
        return 0


def video_vorbereiter():
    """Hintergrunddienst: wandelt die NEUESTEN 60 Videos (bis 3 Min) im Voraus um, solange der Zwischenspeicher unter 80 % der Grenze liegt.
    Alle anderen Videos werden bei Bedarf umgewandelt, wenn sie fuer den Fernseher ausgewaehlt werden (siehe tv_senden)."""
    while not konfiguriert():                                    # im Einrichtungsmodus nichts tun
        time.sleep(30)
    time.sleep(20)
    while True:
        neu = 0
        try:
            d = H.api("POST", "/search/metadata", {"type": "VIDEO", "size": 60, "page": 1, "order": "desc"})["assets"]
            for a in d["items"]:
                if video_cache_groesse() > VIDEO_CACHE_MAX * 0.8:
                    break
                if dauer_sek(a) > 180 or os.path.isfile(os.path.join(VIDEO_DIR, f"v-{a['id']}.mp4")):
                    continue
                tv_video_bereiten_still(a["id"])
                neu += 1
            video_cache_begrenzen()
            if neu:
                H.log.info("Video-Vorbereiter: %d Video(s) umgewandelt", neu)
        except Exception as e:  # noqa: BLE001
            H.log.warning("Video-Vorbereiter: %s", e)
        time.sleep(1800)


@app.on_event("startup")
def video_vorbereiter_starten():
    threading.Thread(target=video_vorbereiter, daemon=True).start()


def tv_video_bereiten_still(aid, schluessel=None):
    try:
        tv_video_bereiten(aid, schluessel)
    except Exception as e:  # noqa: BLE001 - wird beim Abruf nochmal versucht
        H.log.warning("Video %s vorbereiten fehlgeschlagen: %s", aid, e)


@app.get("/api/tv/videodatei/{asset_id}")
def tv_videodatei(asset_id: str, _=Depends(geraet)):
    if not ID_RE.match(asset_id):
        raise HTTPException(404, "ungueltig")
    try:
        pfad = tv_video_bereiten(asset_id, None if UID_CTX.get() else geraete_schluessel(asset_id))
    except Exception as e:  # noqa: BLE001
        H.log.warning("Video %s: %s", asset_id, e)
        raise HTTPException(502, "Video nicht verfuegbar")
    return FileResponse(pfad, media_type="video/mp4", headers={"Cache-Control": "private, max-age=3600", "Accept-Ranges": "bytes"})


@app.get("/api/tv/musikliste")
def tv_musikliste(k: str, _=Depends(geraet)):
    info = musik_bibliothek().get(k)
    if not info:
        raise HTTPException(404, "Musikauswahl unbekannt")
    return {"name": info.get("name", k), "stuecke": [{k2: st.get(k2, "") for k2 in ("datei", "titel", "urheber", "lizenz", "kat")} for st in info["stuecke"]]}


@app.get("/api/tv/musikdatei/{kat}/{datei}")
def tv_musikdatei(kat: str, datei: str, _=Depends(geraet)):
    info = musik_bibliothek().get(kat)
    eintrag = next((st for st in (info or {}).get("stuecke", []) if st["datei"] == datei), None)
    if not eintrag:
        raise HTTPException(404, "Datei nicht gefunden")
    pfad = os.path.realpath(os.path.join(MUSIK_DIR, eintrag["pfad"]))
    if not pfad.startswith(os.path.realpath(MUSIK_DIR) + os.sep) or not os.path.isfile(pfad):
        raise HTTPException(404, "Datei nicht gefunden")
    typ = MUSIK_TYPEN.get(os.path.splitext(pfad)[1].lower(), "audio/mpeg")
    return FileResponse(pfad, media_type=typ, headers={"Cache-Control": "private, max-age=86400", "Accept-Ranges": "bytes"})


def musik_ordner_gesamt():
    summe = 0
    for wurzel, _, dateien in os.walk(MUSIK_DIR):
        summe += sum(os.path.getsize(os.path.join(wurzel, f)) for f in dateien if os.path.splitext(f)[1].lower() in MUSIK_TYPEN)
    return summe


@app.put("/api/musik/{sammlung}/{dateiname}")
async def musik_hochladen(sammlung: str, dateiname: str, request: Request, _=Depends(anmeldung), __=Depends(csrf)):
    """Eigene Musik hinzufuegen (nur mit RAHMEN_WEB_MUSIK_UPLOAD=1): roher Dateiinhalt im Body."""
    if not MUSIK_UPLOAD:
        raise HTTPException(403, "Hochladen ist nicht aktiviert")
    ext = os.path.splitext(dateiname)[1].lower()
    if ext not in MUSIK_TYPEN:
        raise HTTPException(400, "Nur mp3-, ogg- und m4a-Dateien")
    kat = kat_slug(sammlung)
    sauber = re.sub(r"[^\w .()&+'-]", "_", os.path.splitext(os.path.basename(dateiname))[0], flags=re.UNICODE).strip(" .")[:80] or "titel"
    ordner = os.path.join(MUSIK_DIR, kat)
    neu_angelegt = not os.path.isdir(ordner)
    os.makedirs(ordner, exist_ok=True)
    ziel = os.path.join(ordner, sauber + ext)
    n = 2
    while os.path.exists(ziel):
        ziel = os.path.join(ordner, f"{sauber} ({n}){ext}")
        n += 1
    tmp = ziel + ".hochladen"
    groesse, limit = 0, MUSIK_MAX_MB * 1024 * 1024
    try:
        with open(tmp, "wb") as f:
            async for stueck in request.stream():
                groesse += len(stueck)
                if groesse > limit:
                    raise HTTPException(413, f"Die Datei ist groesser als {MUSIK_MAX_MB} MB")
                f.write(stueck)
        if musik_ordner_gesamt() + groesse > MUSIK_GESAMT_MB * 1024 * 1024:
            raise HTTPException(413, "Die Musiksammlung ist voll")
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", tmp], capture_output=True, text=True, timeout=30)
        try:
            dauer = float(r.stdout.strip().split()[0])
        except (ValueError, IndexError):
            dauer = 0
        if dauer <= 0:
            raise HTTPException(400, "Das ist keine abspielbare Audiodatei")
        os.replace(tmp, ziel)
        if neu_angelegt and sammlung.strip() and sammlung.strip() != kat:         # urspruenglichen Namen (Umlaute, Leerzeichen) behalten
            schreibe_json(os.path.join(ordner, "info.json"), {"name": sammlung.strip()[:40], "stuecke": []})
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    musik_neu_einlesen()
    H.log.info("Musik hinzugefuegt: %s/%s (%d KB)", kat, os.path.basename(ziel), groesse // 1024)
    return {"ok": True, "sammlung": kat, "datei": os.path.basename(ziel)}


@app.delete("/api/musik/{kat}/{datei}")
def musik_loeschen(kat: str, datei: str, _=Depends(anmeldung), __=Depends(csrf)):
    if not MUSIK_UPLOAD:
        raise HTTPException(403, "Verwalten ist nicht aktiviert")
    info = musik_bibliothek().get(kat)
    eintrag = next((st for st in (info or {}).get("stuecke", []) if st["datei"] == datei and not st.get("kat")), None)
    if not eintrag:
        raise HTTPException(404, "Datei nicht gefunden")
    pfad = os.path.realpath(os.path.join(MUSIK_DIR, eintrag["pfad"]))
    if not pfad.startswith(os.path.realpath(MUSIK_DIR) + os.sep) or not os.path.isfile(pfad):
        raise HTTPException(404, "Datei nicht gefunden")
    os.remove(pfad)
    ordner = os.path.dirname(pfad)
    try:
        if os.path.realpath(ordner) != os.path.realpath(MUSIK_DIR) and not any(os.path.splitext(f)[1].lower() in MUSIK_TYPEN for f in os.listdir(ordner)):
            if os.path.isfile(os.path.join(ordner, "info.json")):
                os.remove(os.path.join(ordner, "info.json"))
            os.rmdir(ordner)                                    # leere Sammlung verschwindet
    except OSError:
        pass
    musik_neu_einlesen()
    return {"ok": True}


# --------------------------------------------------------------------------- Fehlerbild + Oberflaeche

@app.exception_handler(HTTPException)
async def http_fehler(request: Request, exc: HTTPException):
    return JSONResponse({"ok": False, "nachricht": exc.detail}, status_code=exc.status_code)


@app.exception_handler(urllib.error.HTTPError)
async def immich_fehler(request: Request, exc: urllib.error.HTTPError):
    if exc.code == 401 and UID_CTX.get():                           # Schluessel der Person bei Immich widerrufen/abgelaufen
        return JSONResponse({"ok": False, "nachricht": "Anmeldung erforderlich"}, status_code=401)
    H.log.warning("Immich-Fehler %s bei %s", exc.code, request.url.path)
    return JSONResponse({"ok": False, "nachricht": "Immich hat die Anfrage abgelehnt oder ist nicht erreichbar."}, status_code=502)


@app.exception_handler(Exception)
async def allgemeiner_fehler(request: Request, exc: Exception):
    H.log.exception("Fehler bei %s", request.url.path)
    return JSONResponse({"ok": False, "nachricht": "Es ist ein Fehler aufgetreten. Bitte nochmal versuchen."}, status_code=500)


def _stand():
    """Pruefsumme der Oberflaeche: aendert sich mit jedem neuen Build -> geoeffnete Seiten merken es und bieten Aktualisieren an."""
    h = hashlib.sha1()
    for wurzel, _ordner, dateien in sorted(os.walk(STATIC_DIR)):
        for d in sorted(dateien):
            with open(os.path.join(wurzel, d), "rb") as f:
                h.update(d.encode() + f.read())
    return h.hexdigest()[:12]


APP_VERSION = _stand() if os.path.isdir(STATIC_DIR) else "0"


@app.get("/api/version")
def version():
    return {"v": APP_VERSION}


@app.middleware("http")
async def kein_cache(request: Request, call_next):
    antwort = await call_next(request)
    if not request.url.path.startswith("/api/"):
        antwort.headers["Cache-Control"] = "no-cache"      # Oberflaeche immer gegenpruefen (ETag), nie veraltet aus dem Browser-Cache
    return antwort


if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--set-pin":
        if not re.fullmatch(r"\d{6}", sys.argv[2]):
            sys.exit("Die PIN muss genau 6 Ziffern haben.")
        fd = os.open(PIN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.write(fd, pin_hash(sys.argv[2]).encode())
        os.close(fd)
        print("PIN gesetzt; alle gemerkten Geraete muessen sich neu anmelden.")
    else:
        sys.exit("Aufruf: rahmen_web.py --set-pin 123456   (Dienst: uvicorn rahmen_web:app)")
