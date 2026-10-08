# Änderungsprotokoll
Format: [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach [SemVer](https://semver.org/lang/de/).

## [2.10.1]
### Behoben
- Im Banner gibt es wieder einen Knopf **„■ Show beenden“** (zurück ins Dauerprogramm), solange eine Show läuft – er war beim neuen Aussehen versehentlich versteckt, sodass sich eine laufende Show nur mit „Zurück zu …“ beenden ließ.
- „Verbindung testen“ (Fully): Die Meldung lag hinter dem Dialog und war unsichtbar; sie steht jetzt auch direkt unter dem Knopf. Falsches Passwort und nicht erreichbares Tablet werden klar unterschieden (vorher hätte ein falsches Passwort „Verbunden“ gezeigt).

## [2.10.0]
### Neu
- **Assistent „Gerät hinzufügen“:** Name und Art eingeben, dann zeigt die App Adresse und QR-Code zum Verbinden und wartet live, bis sich das Tablet/der Fernseher meldet („✓ Verbunden“). Den Verbindungs-Link gibt es auch später im ⚙ des Geräts. Der Kopplungs-Code bleibt als Alternative.
- **Einstellungen in der App** (Konto-Menü → ⚙ Einstellungen) statt in der `.env`: Vorgaben für alle Rahmen (Sekunden, Hintergrund, Bildunterschrift, Offline-Alarm), Wetter-Ort (Ortssuche) und Kalender-Link mit Test, Pushover-Zugang mit Test-Nachricht, Spitznamen für Personen, Adresse der Fernseher-Seite. Die Datei `rahmen_web_einstellungen.json` hat Vorrang vor den Umgebungsvariablen; Geheimnisse (Kalender-Link, Pushover) werden nie ausgeliefert. Anmeldeart, vertrautes Netz, Proxys und Immich-Schlüssel bleiben bewusst in der Umgebung.
- **Tablet-Steuerung ohne Adresse und Passwort:** Läuft die Rahmen-Seite in Fully Kiosk mit aktiver JavaScript-Schnittstelle, schaltet das Tablet den Bildschirm zur Nachtruhe selbst aus und meldet Akku und Ladezustand (inkl. Warnung bei niedrigem Akku). Wer das nicht nutzen kann, trägt wie bisher Adresse und Passwort der Fully-Fernbedienung ein – die App schlägt die erkannte Adresse des Tablets vor. Der ganze Bereich ist „optional“ und eingeklappt; ohne ihn läuft alles wie gehabt.
- **Bildunterschrift mit Uhrzeit** (Datum · Uhrzeit · Ort).
- Der Banner nennt bei genau einem Rahmen dessen Namen („Läuft gerade auf Bilderrahmen“); die Hilfe erklärt die Geräte-Verwaltung.

## [2.9.0]
### Neu
- **Zeitplan mit Eingabemaske:** Zeitfenster mit Wochentagen, Uhrzeit von–bis und eigenen Quellen (statt Textfeld); bestehende Zeitpläne werden gelesen und wieder geschrieben.
- **Shows auf die Rahmen verteilen:** Unter „Meine Shows“ (ab zwei Rahmen) wählst du in einem Dialog für jeden Rahmen eine eigene Show, „Normales Programm“ oder „Nicht ändern“.
- Im Geräte-Dialog steht die **Kennung** des Geräts (für Home Assistant); das HA-Beispiel erklärt, wie weitere Geräte ergänzt werden.

## [2.8.0]
### Neu
- **Geräte-Verwaltung in der App:** Unter „Geräte“ (⚙ je Gerät, „＋ Gerät hinzufügen“) legst du Bilderrahmen und Fernseher an, stellst sie ein und löschst sie – ohne Docker-Konfiguration und ohne Neustart. Je Rahmen: Name, Sekunden pro Foto, Hintergrund, Bildunterschrift, Nachtruhe, Dauerprogramm (Quellen mit Gewicht), Zeitplan und Fully Kiosk (mit Verbindungstest). Fernseher: Name und Hintergrund.
- Die Geräteliste liegt in `rahmen_web_geraete.json` im Datenordner (`RAHMEN_WEB_GERAETE_FILE`). Solange es die Datei nicht gibt, gelten wie bisher die Umgebungsvariablen (`RAHMEN_WEB_RAHMEN_ZIELE`, `RAHMEN_WEB_TV_ZIELE`, `RAHMEN_WEB_FULLY_<ID>`); die erste Änderung in der App legt die Datei an, danach hat sie Vorrang. Leere Einstellungen eines Geräts bedeuten: allgemeiner Wert der Installation.
- Die Rahmen-Seite (`/tv/`) holt ihre Einstellungen je Gerät (`/api/config?ziel=…`).
- Schnittstellen: `GET /api/verwaltung`, `POST /api/verwaltung/geraete`, `PUT/DELETE /api/verwaltung/geraete/<id>`, `POST /api/verwaltung/fully-test`. Das Fully-Passwort wird nie ausgeliefert.
### Geändert
- Die Überwachungen (Rahmen offline, Fully-Nachtruhe/Akku) laufen immer und berücksichtigen neu angelegte Geräte sofort.

## [2.7.0]
### Neu
- **Mehrere Bilderrahmen:** Jeder Rahmen (`RAHMEN_WEB_RAHMEN_ZIELE`) hat jetzt seinen eigenen Zustand – laufende Show, „Zurück“, Reihenfolge. Beim Senden wählst du in der Auswahlleiste per Häkchen einen oder mehrere Rahmen (dieselbe Show an mehrere, oder nacheinander verschiedene Shows an verschiedene Rahmen). Im Banner oben wählst du, welchen Rahmen „Normal“, „Zurück“ und die Reihenfolge betreffen.
- Gespeicherte Shows („Meine Shows“) laufen auf den gewählten Rahmen.
- Schnittstellen: `/api/anzeigen` und `/api/shows/<id>/anzeigen` nehmen `ziele` (Liste), `/api/status`, `/api/zurueck`, `/api/normal` und `/api/reihenfolge` nehmen `ziel`. Ohne Angabe gilt der erste Rahmen – bestehende Einrichtungen und Automationen ändern sich nicht.

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
