#!/usr/bin/env python3
"""Bilderrahmen-Helfer (angelegt 2026-10-02).

Versteht Wuensche wie "Anna und Opa 2019 am Strand" oder "Weihnachten 2020",
sucht passende Fotos in Immich und zeigt sie exklusiv auf dem Tablet-Bilderrahmen.

Ablauf: Wunsch zerlegen (Personen / Zeit / Ort / Favoriten / Motiv) -> Immich
durchsuchen -> temporaeres Album "Rahmen: <Wunsch>" mit #nurrahmen anlegen ->
bilderrahmen_sync_albums.py sofort anstossen. Das vorherige Helfer-Album wird
dabei geloescht; andere exklusive Alben (z.B. ein Urlaubsalbum) werden pausiert und
mit /normal wieder hergestellt.

Sicherheit: nutzt einen eigenen Immich-Schluessel OHNE Foto-Loeschrecht
(/root/.rahmen_helfer_key). Geloescht werden nur Alben, die dieser Helfer selbst
angelegt hat (Name "Rahmen: ..." UND Marker #rahmenhelfer) - Fotos bleiben immer.

Aufruf:
  HTTP  GET/POST /zeige?text=...[&dry=1]   GET/POST /normal   GET /status   GET /personen
        Token per Header "X-Rahmen-Token" oder ?token=...
  CLI   rahmen_helfer.py --test "Anna 2021 am Strand"   (nur suchen, nichts aendern)
"""

import calendar
import fcntl
import contextvars
import datetime as dt
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import unicodedata
import uuid
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_BSP = [b.strip() for b in os.environ.get("RAHMEN_WEB_BEISPIELE", "Sommer 2022; Geburtstag; Strand").split(";") if b.strip()]
BEISPIEL_TEXT = " oder ".join('"' + b + '"' for b in _BSP[:2])
IMMICH = os.environ.get("RAHMEN_IMMICH_URL", "http://localhost:2283/api")
KEY = os.environ.get("RAHMEN_IMMICH_KEY", "")
TOKEN_FILE = "/root/.rahmen_helfer_token"
STATE_DIR = os.environ.get("RAHMEN_STATE_DIR", "/var/lib/bilderrahmen")     # Zustand des Helfers (Rahmen-Status, Merkliste)
STATE_FILE = os.path.join(STATE_DIR, "rahmen_helfer_state.json")
ALIAS_FILE = os.environ.get("RAHMEN_ALIAS_FILE", "/opt/bilderrahmen/rahmen_helfer_aliases.json")
PORT = 8079
MAX_FOTOS = 300
SMART_MAX = 400          # Kandidaten aus der Bildsuche, danach Relevanz-Grenze
MOTIV_OHNE_DB = int(os.environ.get("RAHMEN_MOTIV_OHNE_DB", "60"))   # Trefferzahl der Motivsuche, wenn keine Datenbank verfuegbar ist
MIN_AEHNLICHKEIT = 0.095  # SigLIP2 Text-Bild pro Foto (kalibriert an einer Beispielbibliothek: passendes Motiv bis ca. 0,13, Unsinn ca. 0,07)
MOTIV_EXISTIERT = 0.115   # bester Treffer der GANZEN Bibliothek muss darueber liegen (Unsinn: 0,097-0,105)
CLIP_MODELL = "ViT-B-16-SigLIP2__webli"
SERIE_SEKUNDEN = 10      # aus Serien nur ein Bild
ALBUM_PREFIX = "Rahmen: "
HELPER_MARK = "#rahmenhelfer"
EXCLUSIVE_RE = re.compile(r"#\S*nur\S*rahmen\S*", re.IGNORECASE)
ANY_MARK_RE = re.compile(r"#\S*rahmen\S*", re.IGNORECASE)
SYNC_CMD = "export $(cat /root/.immich_api_key | xargs) && /usr/bin/python3 /opt/bilderrahmen/bilderrahmen_sync_albums.py >> /var/log/bilderrahmen-sync-albums.log 2>&1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rahmen-helfer")
LOCK_FILE = os.path.join(STATE_DIR, "rahmen.lock")


class _Sperre:
    """Sperre ueber Threads UND Prozesse (Helfer + Webdienst teilen sich den Zustand)."""

    def __init__(self):
        self._t = threading.RLock()
        self._tiefe = 0
        self._f = None

    def __enter__(self):
        self._t.acquire()
        if self._tiefe == 0:
            os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
            self._f = open(LOCK_FILE, "a")
            fcntl.flock(self._f, fcntl.LOCK_EX)
        self._tiefe += 1
        return self

    def __exit__(self, *exc):
        self._tiefe -= 1
        if self._tiefe == 0:
            fcntl.flock(self._f, fcntl.LOCK_UN)
            self._f.close()
            self._f = None
        self._t.release()


LOCK = _Sperre()

# --------------------------------------------------------------------------- Immich

# Schluessel der angemeldeten Person (Immich-Anmeldung); sonst der Dienstschluessel aus der Umgebung
KEY_CTX = contextvars.ContextVar("rahmen_key", default=None)


def schluessel():
    return KEY_CTX.get() or KEY


def api(method, path, body=None, timeout=120):
    req = urllib.request.Request(IMMICH + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"x-api-key": schluessel(), "Content-Type": "application/json"})
    raw = urllib.request.urlopen(req, timeout=timeout).read()
    return json.loads(raw) if raw else None


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()

# --------------------------------------------------------------------------- Woerterbuecher

ORT_DE = {
    "osterreich": "Austria", "belgien": "Belgium", "bosnien": "Bosnia and Herzegovina", "kroatien": "Croatia",
    "danemark": "Denmark", "frankreich": "France", "deutschland": "Germany", "indien": "India", "italien": "Italy",
    "kenia": "Kenya", "niederlande": "Netherlands", "holland": "Netherlands", "polen": "Poland", "katar": "Qatar",
    "rumanien": "Romania", "serbien": "Serbia", "slowenien": "Slovenia", "schweden": "Sweden", "schweiz": "Switzerland",
    "thailand": "Thailand", "tansania": "United Republic of Tanzania", "usa": "United States of America",
    "amerika": "United States of America", "sardinien": "Sardinia", "bayern": "Bavaria", "hessen": "Hesse",
    "niedersachsen": "Lower Saxony", "nrw": "North Rhine-Westphalia", "nordrhein westfalen": "North Rhine-Westphalia",
    "baden wurttemberg": "Baden-Wurttemberg", "ligurien": "Liguria", "lombardei": "Lombardy", "piemont": "Piedmont",
    "flandern": "Flanders", "nordholland": "North Holland", "toskana": "Tuscany", "sizilien": "Sicily",
    "munchen": "Munich", "koln": "Cologne", "rom": "Rome", "venedig": "Venice", "mailand": "Milan",
    "belgrad": "Belgrade", "wien": "Vienna", "brussel": "Brussels", "kopenhagen": "Copenhagen",
    "zurich": "Zurich", "genf": "Geneva", "neapel": "Naples", "florenz": "Florence", "turin": "Turin",
}
# Suchsprachen: pro Sprache Monate, Zahlwoerter, Fuellwoerter, Jahreszeiten, Zeitausdruecke (Muster auf norm()-Text) usw.
# Neue Sprache = neuer Eintrag. "ort" uebersetzt Ortsnamen in die Schreibweise von Immich (englisch); bei en nicht noetig.
SPRACHEN = {
    "de": {
        "monate": {"januar": 1, "jan": 1, "februar": 2, "feb": 2, "marz": 3, "april": 4, "apr": 4, "mai": 5, "juni": 6,
                   "juli": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "oktober": 10, "okt": 10,
                   "november": 11, "nov": 11, "dezember": 12, "dez": 12},
        "zahlen": {"ein": 1, "einen": 1, "eine": 1, "zwei": 2, "drei": 3, "vier": 4, "funf": 5, "sechs": 6, "sieben": 7,
                   "acht": 8, "neun": 9, "zehn": 10, "zwolf": 12},
        "favorit": {"favoriten", "favorit", "lieblingsfotos", "lieblingsbilder", "schonsten", "schonste", "besten", "beste"},
        "fuell": set("""zeige zeig zeigt mir uns bitte mal bilder bild fotos foto photos photo diashow bilderrahmen rahmen alexa
siri hey sag von vom aus der die das den dem des und mit ohne im in am an auf bei zum zur ein eine einen einem
alle allen jahr jahre jahren gemacht aufgenommen gibt es was wo wie sind war waren auch nur noch neue neuen""".split()),
        "saison": {"fruhling": (3, 5), "fruhjahr": (3, 5), "sommer": (6, 8), "herbst": (9, 11), "winter": (12, 2)},
        "letzte": r"(?:letzte[nmrs]?|vergangene[nmrs]?)\s+(\d+|\w+)?\s*(tag|tage|tagen|woche|wochen|monat|monate|monaten|jahr|jahre|jahren)\b",
        "einheit": {"tag": 1, "woch": 7, "mona": 30, "jahr": 365},
        "dieses_jahr": (r"\b(dieses|diesem) jahr\b", ("dieses", "diesem", "jahr")),
        "letztes_jahr": (r"\bletztes jahr\b|\bletzten jahr\b|\bvorjahr\b", ("letztes", "letzten", "jahr", "vorjahr")),
        "bereich": (r"\b(bis|und|-)\b", ("bis",)),
        "weihnachten": (r"\b(weihnacht|weihnachten|heiligabend)\b", ("weihnacht", "weihnachten", "heiligabend")),
        "silvester": (r"\bsilvester\b", ("silvester",)),
        "stop": {"zeige", "zeig", "bilder", "fotos", "bitte", "mir", "von", "alexa", "bilderrahmen"},
        "ort": ORT_DE, "clip": "de",
    },
    "en": {
        "monate": {"january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5,
                   "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
                   "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12},
        "zahlen": {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                   "eight": 8, "nine": 9, "ten": 10, "twelve": 12},
        "favorit": {"favourites", "favorites", "favourite", "favorite", "best", "nicest", "prettiest"},
        "fuell": set("""show shows me us please photo photos picture pictures pics pic slideshow frame alexa siri hey
of the a an and with without in on at to for from all every year years taken made there is are was were also only still
new latest recent my our""".split()),
        "saison": {"spring": (3, 5), "summer": (6, 8), "autumn": (9, 11), "fall": (9, 11), "winter": (12, 2)},
        "letzte": r"(?:last|past|previous)\s+(\d+|\w+)?\s*(day|days|week|weeks|month|months|year|years)\b",
        "einheit": {"day": 1, "week": 7, "month": 30, "year": 365},
        "dieses_jahr": (r"\bthis year\b", ("this", "year")),
        "letztes_jahr": (r"\blast year\b|\bprevious year\b", ("last", "previous", "year")),
        "bereich": (r"\b(to|until|through|and|-)\b", ("to", "until", "through", "between")),
        "weihnachten": (r"\b(christmas|xmas)\b", ("christmas", "xmas", "eve")),
        "silvester": (r"\b(new year s eve|new years eve|nye)\b", ("new", "year", "s", "years", "eve", "nye")),
        "stop": {"show", "me", "photos", "pictures", "please", "of", "alexa", "frame"},
        "ort": {}, "clip": "en",
    },
}
SPRACHEN["es"] = {
    "monate": {"enero": 1, "ene": 1, "febrero": 2, "feb": 2, "marzo": 3, "mar": 3, "abril": 4, "abr": 4, "mayo": 5, "junio": 6, "jun": 6, "julio": 7, "jul": 7,
               "agosto": 8, "ago": 8, "septiembre": 9, "setiembre": 9, "sep": 9, "sept": 9, "octubre": 10, "oct": 10, "noviembre": 11, "nov": 11, "diciembre": 12, "dic": 12},
    "zahlen": {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "doce": 12},
    "favorit": {"favoritas", "favoritos", "favorita", "favorito", "mejores", "mejor", "preferidas", "preferidos"},
    "fuell": set("""muestrame muestra mostrar ensename ensena por favor fotos foto imagenes imagen fotografias fotografia presentacion marco alexa siri hey de del la las el los lo
un una unos unas y con sin en a al para desde hasta todas todos todo ano anos tomadas hechas hay es son era eran tambien solo aun nuevas nuevos mis nuestras""".split()),
    "saison": {"primavera": (3, 5), "verano": (6, 8), "otono": (9, 11), "invierno": (12, 2)},
    "letzte": r"(?:ultim[oa]s?|pasad[oa]s?)\s+(\d+|\w+)?\s*(dia|dias|semana|semanas|mes|meses|ano|anos)\b",
    "einheit": {"dia": 1, "semana": 7, "mes": 30, "ano": 365},
    "dieses_jahr": (r"\beste ano\b", ("este", "ano")),
    "letztes_jahr": (r"\bano pasado\b|\bultimo ano\b", ("ano", "pasado", "ultimo")),
    "bereich": (r"\b(hasta|a|y|-)\b", ("hasta", "entre", "desde")),
    "weihnachten": (r"\b(navidad|navidades|nochebuena)\b", ("navidad", "navidades", "nochebuena")),
    "silvester": (r"\b(nochevieja|fin de ano)\b", ("nochevieja", "fin", "de", "ano")),
    "stop": {"muestrame", "muestra", "fotos", "por", "favor", "alexa", "marco"},
    "ort": {"espana": "Spain", "alemania": "Germany", "francia": "France", "italia": "Italy", "reino unido": "United Kingdom", "estados unidos": "United States of America",
            "paises bajos": "Netherlands", "holanda": "Netherlands", "suiza": "Switzerland", "austria": "Austria", "belgica": "Belgium", "grecia": "Greece", "turquia": "Turkey",
            "portugal": "Portugal", "irlanda": "Ireland", "polonia": "Poland", "croacia": "Croatia", "mexico": "Mexico", "japon": "Japan", "viena": "Vienna", "roma": "Rome",
            "venecia": "Venice", "milan": "Milan", "florencia": "Florence", "napoles": "Naples", "munich": "Munich", "colonia": "Cologne", "londres": "London", "lisboa": "Lisbon",
            "cerdena": "Sardinia", "sicilia": "Sicily", "toscana": "Tuscany", "bruselas": "Brussels", "ginebra": "Geneva", "zurich": "Zurich", "copenhague": "Copenhagen"},
    "clip": "es",
}
SPRACHEN["fr"] = {
    "monate": {"janvier": 1, "janv": 1, "fevrier": 2, "fevr": 2, "mars": 3, "avril": 4, "avr": 4, "mai": 5, "juin": 6, "juillet": 7, "juil": 7, "aout": 8,
               "septembre": 9, "sept": 9, "octobre": 10, "oct": 10, "novembre": 11, "nov": 11, "decembre": 12, "dec": 12},
    "zahlen": {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "douze": 12},
    "favorit": {"favoris", "favorites", "favori", "favorite", "meilleures", "meilleurs", "meilleur", "preferees", "preferes"},
    "fuell": set("""montre montrez moi nous affiche afficher photo photos image images diaporama cadre alexa siri hey de du des la le les l d un une et avec sans en dans a au aux pour
depuis jusqu toutes tous tout annee annees prises faites il y a est sont etait aussi seulement encore nouvelles mes nos""".split()),
    "saison": {"printemps": (3, 5), "ete": (6, 8), "automne": (9, 11), "hiver": (12, 2)},
    "letzte": r"(\d+|\w+)?\s*(?:derni(?:er|ere|eres|ers)|passe[es]?s?)\s+(?:\d+\s+)?(jour|jours|semaine|semaines|mois|an|ans|annee|annees)\b",
    "einheit": {"jour": 1, "semaine": 7, "mois": 30, "an": 365},
    "dieses_jahr": (r"\bcette annee\b", ("cette", "annee")),
    "letztes_jahr": (r"\bl annee derniere\b|\bannee derniere\b|\bannee passee\b", ("annee", "derniere", "passee", "l")),
    "bereich": (r"\b(a|jusqu|et|-)\b", ("jusqu", "entre")),
    "weihnachten": (r"\b(noel)\b", ("noel",)),
    "silvester": (r"\b(nouvel an|saint sylvestre|reveillon)\b", ("nouvel", "an", "saint", "sylvestre", "reveillon")),
    "stop": {"montre", "moi", "photos", "photo", "alexa", "cadre"},
    "ort": {"espagne": "Spain", "allemagne": "Germany", "france": "France", "italie": "Italy", "royaume uni": "United Kingdom", "etats unis": "United States of America",
            "pays bas": "Netherlands", "hollande": "Netherlands", "suisse": "Switzerland", "autriche": "Austria", "belgique": "Belgium", "grece": "Greece", "turquie": "Turkey",
            "irlande": "Ireland", "pologne": "Poland", "croatie": "Croatia", "mexique": "Mexico", "japon": "Japan", "vienne": "Vienna", "rome": "Rome", "venise": "Venice",
            "milan": "Milan", "florence": "Florence", "naples": "Naples", "munich": "Munich", "cologne": "Cologne", "londres": "London", "lisbonne": "Lisbon",
            "sardaigne": "Sardinia", "sicile": "Sicily", "toscane": "Tuscany", "bruxelles": "Brussels", "geneve": "Geneva", "copenhague": "Copenhagen"},
    "clip": "fr",
}
SPRACHEN["nl"] = {
    "monate": {"januari": 1, "jan": 1, "februari": 2, "feb": 2, "maart": 3, "mrt": 3, "april": 4, "apr": 4, "mei": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7,
               "augustus": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "oktober": 10, "okt": 10, "november": 11, "nov": 11, "december": 12, "dec": 12},
    "zahlen": {"een": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6, "zeven": 7, "acht": 8, "negen": 9, "tien": 10, "twaalf": 12},
    "favorit": {"favorieten", "favoriet", "beste", "mooiste", "leukste"},
    "fuell": set("""toon laat zien me ons alsjeblieft graag foto fotos plaatjes afbeeldingen diavoorstelling lijst fotolijst alexa siri hey van de het een en met zonder in op aan bij
voor vanaf tot alle alles jaar jaren genomen gemaakt er is zijn was waren ook alleen nog nieuwe mijn onze""".split()),
    "saison": {"lente": (3, 5), "voorjaar": (3, 5), "zomer": (6, 8), "herfst": (9, 11), "najaar": (9, 11), "winter": (12, 2)},
    "letzte": r"(?:laatste|afgelopen|vorige)\s+(\d+|\w+)?\s*(dag|dagen|week|weken|maand|maanden|jaar|jaren)\b",
    "einheit": {"dagen": 1, "dag": 1, "weken": 7, "week": 7, "maanden": 30, "maand": 30, "jaren": 365, "jaar": 365},
    "dieses_jahr": (r"\bdit jaar\b", ("dit", "jaar")),
    "letztes_jahr": (r"\bvorig jaar\b|\bvorige jaar\b|\blaatste jaar\b", ("vorig", "vorige", "laatste", "jaar")),
    "bereich": (r"\b(tot|tot en met|en|-)\b", ("tot", "tussen", "met")),
    "weihnachten": (r"\b(kerst|kerstmis|kerstavond)\b", ("kerst", "kerstmis", "kerstavond")),
    "silvester": (r"\b(oud en nieuw|oudejaarsavond|oudjaar)\b", ("oud", "en", "nieuw", "oudejaarsavond", "oudjaar")),
    "stop": {"toon", "laat", "zien", "me", "fotos", "foto", "alexa", "lijst"},
    "ort": {"spanje": "Spain", "duitsland": "Germany", "frankrijk": "France", "italie": "Italy", "verenigd koninkrijk": "United Kingdom", "verenigde staten": "United States of America",
            "nederland": "Netherlands", "zwitserland": "Switzerland", "oostenrijk": "Austria", "belgie": "Belgium", "griekenland": "Greece", "turkije": "Turkey",
            "ierland": "Ireland", "polen": "Poland", "kroatie": "Croatia", "mexico": "Mexico", "japan": "Japan", "wenen": "Vienna", "rome": "Rome", "venetie": "Venice",
            "milaan": "Milan", "florence": "Florence", "napels": "Naples", "munchen": "Munich", "keulen": "Cologne", "londen": "London", "lissabon": "Lisbon",
            "sardinie": "Sardinia", "sicilie": "Sicily", "toscane": "Tuscany", "brussel": "Brussels", "geneve": "Geneva", "kopenhagen": "Copenhagen"},
    "clip": "nl",
}
# Rueckwaertskompatible Namen (deutsch)
MONATE, ZAHLEN, FAVORIT_WORTE, FUELL, SAISON = (SPRACHEN["de"][k] for k in ("monate", "zahlen", "favorit", "fuell", "saison"))

# --------------------------------------------------------------------------- Parser

def lade_personen():
    ppl = api("GET", "/people?withHidden=false&size=1000")["people"]
    named = [(p["name"].strip(), p["id"]) for p in ppl if p.get("name", "").strip()]
    alias = {}
    if os.path.exists(ALIAS_FILE):
        alias = {norm(k): v for k, v in json.load(open(ALIAS_FILE)).items()}
    for eintrag in os.environ.get("RAHMEN_WEB_ALIASE", "").split(";"):       # "oma=Erika Muster; opa=Karl Muster"
        k, _, v = eintrag.partition("=")
        if k.strip() and v.strip():
            alias[norm(k)] = v.strip()
    return named, alias


def lade_orte():
    orte = {}
    for typ in ("country", "state", "city"):
        for name in api("GET", f"/search/suggestions?type={typ}") or []:
            if name:
                orte.setdefault(norm(name), (typ, name))
    return orte


def jahr_fenster(j):
    return (dt.datetime(j, 1, 1), dt.datetime(j + 1, 1, 1))


def zeit_parsen(text, rest, lang="de"):
    """Liefert Liste von (von, bis) Zeitfenstern oder [] und entfernt erkannte Woerter aus rest."""
    L = SPRACHEN[lang]
    heute = dt.datetime.now()
    t = norm(text)
    fenster = []

    def weg(*worte):
        for w in worte:
            if w in rest:
                rest.remove(w)

    def trifft(schluessel):
        muster, worte = L[schluessel]
        return re.search(muster, t), worte

    if lang == "en":                                   # "last year" = voriges Kalenderjahr (vor "last N <Einheit>")
        m, worte = trifft("letztes_jahr")
        if m:
            weg(*worte)
            return [jahr_fenster(heute.year - 1)]
    m = re.search(L["letzte"], t)
    if m:
        n = m.group(1)
        n = int(n) if n and n.isdigit() else L["zahlen"].get(n or "", 1)
        einheit = m.group(2)
        tage = L["einheit"][next(k for k in L["einheit"] if einheit.startswith(k))]
        fenster = [(heute - dt.timedelta(days=n * tage), heute + dt.timedelta(days=1))]
        weg(*m.group(0).split())
        return fenster
    m, worte = trifft("dieses_jahr")
    if m:
        weg(*worte)
        return [jahr_fenster(heute.year)]
    m, worte = trifft("letztes_jahr")
    if m:
        weg(*worte)
        return [jahr_fenster(heute.year - 1)]

    jahre = [int(j) for j in re.findall(r"\b(19[5-9]\d|20[0-4]\d)\b", t)]
    for j in jahre:
        weg(str(j))
    m, worte = trifft("bereich")
    bereich = len(jahre) >= 2 and m
    if bereich:
        weg(*worte)
        jahre = list(range(min(jahre), max(jahre) + 1))
    alle_jahre = jahre or list(range(1990, heute.year + 1))

    m, worte = trifft("weihnachten")
    if m:
        weg(*worte)
        return [(dt.datetime(j, 12, 20), dt.datetime(j, 12, 28)) for j in alle_jahre]
    m, worte = trifft("silvester")
    if m:
        weg(*worte)
        return [(dt.datetime(j, 12, 31, 12), dt.datetime(j + 1, 1, 1, 8)) for j in alle_jahre]
    for wort, (a, b) in L["saison"].items():
        if re.search(rf"\b{wort}\b", t):
            weg(wort)
            res = []
            for j in alle_jahre:
                if a <= b:
                    res.append((dt.datetime(j, a, 1), dt.datetime(j, b, calendar.monthrange(j, b)[1]) + dt.timedelta(days=1)))
                else:
                    res.append((dt.datetime(j, a, 1), dt.datetime(j + 1, b, calendar.monthrange(j + 1, b)[1]) + dt.timedelta(days=1)))
            return res
    for wort, mon in L["monate"].items():
        if re.search(rf"\b{wort}\b", t):
            weg(wort)
            return [(dt.datetime(j, mon, 1), dt.datetime(j, mon, calendar.monthrange(j, mon)[1]) + dt.timedelta(days=1)) for j in alle_jahre]
    if jahre:
        return [(dt.datetime(min(jahre), 1, 1), dt.datetime(max(jahre) + 1, 1, 1))]
    return []


def parse(text, personen, alias, orte, lang="de"):
    L = SPRACHEN.get(lang) or SPRACHEN["de"]
    lang = lang if lang in SPRACHEN else "de"
    t = norm(text)
    rest = t.split()
    erg = {"personen": [], "zeit": [], "ort": None, "favoriten": False, "motiv": "", "rueckfrage": None, "sprache": lang}

    # Personen: Spitznamen, dann volle Namen (laengste zuerst), dann eindeutige Namensteile
    def entferne(phrase):
        teile = phrase.split()
        for i in range(len(rest) - len(teile) + 1):
            if rest[i:i + len(teile)] == teile:
                del rest[i:i + len(teile)]
                return True
        return False

    by_norm = {}
    for name, pid in personen:
        by_norm.setdefault(norm(name), []).append((name, pid))
    for a, ziel in sorted(alias.items(), key=lambda x: -len(x[0])):
        if entferne(a):
            for name, pid in personen:
                if norm(name) == norm(ziel):
                    erg["personen"].append((name, pid))
    for n in sorted(by_norm, key=len, reverse=True):
        while entferne(n):
            treffer = by_norm[n]
            if len(treffer) > 1:
                erg["rueckfrage"] = f"Es gibt mehrere Personen namens {treffer[0][0]}. Bitte in Immich eindeutig benennen."
            erg["personen"].append(treffer[0])
    for wort in list(rest):
        if wort in L["fuell"] or len(wort) < 3 or wort in L["ort"] or wort in orte or wort in L["monate"] or wort in L["saison"]:
            continue
        kandidaten = [(name, pid) for name, pid in personen if wort in norm(name).split()]
        if len(kandidaten) > 1:
            erg["rueckfrage"] = f"Welche Person meinst du mit \"{wort}\"? " + " oder ".join(sorted({k[0] for k in kandidaten}))
            rest.remove(wort)
        elif len(kandidaten) == 1:
            erg["personen"].append(kandidaten[0])
            rest.remove(wort)

    # Zeit
    erg["zeit"] = zeit_parsen(text, rest, lang)

    # Ort (Phrasen bis 3 Woerter, DE-Uebersetzung)
    for laenge in (3, 2, 1):
        for i in range(len(rest) - laenge + 1):
            phrase = " ".join(rest[i:i + laenge])
            kandidat = L["ort"].get(phrase)
            schluessel = norm(kandidat) if kandidat else phrase
            if schluessel in orte and not erg["ort"]:
                erg["ort"] = orte[schluessel]
                del rest[i:i + laenge]
                break
        if erg["ort"]:
            break

    # Favoriten
    for w in list(rest):
        if w in L["favorit"]:
            erg["favoriten"] = True
            rest.remove(w)

    # Motiv = was uebrig bleibt (ohne Fuellwoerter am Rand)
    inhalt = [w for w in rest if w not in L["fuell"] and not w.isdigit()]
    if inhalt:
        # Originalschreibweise (mit Umlauten) aus dem Text holen
        orig = [w for w in re.findall(r"[\wäöüÄÖÜß]+", text) if norm(w) in rest and norm(w) not in L["stop"]]
        while orig and norm(orig[0]) in L["fuell"]:
            orig.pop(0)
        while orig and norm(orig[-1]) in L["fuell"]:
            orig.pop()
        erg["motiv"] = " ".join(orig) or " ".join(inhalt)
    return erg

# --------------------------------------------------------------------------- Suche

def filter_body(erg, fenster):
    body = {"type": "IMAGE", "withExif": True}
    if erg["personen"]:
        body["personIds"] = [pid for _, pid in erg["personen"]]
    if fenster:
        body["takenAfter"] = fenster[0].strftime("%Y-%m-%dT%H:%M:%S.000Z")
        body["takenBefore"] = fenster[1].strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if erg["ort"]:
        body[erg["ort"][0]] = erg["ort"][1]
    if erg["favoriten"]:
        body["isFavorite"] = True
    return body


def ml_url():
    if os.environ.get("RAHMEN_ML_URL"):          # Container: ueber das Docker-Netz
        return os.environ["RAHMEN_ML_URL"]
    ip = subprocess.run(["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                         "immich_machine_learning"], capture_output=True, text=True).stdout.strip()
    return f"http://{ip}:3003/predict"


def text_vektor(text, lang="de"):
    bnd = uuid.uuid4().hex
    entries = json.dumps({"clip": {"textual": {"modelName": CLIP_MODELL, "options": {"language": SPRACHEN.get(lang, SPRACHEN["de"])["clip"]}}}})
    body = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"entries\"\r\n\r\n{entries}\r\n"
            f"--{bnd}\r\nContent-Disposition: form-data; name=\"text\"\r\n\r\n{text}\r\n--{bnd}--\r\n").encode()
    req = urllib.request.Request(ml_url(), data=body, headers={"Content-Type": f"multipart/form-data; boundary={bnd}"})
    v = json.load(urllib.request.urlopen(req, timeout=120))["clip"]
    return json.loads(v) if isinstance(v, str) else v


def relevante(ids, motiv, lang="de"):
    """Behaelt nur Fotos, deren Aehnlichkeit zum Motiv ueber MIN_AEHNLICHKEIT liegt (nur lesender DB-Zugriff)."""
    if not ids:
        return set()
    if not (os.environ.get("RAHMEN_DB_DSN") or shutil.which("docker")):
        # Ohne Datenbankzugang gibt die Immich-API keine Aehnlichkeitswerte her: die besten Treffer der Rangliste nehmen
        log.info("Motiv '%s': keine Datenbank, nehme die ersten %d Treffer der Rangliste", motiv, MOTIV_OHNE_DB)
        return set(ids[:MOTIV_OHNE_DB])
    vec = "[" + ",".join(map(str, text_vektor(motiv, lang))) + "]"

    def lesen(sql):
        if os.environ.get("RAHMEN_DB_DSN"):      # Container: eigene Nur-Lese-Rolle statt docker exec
            import psycopg
            with psycopg.connect(os.environ["RAHMEN_DB_DSN"], connect_timeout=10, autocommit=True) as c:
                zeilen = c.execute(sql).fetchall()
            return [str(v) for z in zeilen for v in z]
        out = subprocess.run(["docker", "exec", "-i", "immich_postgres", "psql", "-U", "postgres", "-d", "immich", "-tA",
                              "-v", "ON_ERROR_STOP=1", "-c", "set default_transaction_read_only = on;", "-c", sql],
                             capture_output=True, text=True)
        if out.returncode:
            raise RuntimeError("Relevanzpruefung fehlgeschlagen: " + out.stderr[:200])
        return out.stdout.split()

    bester = lesen(f"select 1 - (s.embedding <=> '{vec}') from smart_search s join asset a on a.id = s.\"assetId\" "
                   f"where a.\"deletedAt\" is null order by s.embedding <=> '{vec}' limit 1;")
    if not bester or float(bester[-1]) < MOTIV_EXISTIERT:
        log.info("Motiv '%s' existiert nicht (bester Treffer %s)", motiv, bester[-1] if bester else "-")
        return set()
    liste = ",".join(f"'{i}'" for i in ids if re.fullmatch(r"[0-9a-f-]{36}", i))
    zeilen = lesen(f"select \"assetId\" from smart_search where \"assetId\" in ({liste}) "
                   f"and 1 - (embedding <=> '{vec}') >= {MIN_AEHNLICHKEIT};")
    return {z for z in zeilen if re.fullmatch(r"[0-9a-f-]{36}", z)}


def suche(erg):
    fenster_liste = erg["zeit"] or [None]
    gefunden = {}
    for fenster in fenster_liste:
        body = filter_body(erg, fenster)
        if erg["motiv"]:
            seite, geholt = 1, 0
            while seite and geholt < SMART_MAX:
                d = api("POST", "/search/smart", {**body, "query": erg["motiv"], "size": 100, "page": seite, **({"language": SPRACHEN[erg["sprache"]]["clip"]} if erg.get("sprache", "de") != "de" else {})})
                for a in d["assets"]["items"]:
                    gefunden.setdefault(a["id"], a)
                geholt += len(d["assets"]["items"])
                seite = int(d["assets"]["nextPage"]) if d["assets"].get("nextPage") else None
            passend = relevante(list(gefunden), erg["motiv"], erg.get("sprache", "de"))
            gefunden = {k: v for k, v in gefunden.items() if k in passend}
        else:
            seite = 1
            while seite:
                d = api("POST", "/search/metadata", {**body, "size": 1000, "page": seite})
                for a in d["assets"]["items"]:
                    gefunden.setdefault(a["id"], a)
                seite = int(d["assets"]["nextPage"]) if d["assets"].get("nextPage") else None
    return list(gefunden.values())


def ist_screenshot(a):
    e = a.get("exifInfo") or {}
    return "screenshot" in (a.get("originalFileName") or "").lower() or (
        not e.get("make") and (a.get("originalFileName") or "").lower().endswith(".png"))


def auswahl(assets, maximum=None):
    maximum = maximum or MAX_FOTOS

    def zeit(a):
        return a.get("localDateTime") or a.get("fileCreatedAt") or ""

    kandidaten = sorted((a for a in assets if a.get("type") == "IMAGE" and not ist_screenshot(a)), key=zeit)
    ohne_serie, letzte = [], None
    for a in kandidaten:
        try:
            z = dt.datetime.fromisoformat(zeit(a).replace("Z", "+00:00"))
        except ValueError:
            z = None
        if letzte and z and abs((z - letzte).total_seconds()) < SERIE_SEKUNDEN:
            continue
        ohne_serie.append(a)
        letzte = z or letzte
    if len(ohne_serie) <= maximum:
        return ohne_serie
    fav = [a for a in ohne_serie if a.get("isFavorite")]
    rest = [a for a in ohne_serie if not a.get("isFavorite")]
    platz = max(maximum - len(fav), 0)
    schritt = len(rest) / platz if platz else 0
    gleichmaessig = [rest[int(i * schritt)] for i in range(platz)] if platz else []
    return sorted((fav[:maximum] + gleichmaessig)[:maximum], key=zeit)

# --------------------------------------------------------------------------- Zustand / Alben

def lade_state():
    try:
        return json.load(open(STATE_FILE))
    except (OSError, ValueError):
        return {"album": None, "wunsch": None, "pausiert": {}, "verlauf": [], "gemerkt": []}


def speichere_state(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    json.dump(s, open(tmp, "w"), indent=1, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


VERLAUF_MAX = 5
PLATZHALTER = "— auswählen —"


def in_verlauf(state, text, anzahl):
    v = [e for e in state.get("verlauf", []) if norm(e["text"]) != norm(text)]
    state["verlauf"] = [{"text": text.strip(), "anzahl": anzahl, "zeit": dt.datetime.now().isoformat(timespec="minutes")}] + v[:VERLAUF_MAX - 1]


def liste():
    s = lade_state()
    gemerkt = s.get("gemerkt", [])
    verlauf = [e["text"] for e in s.get("verlauf", []) if norm(e["text"]) not in {norm(g) for g in gemerkt}]
    return {"ok": True, "gemerkt": gemerkt, "verlauf": verlauf, "aktuell": s.get("wunsch"),
            "optionen": [PLATZHALTER] + [f"⭐ {g}" for g in gemerkt] + [f"🕘 {v}" for v in verlauf]}


def merken(text=None):
    with LOCK:
        s = lade_state()
        text = (text or s.get("wunsch") or "").strip()
        if not text:
            return {"ok": False, "nachricht": "Es läuft gerade kein Wunsch, den ich merken könnte."}
        if norm(text) not in {norm(g) for g in s.setdefault("gemerkt", [])}:
            s["gemerkt"].append(text)
            speichere_state(s)
        return {"ok": True, "nachricht": f"Gemerkt: „{text}“ – steht jetzt unter „Meine Diashows“."}


def vergessen(text=None):
    with LOCK:
        s = lade_state()
        text = (text or s.get("wunsch") or "").strip()
        vorher = len(s.get("gemerkt", []))
        s["gemerkt"] = [g for g in s.get("gemerkt", []) if norm(g) != norm(text)]
        s["verlauf"] = [e for e in s.get("verlauf", []) if norm(e["text"]) != norm(text)]
        speichere_state(s)
        return {"ok": True, "nachricht": f"„{text}“ entfernt." if len(s["gemerkt"]) < vorher else f"„{text}“ war nicht gemerkt (aus dem Verlauf entfernt)."}


def ist_helfer_album(a):
    return a["albumName"].startswith(ALBUM_PREFIX) and HELPER_MARK in (a.get("description") or "")


def sync_anstossen():
    if os.environ.get("RAHMEN_SYNC_URL"):        # Container: der Helfer auf dem Host fuehrt die Synchronisation aus
        try:
            req = urllib.request.Request(os.environ["RAHMEN_SYNC_URL"], method="POST", data=b"{}",
                                         headers={"X-Rahmen-Token": os.environ.get("RAHMEN_SYNC_TOKEN", ""),
                                                  "Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=15).read()
        except Exception as e:  # noqa: BLE001 - Album ist angelegt; Sync laeuft spaetestens im 3-Minuten-Takt
            log.warning("Sync-Aufruf fehlgeschlagen: %s", e)
        return
    subprocess.Popen(["/bin/bash", "-c", SYNC_CMD])


def beschreibe(erg, anzahl):
    teile = []
    if erg["personen"]:
        teile.append(" und ".join(n for n, _ in erg["personen"]))
    if erg["motiv"]:
        teile.append(f"\"{erg['motiv']}\"")
    if erg["ort"]:
        teile.append(f"in {erg['ort'][1]}")
    if erg["zeit"]:
        a, b = erg["zeit"][0][0], erg["zeit"][-1][1] - dt.timedelta(seconds=1)
        teile.append(f"aus {a.year}" if a.year == b.year and len(erg["zeit"]) == 1 and (b - a).days > 300
                     else f"vom {a:%d.%m.%Y} bis {b:%d.%m.%Y}" if len(erg["zeit"]) == 1 else f"({len(erg['zeit'])} Zeitraeume)")
    if erg["favoriten"]:
        teile.append("nur Favoriten")
    return f"{anzahl} Fotos" + (" – " + ", ".join(teile) if teile else "")


def album_anzeigen(name, ids, verlauf=False, reihenfolge="alt"):
    """Legt das temporaere Helfer-Album fuer genau diese Fotos an und stellt es exklusiv auf den Rahmen.
    Das vorherige Helfer-Album wird entfernt, andere exklusive Alben werden pausiert. Gibt die Zahl der
    tatsaechlich aufgenommenen Fotos zurueck (Fotos, auf die der Schluessel keinen Zugriff hat, fallen weg)."""
    name = name.strip()
    with LOCK:
        state = lade_state()
        neu = api("POST", "/albums", {"albumName": (ALBUM_PREFIX + name)[:100],
                                      "description": f"#nurrahmen {HELPER_MARK} – vom Bilderrahmen-Helfer angelegt "
                                                     f"({dt.datetime.now():%d.%m.%Y %H:%M}). Wird beim naechsten Wunsch "
                                                     f"automatisch entfernt, die Fotos selbst bleiben erhalten."})
        ok = 0
        for i in range(0, len(ids), 500):
            res = api("PUT", f"/albums/{neu['id']}/assets", {"ids": ids[i:i + 500]}) or []
            ok += sum(1 for r in res if r.get("success") or r.get("error") == "duplicate")
        if not ok:
            api("DELETE", f"/albums/{neu['id']}")
            raise ValueError("Keines der Fotos konnte in das Rahmen-Album aufgenommen werden")
        for a in api("GET", "/albums"):
            if a["id"] == neu["id"]:
                continue
            if ist_helfer_album(a):
                api("DELETE", f"/albums/{a['id']}")
                log.info("altes Helfer-Album entfernt: %s", a["albumName"])
            elif EXCLUSIVE_RE.search(a.get("description") or ""):
                state["pausiert"].setdefault(a["id"], a.get("description") or "")
                api("PATCH", f"/albums/{a['id']}", {"description": ANY_MARK_RE.sub("", a.get("description") or "").strip()})
                log.info("exklusives Album pausiert: %s", a["albumName"])
        state.update({"reihenfolge": reihenfolge if reihenfolge in REIHENFOLGEN else "alt", "album": neu["id"], "wunsch": name, "seit": dt.datetime.now().isoformat(timespec="seconds"), "anzahl": ok})
        if verlauf:
            in_verlauf(state, name, ok)
        speichere_state(state)
    sync_anstossen()
    return ok


REIHENFOLGEN = ("alt", "neu", "zufall")      # alt = aeltestes zuerst (Standard), neu = neuestes zuerst, zufall = gemischt


def reihenfolge_setzen(r):
    """Aendert die Anzeige-Reihenfolge der laufenden Wunsch-Show (der Sync schreibt sie als album_order in die Kiosk-Konfiguration)."""
    if r not in REIHENFOLGEN:
        raise ValueError("Unbekannte Reihenfolge")
    with LOCK:
        state = lade_state()
        state["reihenfolge"] = r
        speichere_state(state)
    sync_anstossen()


def zeige(text, dry=False):
    text = re.sub(r"^\s*(⭐|🕘)\s*", "", text or "")
    personen, alias = lade_personen()
    erg = parse(text, personen, alias, lade_orte())
    info = {"personen": [n for n, _ in erg["personen"]], "zeit": [(a.date().isoformat(), b.date().isoformat()) for a, b in erg["zeit"][:5]],
            "zeitraeume": len(erg["zeit"]), "ort": erg["ort"][1] if erg["ort"] else None, "favoriten": erg["favoriten"], "motiv": erg["motiv"]}
    if erg["rueckfrage"]:
        return {"ok": False, "nachricht": erg["rueckfrage"], "erkannt": info}
    if not any([erg["personen"], erg["zeit"], erg["ort"], erg["favoriten"], erg["motiv"]]):
        return {"ok": False, "nachricht": "Das habe ich nicht verstanden. Beispiel: " + BEISPIEL_TEXT + ".", "erkannt": info}
    fotos = auswahl(suche(erg))
    hinweis = ""
    if not fotos and erg["favoriten"]:
        erg["favoriten"] = False
        fotos = auswahl(suche(erg))
        hinweis = " (keine Favoriten markiert – ich zeige alle passenden)"
    beschreibung = beschreibe(erg, len(fotos)) + hinweis
    if not fotos:
        return {"ok": False, "nachricht": "Dazu habe ich keine Fotos gefunden. Der Bilderrahmen bleibt wie er ist.", "erkannt": info}
    if dry:
        return {"ok": True, "nachricht": f"(Test) {beschreibung}", "erkannt": info, "anzahl": len(fotos)}

    ids = [a["id"] for a in fotos]
    anzahl = album_anzeigen(text, ids, verlauf=True)
    log.info("Wunsch '%s' -> %s", text, beschreibung)
    return {"ok": True, "nachricht": f"{beschreibung} – läuft gleich auf dem Bilderrahmen.", "erkannt": info, "anzahl": anzahl}


def normal():
    with LOCK:
        state = lade_state()
        for a in api("GET", "/albums"):
            if ist_helfer_album(a):
                api("DELETE", f"/albums/{a['id']}")
        wieder = 0
        for aid, beschr in state.get("pausiert", {}).items():
            try:
                api("PATCH", f"/albums/{aid}", {"description": beschr})
                wieder += 1
            except urllib.error.HTTPError:
                log.warning("pausiertes Album %s nicht mehr vorhanden", aid)
        state.update({"album": None, "wunsch": None, "pausiert": {}})
        speichere_state(state)
    sync_anstossen()
    return {"ok": True, "nachricht": "Der Bilderrahmen zeigt wieder das normale Programm." + (f" ({wieder} Album/Alben wieder aktiv)" if wieder else "")}


def status():
    s = lade_state()
    if s.get("album"):
        return {"ok": True, "nachricht": f"Läuft gerade: \"{s['wunsch']}\" ({s.get('anzahl', '?')} Fotos, seit {s.get('seit', '?')})", **s}
    return {"ok": True, "nachricht": "Der Bilderrahmen zeigt das normale Programm.", **s}

# --------------------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    def _antwort(self, code, daten):
        roh = json.dumps(daten, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def _handle(self):
        teile = urllib.parse.urlparse(self.path)
        q = {k: v[-1] for k, v in urllib.parse.parse_qs(teile.query).items()}
        if self.command == "POST" and int(self.headers.get("Content-Length") or 0):
            roh = self.rfile.read(int(self.headers["Content-Length"]))
            try:
                q.update(json.loads(roh))
            except ValueError:
                q.update({k: v[-1] for k, v in urllib.parse.parse_qs(roh.decode()).items()})
        token = open(TOKEN_FILE).read().strip()
        if (self.headers.get("X-Rahmen-Token") or q.get("token")) != token:
            return self._antwort(401, {"ok": False, "nachricht": "nicht berechtigt"})
        try:
            if teile.path == "/zeige":
                return self._antwort(200, zeige(str(q.get("text", "")), dry=str(q.get("dry", "")) in ("1", "true", "True")))
            if teile.path == "/normal":
                return self._antwort(200, normal())
            if teile.path == "/status":
                return self._antwort(200, status())
            if teile.path == "/liste":
                return self._antwort(200, liste())
            if teile.path == "/merken":
                return self._antwort(200, merken(q.get("text")))
            if teile.path == "/vergessen":
                return self._antwort(200, vergessen(q.get("text")))
            if teile.path == "/sync":
                sync_anstossen()
                return self._antwort(200, {"ok": True, "nachricht": "Synchronisation angestossen"})
            if teile.path == "/personen":
                return self._antwort(200, {"ok": True, "personen": sorted(n for n, _ in lade_personen()[0])})
            return self._antwort(404, {"ok": False, "nachricht": "unbekannt"})
        except Exception as e:  # noqa: BLE001 - Fehler an den Aufrufer melden statt abstuerzen
            log.exception("Fehler bei %s", self.path)
            return self._antwort(500, {"ok": False, "nachricht": f"Fehler: {e}"})

    do_GET = do_POST = _handle

    def log_message(self, fmt, *args):
        log.info("%s %s %s", self.address_string(), self.command, urllib.parse.urlparse(self.path).path)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--test":
        print(json.dumps(zeige(" ".join(sys.argv[2:]), dry=True), ensure_ascii=False, indent=1))
    else:
        ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
