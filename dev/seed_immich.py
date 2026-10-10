#!/usr/bin/env python3
"""Fuellt eine FRISCHE Test-Immich-Instanz fuer die Frameside-Entwicklung: Administrator, Testbenutzer, API-Schluessel, ~70 erfundene
Fotos (Datum, GPS, Orte), 3 Videos, 3 Personen mit Gesichtern. Nichts davon ist echt. Nicht gegen eine echte Immich-Installation ausfuehren!

Aufruf (auf dem Entwicklungsrechner, Immich unter http://localhost:2283):
    python3 seed_immich.py [--url http://localhost:2283] [--ausgabe zugang.json]
Benoetigt: Python 3, Pillow, exiftool, ffmpeg, curl.
"""
import argparse
import datetime as dt
import json
import os
import random
import subprocess
import sys
import tempfile
import urllib.request

from PIL import Image, ImageDraw, ImageFont

ORTE = [("Rom", 41.9028, 12.4964), ("Cagliari", 39.2238, 9.1217), ("Muenchen", 48.1351, 11.5820), ("Belgrad", 44.7866, 20.4489),
        ("Barcelona", 41.3851, 2.1734), ("Wien", 48.2082, 16.3738)]
PERSONEN = ["Anna Test", "Opa Karl", "Mia Muster"]
RECHTE = ["asset.read", "asset.view", "asset.statistics", "timeline.read", "person.read", "album.create", "album.read", "album.update",
          "album.delete", "albumAsset.create", "albumAsset.delete", "map.read"]


def api(basis, methode, pfad, daten=None, token=None):
    req = urllib.request.Request(basis + "/api" + pfad, method=methode, data=json.dumps(daten).encode() if daten is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    raw = urllib.request.urlopen(req, timeout=120).read()
    return json.loads(raw) if raw else None


def bild(pfad, n, ort, datum):
    """Erfundenes Landschaftsbild (Himmel, Sonne/Mond, Berge oder Meer oder Stadt) - jedes Foto sieht anders aus, nichts davon ist echt."""
    random.seed(n * 7919)
    w, h = 1600, 1067
    szene = ("berge", "meer", "stadt")[n % 3]
    stunde = datum.hour
    tag = 7 <= stunde <= 18
    oben, unten = ((random.choice([(70, 130, 200), (90, 150, 210), (60, 110, 180)]), (235, 215, 190)) if tag
                   else ((20, 24, 60), (120, 80, 110)))
    im = Image.new("RGB", (w, h)); d = ImageDraw.Draw(im)
    horizont = int(h * random.uniform(.55, .68))
    for y in range(horizont):
        t = y / horizont
        d.line([(0, y), (w, y)], fill=tuple(int(oben[i] * (1 - t) + unten[i] * t) for i in range(3)))
    sx, sy, sr = random.randint(150, w - 150), random.randint(90, horizont // 2), random.randint(40, 70)
    d.ellipse([sx - sr * 2, sy - sr * 2, sx + sr * 2, sy + sr * 2], fill=tuple(min(255, c + 25) for c in (unten if tag else (150, 140, 170))))
    d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 238, 190) if tag else (235, 235, 245))
    if szene == "berge":
        for lage, farbe in ((0, (92, 108, 134)), (1, (62, 82, 98)), (2, (36, 54, 62))):
            pts = [(0, horizont + 40)]
            x = -50
            while x < w + 100:
                pts.append((x, horizont - random.randint(80, 330) + lage * 70)); x += random.randint(110, 260)
            pts += [(w, horizont + 40), (w, h), (0, h)]
            d.polygon(pts, fill=farbe)
        d.rectangle([0, horizont + 120, w, h], fill=(36, 58, 48))
    elif szene == "meer":
        for y in range(horizont, h):
            t = (y - horizont) / (h - horizont)
            d.line([(0, y), (w, y)], fill=(int(40 + 20 * (1 - t)), int(110 + 40 * (1 - t)), int(150 + 40 * (1 - t))))
        for _ in range(70):
            x, y = random.randint(0, w), random.randint(horizont + 10, h)
            d.line([(x, y), (x + random.randint(30, 120), y)], fill=(210, 235, 245), width=2)
        d.polygon([(0, h), (0, h - 140), (w // 3, h - 60), (w // 2, h)], fill=(214, 190, 140))
    else:
        d.rectangle([0, horizont, w, h], fill=(48, 52, 60))
        x = 0
        while x < w:
            bw, bh = random.randint(90, 190), random.randint(180, 520)
            farbe = random.choice([(168, 120, 96), (190, 160, 120), (140, 110, 100), (205, 185, 150), (120, 98, 92)])
            d.rectangle([x, horizont - bh + 160, x + bw, h], fill=farbe)
            for fy in range(horizont - bh + 190, h - 40, 60):
                for fx in range(x + 14, x + bw - 24, 40):
                    d.rectangle([fx, fy, fx + 18, fy + 28], fill=(250, 225, 150) if not tag and random.random() < .6 else (70, 82, 98))
            x += bw + random.randint(0, 14)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
    except OSError:
        f = ImageFont.load_default()
    d.text((50, h - 90), f"{ort[0]}  ·  {datum:%d.%m.%Y}", fill=(255, 255, 255), font=f, stroke_width=3, stroke_fill=(0, 0, 0))
    im.save(pfad, "JPEG", quality=88)


def exif(pfad, ort, datum):
    lat, lon = ort[1], ort[2]
    os.environ.setdefault("LC_ALL", "C")
    subprocess.run(["exiftool", "-q", "-overwrite_original", f"-DateTimeOriginal={datum:%Y:%m:%d %H:%M:%S}", f"-CreateDate={datum:%Y:%m:%d %H:%M:%S}",
                    f"-GPSLatitude={abs(lat)}", f"-GPSLatitudeRef={'N' if lat >= 0 else 'S'}", f"-GPSLongitude={abs(lon)}",
                    f"-GPSLongitudeRef={'E' if lon >= 0 else 'W'}", pfad], check=True)


def hochladen(basis, token, pfad, datum, n):
    zeit = datum.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    ausgabe = subprocess.run(["curl", "-sS", "-X", "POST", basis + "/api/assets", "-H", f"Authorization: Bearer {token}",
                              "-F", f"assetData=@{pfad}", "-F", f"deviceAssetId=seed-{n}", "-F", "deviceId=showcase-seed",
                              "-F", f"fileCreatedAt={zeit}", "-F", f"fileModifiedAt={zeit}"], capture_output=True, text=True, check=True).stdout
    antwort = json.loads(ausgabe)
    if "id" not in antwort:
        raise SystemExit(f"Upload fehlgeschlagen ({pfad}): {ausgabe[:300]}")
    return antwort["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:2283")
    ap.add_argument("--ausgabe", default="zugang.json")
    ap.add_argument("--fotos", type=int, default=70)
    ap.add_argument("--sparsam", action="store_true", help="Immich-Hintergrundaufgaben nacheinander (weniger Arbeitsspeicher)")
    arg = ap.parse_args()
    basis = arg.url.rstrip("/")
    admin = {"email": "admin@guckloch.test", "password": "dev-" + os.urandom(6).hex(), "name": "Dev Admin"}
    user = {"email": "anna@guckloch.test", "password": "dev-" + os.urandom(6).hex(), "name": "Anna Testnutzerin"}
    api(basis, "POST", "/auth/admin-sign-up", admin)
    token = api(basis, "POST", "/auth/login", {k: admin[k] for k in ("email", "password")})["accessToken"]
    api(basis, "POST", "/admin/users", user, token)
    schluessel = api(basis, "POST", "/api-keys", {"name": "showcase-dev (keine Foto-Loeschrechte)", "permissions": RECHTE}, token)["secret"]

    if arg.sparsam:                                           # Parallelitaet 1: kleinere Speicherspitzen auf knappen Rechnern
        cfg = api(basis, "GET", "/system-config", None, token)
        for j in cfg["job"]:
            if isinstance(cfg["job"][j], dict) and "concurrency" in cfg["job"][j]:
                cfg["job"][j]["concurrency"] = 1
        api(basis, "PUT", "/system-config", cfg, token)
    random.seed(7)
    ids = []
    with tempfile.TemporaryDirectory() as tmp:
        for n in range(1, arg.fotos + 1):
            ort = ORTE[n % len(ORTE)]
            datum = dt.datetime(2019 + n % 7, 1 + (n * 5) % 12, 1 + (n * 3) % 27, 9 + n % 10, n % 60)
            pfad = os.path.join(tmp, f"test_{n:03d}.jpg")
            bild(pfad, n, ort, datum)
            exif(pfad, ort, datum)
            ids.append((hochladen(basis, token, pfad, datum, n), datum))
        for k in range(1, 4):
            datum = dt.datetime(2021 + k, 6, 10 + k, 15, 0)
            pfad = os.path.join(tmp, f"video_{k}.mp4")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=4", "-f", "lavfi",
                            "-i", "sine=frequency=440:duration=4", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                            "-metadata", f"creation_time={datum:%Y-%m-%dT%H:%M:%S}Z", pfad], check=True)
            hochladen(basis, token, pfad, datum, 1000 + k)
    personen = [api(basis, "POST", "/people", {"name": name}, token)["id"] for name in PERSONEN]
    for i, (aid, _) in enumerate(ids):
        for pid in personen[: 1 + i % 3 if i % 4 else 0]:
            api(basis, "POST", "/faces", {"assetId": aid, "personId": pid, "imageWidth": 1600, "imageHeight": 1067, "x": 710, "y": 380, "width": 180, "height": 240}, token)
    zugang = {"url": basis, "admin": admin, "benutzer": user, "api_key": schluessel, "fotos": len(ids), "videos": 3, "personen": PERSONEN}
    with open(arg.ausgabe, "w") as f:
        json.dump(zugang, f, indent=1)
    os.chmod(arg.ausgabe, 0o600)
    print(f"fertig: {len(ids)} Fotos, 3 Videos, {len(PERSONEN)} Personen. Zugangsdaten in {arg.ausgabe}")


if __name__ == "__main__":
    sys.exit(main())
