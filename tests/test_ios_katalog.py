"""iPhone-App: Jeder Text, der per L("...") im Code steht, hat eine englische Uebersetzung im String-Katalog."""
import glob
import json
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IOS = os.path.join(RAIZ, "ios")


def literale(text):
    """Alle L("...")-Aufrufe samt Interpolationen (verschachtelte Klammern beachtet). Rueckgabe: Schluessel im Katalog-Format (%@ / %lld)."""
    erg = []
    for m in re.finditer(r'\bL\("', text):
        i, roh, tiefe = m.end(), "", 0
        while i < len(text):
            c = text[i]
            if c == "\\" and text[i + 1] == "(":
                j, t = i + 2, 1
                while j < len(text) and t:
                    t += {"(": 1, ")": -1}.get(text[j], 0)
                    j += 1
                ausdruck = text[i + 2:j - 1]
                roh += "%lld" if re.match(r"^(Int\(|status$|code$|e\.rawValue$|ergebnisse\.count$)", ausdruck.strip()) else "%@"
                i = j
                continue
            if c == '"':
                break
            roh += c
            i += 1
        erg.append(roh)
    return erg


def test_alle_L_texte_sind_uebersetzt():
    katalog = json.load(open(os.path.join(IOS, "Resources", "Localizable.xcstrings")))["strings"]
    fehlend = []
    for datei in glob.glob(os.path.join(IOS, "Sources", "*.swift")) + glob.glob(os.path.join(IOS, "Shared", "*.swift")):
        for schluessel in literale(open(datei).read()):
            if schluessel not in katalog or "en" not in katalog[schluessel]["localizations"]:
                fehlend.append((os.path.basename(datei), schluessel))
    assert not fehlend, fehlend


def test_katalogdateien_sind_gueltig():
    for name in ("Localizable", "AppShortcuts", "InfoPlist"):
        d = json.load(open(os.path.join(IOS, "Resources", name + ".xcstrings")))
        assert d["sourceLanguage"] == "de" and d["strings"]
        assert all(v["localizations"]["en"]["stringUnit"]["value"].strip() for v in d["strings"].values())
