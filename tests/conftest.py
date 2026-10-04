"""Testrahmen: laedt die App mit frei waehlbarer Umgebung und einem kleinen Schein-Immich (kein Netzwerk, keine echten Fotos)."""
import datetime as dt
import importlib
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

PERSONEN = [("Anna Muster", "11111111-1111-4111-8111-111111111111"), ("Opa Karl", "22222222-2222-4222-8222-222222222222")]
LAENDER = ["Germany", "Italy", "Serbia"]


def _id(n):
    return f"{n:08x}-0000-4000-8000-{n:012x}"


def _asset(n, jahr, monat, typ="IMAGE", land="Italy"):
    d = dt.datetime(jahr, monat, 1 + n % 27, 12, 0)
    return {"id": _id(n), "type": typ, "localDateTime": d.isoformat() + ".000Z", "fileCreatedAt": d.isoformat() + ".000Z",
            "isFavorite": False, "exifInfo": {"country": land, "exifImageWidth": 4000, "exifImageHeight": 3000}, "originalFileName": f"IMG_{n}.jpg"}


# 30 Fotos: 10 je Jahr 2019/2020/2021, 2 Videos
ASSETS = [_asset(i, 2019 + i % 3, 1 + i % 12, land=LAENDER[i % 3]) for i in range(1, 29)]
ASSETS += [_asset(100, 2020, 5, "VIDEO"), _asset(101, 2021, 6, "VIDEO")]


def H_schluessel():
    import rahmen_helfer
    return rahmen_helfer.schluessel()


ALBEN = {"aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa": [a["id"] for a in ASSETS[:14]], "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb": [a["id"] for a in ASSETS[14:28]]}


class SchreinImmich:
    """Beantwortet genau die Immich-Aufrufe, die die App macht."""

    def __init__(self):
        self.aufrufe = []
        self.schluessel = []         # welcher Immich-Schluessel gehoerte zu jedem Aufruf

    def __call__(self, method, path, body=None, timeout=120):
        self.aufrufe.append((method, path))
        self.bodies = getattr(self, "bodies", [])
        self.bodies.append((path, body))
        self.schluessel.append(H_schluessel())
        body = body or {}
        if path.startswith("/people"):
            return {"people": [{"id": i, "name": n} for n, i in PERSONEN]}
        if path.startswith("/search/suggestions"):
            return LAENDER if "country" in path else []
        if path == "/albums":
            return getattr(self, "albumliste", [])
        if path.startswith("/assets/"):
            return next(a for a in ASSETS if a["id"] == path.rsplit("/", 1)[1])
        if path in ("/search/statistics", "/search/metadata", "/search/random", "/search/smart"):
            treffer = [a for a in ASSETS if self._passt(a, body)]
            if path == "/search/statistics":
                return {"total": len(treffer)}
            if path == "/search/random":
                return treffer[: body.get("size", 10)]
            if body.get("order") == "asc":
                treffer = sorted(treffer, key=lambda a: a["localDateTime"])
            else:
                treffer = sorted(treffer, key=lambda a: a["localDateTime"], reverse=True)
            n = body.get("size", 100)
            return {"assets": {"items": treffer[:n], "total": len(treffer[:n]), "nextPage": None}}
        raise AssertionError(f"unerwarteter Immich-Aufruf {method} {path}")

    @staticmethod
    def _passt(a, b):
        if b.get("type") and a["type"] != b["type"]:
            return False
        if b.get("country") and a["exifInfo"]["country"] != b["country"]:
            return False
        if b.get("albumIds") and a["id"] not in {i for alb in b["albumIds"] for i in ALBEN.get(alb, [])}:
            return False
        if b.get("takenAfter") and a["localDateTime"] < b["takenAfter"][:19]:
            return False
        if b.get("takenBefore") and a["localDateTime"] >= b["takenBefore"][:19]:
            return False
        return True


@pytest.fixture
def app_laden(tmp_path, monkeypatch):
    """app_laden(**env) -> (modul, TestClient-Fabrik). Jede Umgebung bekommt frische Module und Datenverzeichnisse."""
    from fastapi.testclient import TestClient

    def laden(**env):
        daten = tmp_path / "data"
        daten.mkdir(exist_ok=True)
        basis = {"RAHMEN_WEB_PIN_FILE": str(daten / "pin"), "RAHMEN_WEB_SECRET_FILE": str(daten / "secret"),
                 "RAHMEN_WEB_AUTH_STATE": str(daten / "auth.json"), "RAHMEN_WEB_SHOWS_FILE": str(daten / "shows.json"),
                 "RAHMEN_WEB_STATIC": os.path.join(RAIZ, "static"), "RAHMEN_HELFER_DIR": RAIZ, "RAHMEN_IMMICH_KEY": "test", "RAHMEN_IMMICH_URL": "http://immich.test/api", "RAHMEN_WEB_EINSTELLUNGEN": str(daten / "gibt-es-nicht.json"),
                 "RAHMEN_WEB_VIDEO_DIR": str(daten / "videos"), "RAHMEN_WEB_TV_DIR": str(daten / "tv"), "RAHMEN_WEB_MUSIK_DIR": str(daten / "musik")}
        for k in list(os.environ):
            if k.startswith("RAHMEN_"):
                monkeypatch.delenv(k)
        for k, v in {**basis, **env}.items():
            monkeypatch.setenv(k, v)
        for m in ("rahmen_helfer", "rahmen_web"):
            sys.modules.pop(m, None)
        import rahmen_helfer
        monkeypatch.setattr(rahmen_helfer, "STATE_FILE", str(tmp_path / "state.json"))
        monkeypatch.setattr(rahmen_helfer, "LOCK_FILE", str(tmp_path / "lock"))
        importlib.invalidate_caches()
        import rahmen_web
        schrein = SchreinImmich()
        monkeypatch.setattr(rahmen_helfer, "api", schrein)
        rahmen_web.CACHE.clear()
        (daten / "pin").write_text(rahmen_web.pin_hash("123456"))
        return rahmen_web, (lambda host="192.168.1.50": TestClient(rahmen_web.app, client=(host, 50000))), schrein

    return laden


BENUTZER = {"anna@example.org": ("anna-passwort", "aaaaaaaa-0000-4000-8000-00000000000a", "Anna"),
            "karl@example.org": ("karl-passwort", "bbbbbbbb-0000-4000-8000-00000000000b", "Karl")}


class SchreinAnmeldung:
    """Schein fuer die direkten Anmelde-Aufrufe (/auth/login, /api-keys, /auth/logout)."""

    def __init__(self):
        self.schluessel = {}       # uid -> ausgestellter Schluessel
        self.abgemeldet = []
        self.widerrufen = set()

    def __call__(self, methode, pfad, daten=None, token=None, schluessel=None, basis=None):
        import urllib.error
        if pfad == "/auth/login":
            e = BENUTZER.get(daten["email"])
            if not e or e[0] != daten["password"]:
                raise urllib.error.HTTPError("x", 401, "nein", {}, None)
            return {"accessToken": "tok-" + e[1], "userId": e[1], "name": e[2], "userEmail": daten["email"]}
        if pfad == "/api-keys" and methode == "POST":
            assert token and "asset.delete" not in daten["permissions"] and not any("delete" in p and p not in ("album.delete", "albumAsset.delete") for p in daten["permissions"])
            uid = token[4:]
            self.schluessel[uid] = "key-" + uid[:4] + f"-{len(self.schluessel)}"
            return {"secret": self.schluessel[uid], "apiKey": {"id": "id-" + uid[:4]}}
        if pfad == "/api-keys/me":
            if schluessel in self.widerrufen or (schluessel not in self.schluessel.values() and schluessel != "eigener-key"):
                raise urllib.error.HTTPError("x", 401, "nein", {}, None)
            return {"name": "Immich Showcase", "permissions": ["all"]}
        if methode == "DELETE" and pfad.startswith("/api-keys/"):
            self.geloescht = getattr(self, "geloescht", []) + [pfad]
            return None
        if pfad == "/server/version":
            return {"major": 3, "minor": 2, "patch": 4}
        if pfad == "/users/me":
            if schluessel not in self.schluessel.values() and schluessel != "eigener-key":
                raise urllib.error.HTTPError("x", 401, "nein", {}, None)
            return {"id": "cccccccc-0000-4000-8000-00000000000c", "name": "Sven", "email": "sven@example.org"}
        if pfad == "/auth/logout":
            self.abgemeldet.append(token)
            return {"successful": True}
        raise AssertionError(pfad)
