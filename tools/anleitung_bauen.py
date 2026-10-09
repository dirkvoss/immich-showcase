#!/usr/bin/env python3
"""Baut aus den Anleitungen docs/anleitung.md und docs/anleitung-externer-rechner.md je ein einziges Dokument mit Text UND Bildern (docs/<name>.html, alle Bilder eingebettet).

    python tools/anleitung_bauen.py          # nur die HTML-Datei
    python tools/anleitung_bauen.py --pdf    # zusaetzlich docs/anleitung.pdf (braucht Chrome/Chromium)
Benoetigt das Paket `markdown` (pip install markdown).
"""
import base64
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

WURZEL = Path(__file__).resolve().parent.parent
DOCS = WURZEL / "docs"
REPO = "https://github.com/dirkvoss/immich-showcase/tree/main/"

CSS = """
:root { color-scheme: light; }
body { font: 16px/1.6 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #1c2430; background: #fff; margin: 0; }
main { max-width: 820px; margin: 0 auto; padding: 32px 22px 64px; }
h1 { font-size: 2rem; margin: 0 0 .4em; } h2 { margin: 2.2em 0 .5em; padding-bottom: .25em; border-bottom: 2px solid #e8c88a; }
h3 { margin: 1.6em 0 .4em; }
img { max-width: 100%; height: auto; border: 1px solid #d5dae1; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,.12); margin: .6em 0 1.2em; display: block; max-height: 700px; width: auto; }
img[src*="anleitung/13"], img[src*="anleitung/14"] { max-width: 300px; }
code { background: #f1f3f6; padding: .1em .35em; border-radius: 4px; font-size: .92em; }
pre { background: #1b1d23; color: #e3e6ec; padding: 14px 16px; border-radius: 8px; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; } pre code { background: none; color: inherit; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; } th, td { border: 1px solid #d5dae1; padding: 8px 10px; vertical-align: top; text-align: left; } th { background: #f4f6f9; }
blockquote { margin: 1em 0; padding: .6em 1em; border-left: 4px solid #e0a24a; background: #fff8ec; }
blockquote p { margin: .3em 0; } hr { border: 0; border-top: 1px solid #d5dae1; margin: 2em 0; }
details { margin: .8em 0; } summary { cursor: pointer; font-weight: 600; }
a { color: #9a5b10; }
@media print { main { padding: 0; max-width: none; } h2 { break-after: avoid; } img, pre, table, blockquote { break-inside: avoid; } img { box-shadow: none; max-height: 11.5cm; width: auto; } }
"""


def bild_einbetten(m):
    pfad = DOCS / m.group(2)
    if not pfad.is_file():
        raise SystemExit(f"Bild fehlt: {pfad}")
    daten = base64.b64encode(pfad.read_bytes()).decode()
    return f'{m.group(1)}data:image/png;base64,{daten}"'


SEITEN = {"anleitung": "Immich Showcase – Erste Schritte", "anleitung-externer-rechner": "Immich Showcase – auf einem anderen Rechner als Immich"}


def bauen(name, titel, pdf=False):
    text = (DOCS / f"{name}.md").read_text(encoding="utf-8")
    text = re.sub(r"\]\(\.\./([^)]+)\)", lambda m: f"]({REPO}{m.group(1)})", text)          # Links ins Repo absolut machen
    html = markdown.markdown(text, extensions=["tables", "fenced_code", "md_in_html", "sane_lists"])
    html = html.replace("<details>", "<details open>")                                       # im Dokument alles aufgeklappt
    html = re.sub(r'(<img [^>]*src=")(anleitung/[^"]+)"', bild_einbetten, html)
    seite = f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{titel}</title><style>{CSS}</style></head><body><main>{html}</main></body></html>'
    ziel = DOCS / f"{name}.html"
    ziel.write_text(seite, encoding="utf-8")
    print(f"{ziel.relative_to(WURZEL)}  {ziel.stat().st_size // 1024} KB")
    if pdf:
        chrome = next((c for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", shutil.which("chromium"), shutil.which("google-chrome")) if c and Path(c).exists()), None)
        if not chrome:
            raise SystemExit("Chrome/Chromium nicht gefunden - PDF uebersprungen.")
        out = DOCS / f"{name}.pdf"
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={out}", ziel.as_uri()], check=True, capture_output=True)
        print(f"{out.relative_to(WURZEL)}  {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    for n, ti in SEITEN.items():
        bauen(n, ti, "--pdf" in sys.argv)
