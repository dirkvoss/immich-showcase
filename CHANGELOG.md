# Änderungsprotokoll
Format: [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach [SemVer](https://semver.org/lang/de/).

## [2.6.2]
### Behoben
- Am Rechner wurde die Auswahl-Seitenleiste rechts abgeschnitten (z. B. „merken“); Inhalt bleibt jetzt in der Leistenbreite, die Zeile „Name der Show“ darf umbrechen.
- Die Vorlagen für „Problem melden“ und „Wunsch“ auf GitHub waren kein gültiges YAML und wurden nicht geladen; jetzt zweisprachig und gültig.
### Intern
- README mit animiertem Ablauf-GIF.
- `tools/check.sh` prüft vor dem Push, was die CI prüft (Quelltext-Warnungen, Shell-Skripte, YAML, Compose, Tests).
- CI robuster: Docker-Hub-Spiegel gegen die Download-Begrenzung, Container-Test wartet auf das Protokoll, Warnungen im Quelltext lassen den Bau fehlschlagen.

## [2.6.1]
### Behoben
- `install.sh` fand den Einrichtungs-Code im Protokoll nicht (falsches Suchmuster).
- Kalender-Termine: ungültiges Escape-Zeichen im Quelltext (Python-Warnung) korrigiert.
- Der Container-Test in der CI wartet jetzt kurz auf das Protokoll (Version 2.6.0 wurde deshalb nicht veröffentlicht, der Inhalt ist in 2.6.1 enthalten).

## [2.6.0]
### Neu
- **Neues Aussehen („Galerie“):** warmes Papier (hell) bzw. Nachtgalerie (dunkel) mit Messing-Akzent, Serifen-Schrift für Datums-Überschriften, Show-Namen und Fenster-Titel, einheitliche Linien-Symbole statt Emojis (`static/ikonen.js`).
- **Fotos zuerst am Handy:** kompakter Kopf (Geräte, Hilfe, Konto-Menü als Symbole), schmale Rahmen-Statusleiste, Filter als scrollbare Chip-Zeile, größere Foto-Kacheln mit Messing-Rahmen für die Auswahl, neu geordnete Auswahlleiste.
- **Am Rechner:** Fotos links, Auswahl als feste Seitenleiste rechts; Tastenkürzel „/“ (Suche) und „Esc“ (Fenster schließen).
### Behoben
- Der „Zurück zu …“-Knopf im Rahmen-Status erscheint nur noch, solange eine Show läuft, und ist übersetzt (er wurde am Handy abgeschnitten).

## [2.5.1]
### Behoben
- **Eine laufende Show wird nach einem Neustart oder Update des Servers nicht mehr vergessen.** Bisher lief sie am Gerät weiter, aber die App zeigte „Normales Programm“, und das Stoppen bzw. Neu-Laden der Seite funktionierte nicht richtig. Der Zustand wird jetzt gespeichert (`rahmen_web_aktiv.json` neben den Shows).

## [2.5.0]
### Neu
- **Home Assistant:** `GET /api/ha/status`, `POST /api/ha/steuer|show|bildschirm` und eine fertige Vorlage `examples/home-assistant/immich_showcase.yaml` (Sensoren, Online-Sensor, Befehle).
- **Fully Kiosk fernsteuern:** Bildschirm zur Nachtruhe wirklich aus/an (`RAHMEN_WEB_FULLY_<KENNUNG>`), per App an/aus, Akkustand in der Geräte-Ansicht und Pushover-Meldung bei leerem Akku.
- **Programm nach Person:** neue Quelle `person=<Name oder Spitzname>` für das Dauerprogramm.

## [2.4.0]
### Neu
- **Geräte per Code koppeln:** `/tv/` ohne Kennung zeigt einen 6-stelligen Code und einen QR-Code; in der App unter „📡 Geräte“ eingeben (oder scannen) und zuweisen – das Gerät merkt sich seine Rolle. Hinweis: `/tv/` ohne `?ziel=` zeigt jetzt die Kopplung statt automatisch den Fernseher „lg“.
- **Geräte-Ansicht** in der App: online/offline, was läuft, Alter des Bildes, zuletzt gesehen.
- **Mehrere Rahmen mit eigenem Programm** (`RAHMEN_WEB_RAHMEN_QUELLEN_<KENNUNG>`) und **Zeitplan** (`RAHMEN_WEB_RAHMEN_ZEITPLAN`, auch je Rahmen; Wochentage, Uhrzeiten, über Mitternacht).
- **„Heute vor Jahren“:** neue Quelle `heute` / `heuteN` für das Dauerprogramm.
- **Zusatzanzeige am Rahmen:** Wetter (open-meteo.com) und Termine (iCalendar-Link), nur wenn eingerichtet.
- **Schnellinstallation:** `install.sh` und `examples/immich-stack/` (Immich und Immich Showcase zusammen).
### Geändert
- Der Integrationstest in der CI lädt Images mit Wiederholung (Registry-Begrenzung).

## [2.3.0]
### Neu
- **Version immer sichtbar:** klein links in der Kopfzeile der Hauptseite (z. B. „v2.3.0“).
- **Problem melden / Wunsch äußern** im Hilfe-Fenster (öffnet GitHub mit eingetragener Version); Anleitung dazu im README; Link zu den Diskussionen für Fragen.

## [2.2.1]
### Neu
- Die **Version** steht jetzt sichtbar in der App: klein unter der Anmeldeseite und am Ende der Hauptseite (zusätzlich wie bisher im Hilfe-Fenster).

## [2.2.0]
### Neu
- **Englische Dokumentation:** `README.md` ist jetzt eine ausführliche Installations- und Bedienungsanleitung auf Englisch, `README.de.md` die deutsche Fassung; Screenshots mit dem neuen Namen.
- Marker-Alben erkennen auch englische Marker (`#frame`, `#onlyframe`).
### Behoben
- Der längere Name „Immich Showcase“ wird im Kopf der App nicht mehr abgeschnitten (bricht um).

## [2.1.0]
### Neu
- **Marker-Alben für den Bilderrahmen** (`RAHMEN_WEB_RAHMEN_MARKER=1`): Alben mit `#…rahmen…` in der Beschreibung kommen von selbst zum Dauerprogramm, `#…nurrahmen…` zeigt nur diese Alben (in der gewählten Reihenfolge, laufend weiter). Damit kann der Eigenplayer den bisherigen Rahmen-Kiosk ersetzen.

## [2.0.0]
### Geändert (Umbenennung – bitte lesen)
- Das Projekt heißt jetzt **Immich Showcase** (früher „Guckloch“), mit neuem Symbol.
- **Image:** `ghcr.io/dirkvoss/immich-showcase` (statt `…/guckloch`).
- **Umgebungsvariablen:** Präfix `SHOWCASE_` statt `GUCKLOCH_` (`SHOWCASE_VERSION`, `SHOWCASE_PIN`, …). `deploy/deploy.sh` liest `GUCKLOCH_*` aus `deploy.conf` und `.env` weiterhin; die Compose-Datei muss angepasst werden (siehe README/Skript).
- CI schneller: Image-Bau parallel zum Integrationstest, Versions-Tags wiederholen den Integrationstest nicht.

## [Unveröffentlicht]
### Neu
- **Geräte per Code koppeln:** `/tv/` ohne Kennung zeigt einen 6-stelligen Code und einen QR-Code; in der App unter „📡 Geräte“ eingeben (oder scannen) und zuweisen – das Gerät merkt sich seine Rolle. Hinweis: `/tv/` ohne `?ziel=` zeigt jetzt die Kopplung statt automatisch den Fernseher „lg“.
- **Geräte-Ansicht** in der App: online/offline, was läuft, Alter des Bildes, zuletzt gesehen.
- **Mehrere Rahmen mit eigenem Programm** (`RAHMEN_WEB_RAHMEN_QUELLEN_<KENNUNG>`) und **Zeitplan** (`RAHMEN_WEB_RAHMEN_ZEITPLAN`, auch je Rahmen; Wochentage, Uhrzeiten, über Mitternacht).
- **„Heute vor Jahren“:** neue Quelle `heute` / `heuteN` für das Dauerprogramm.
- **Zusatzanzeige am Rahmen:** Wetter (open-meteo.com) und Termine (iCalendar-Link), nur wenn eingerichtet.
- **Schnellinstallation:** `install.sh` und `examples/immich-stack/` (Immich und Immich Showcase zusammen).
### Geändert
- Der Integrationstest in der CI lädt Images mit Wiederholung (Registry-Begrenzung).

### Neu (älter)
- **Einrichtungsassistent** unter `/setup/` (Code aus dem Protokoll): verbindet mit Immich, legt den Schlüssel selbst an, setzt die PIN, startet neu.
- **Anmeldung mit eigenem Immich-API-Schlüssel** (für Konten ohne Passwort, z. B. SSO).
- **Rahmen-Anzeigeoptionen:** unscharfer Hintergrund oder Zuschnitt statt schwarzer Balken, Datum/Ort als Bildunterschrift, Nachtruhe (`RAHMEN_WEB_RAHMEN_FUELLUNG`, `_ANZEIGE`, `_NACHT`).
- Die Motivsuche fällt ohne Immich Machine Learning auf eine Suche ohne Motiv zurück.
- **Sprachen:** Oberfläche und Suche jetzt auch auf Spanisch, Französisch und Niederländisch (Umschalter im Hilfe-Fenster); Englisch für die Suche.
- **Hilfe-Fenster** mit Kurzanleitung und **Support-Paket** (Diagnose ohne Geheimnisse) zum Herunterladen für Fehlerberichte.
- Test gegen echte Immich-Versionen in GitHub Actions; Container-Image für amd64 **und arm64** (Raspberry Pi, Synology).
### Geändert
- Der Immich-Schlüssel braucht zusätzlich `user.read`.
- Kopfzeile bei Immich-Anmeldung: Name und „Abmelden“ in eigener Zeile.

## [1.3.0]
- Keine Musik mehr im Lieferumfang: eigene Ordner (mp3/ogg/m4a), Titel aus Dateimarken, optional Hochladen/Entfernen in der App (`RAHMEN_WEB_MUSIK_UPLOAD`).
- **Prüfungen nach dem Deploy** (`postdeploy.py`) mit automatischem Rückweg in `deploy.sh`.

## [1.2.0]
- Dauerprogramm des Rahmens mit gewichteten Quellen, ohne Wiederholer, Überwachung (Selbstheilung, Pushover).
- Komplette Docker-Compose-Installation, alle Einstellungen über `.env`, Rauchtest in der CI, `:latest`-Tag.

## [1.1.0]
- Anmeldung mit dem Immich-Konto (`RAHMEN_WEB_AUTH`), je Person eigener Schlüssel, Shows und Zähler.

## [1.0.0]
- Erste Veröffentlichung: Suche in ganzen Sätzen, Auswahl, Shows, Fernseher, Bilderrahmen, Browser-Diashow, Deutsch/Englisch.
