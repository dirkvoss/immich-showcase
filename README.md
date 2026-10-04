# Immich Showcase

Eine kleine Web-App (PWA) für **Immich**: Fotos suchen und auswählen, der Auswahl einen Namen geben und sie auf dem **Bilderrahmen**, dem **Fernseher** (mit Hintergrundmusik und Videos) oder als **Diashow im Browser** zeigen. Gedacht für Familien, bei denen nicht jeder Immich bedienen möchte.

> Immich Showcase ist ein unabhängiges Community-Projekt und steht in keiner Verbindung zum Immich-Projekt oder dessen Betreibern. „Immich“ ist der Name der Software, mit der es zusammenarbeitet.

> Status: läuft produktiv im Homelab des Autors und wird gerade für andere Installationen verallgemeinert (siehe [Fahrplan](#fahrplan)). Bis dahin: **nur für Leute, die Docker und Immich selbst betreiben.**

## Was es kann
- Suche in ganzen Sätzen: Personen, Zeit, Ort, Motiv („Oma und Anna Weihnachten 2019 am Strand“)
- Verknüpfte Filter (Person, Jahr, Land, Fotos/Videos), alle Fotos eines Tages oder alles auswählen, Rückgängig
- Shows speichern, benennen, merken, wieder starten
- Fernseher: Seite im TV-Browser (LG webOS, Android TV, Shield …), Steuerung vom Handy (Pause, vor/zurück, Musik), Reihenfolge zeitlich auf- oder absteigend oder zufällig, Videos werden vorab für den Fernseher umgewandelt
- Hintergrundmusik aus eigenen Ordnern (Zufall, Titelwahl)
- Bilderrahmen: eigener Player (Tablet-Browser oder Fully Kiosk öffnet `…/tv/?ziel=rahmen`): im Leerlauf Zufallsfotos mit Uhr, Shows aus der App laufen dort wie auf einem Fernseher; „Stopp“ bringt das Dauerprogramm zurück.

## Voraussetzungen
- Immich (getestet mit 3.2.x); ein API-Schlüssel mit den in `.env.example` genannten Rechten. Zugriff auf Immichs Datenbank ist **optional**.
- Docker / Compose, ein Reverse-Proxy mit HTTPS, wenn die App von außen erreichbar sein soll
- Optional: immich-kiosk für den festen Bilderrahmen

## Installation (Docker Compose)
Voraussetzung: Docker mit Compose und eine laufende Immich-Installation. Es wird **kein Quelltext gebaut**, das fertige Image kommt von `ghcr.io`.

```bash
git clone https://github.com/dirkvoss/immich-showcase.git && cd immich-showcase     # oder nur docker-compose.yml und .env.example herunterladen
cp .env.example .env
docker compose up -d
docker compose logs showcase      # zeigt den Einrichtungs-Code
```
Dann `http://<server>:8090` öffnen: Der **Einrichtungsassistent** fragt nach dem Code aus dem Protokoll, der Adresse von Immich und deinem Immich-Konto (E-Mail + Passwort), legt den nötigen Schlüssel **selbst** an (ohne Lösch-Rechte; das Passwort wird nicht gespeichert) und lässt dich die PIN wählen. Danach startet Immich Showcase von selbst neu (iPhone: Teilen → „Zum Home-Bildschirm“). Wer lieber ohne Assistent arbeitet, trägt `RAHMEN_IMMICH_URL` und `RAHMEN_IMMICH_KEY` in die `.env` ein; die Einstellungen aus der `.env` haben immer Vorrang vor denen des Assistenten (gespeichert in `/data/einstellungen.json`). Alles Weitere steht in der `.env`, jede Einstellung ist dort erklärt.

**Immich im selben Docker-Rechner?** Entweder `RAHMEN_IMMICH_URL=http://<ip-des-rechners>:2283/api` eintragen, oder Immich Showcase ins Immich-Netzwerk hängen: in `.env` `COMPOSE_FILE=docker-compose.yml:docker-compose.immich-network.yml` und `SHOWCASE_IMMICH_NETWORK=immich_default` (Name per `docker network ls`) setzen, dann `RAHMEN_IMMICH_URL=http://immich_server:2283/api`.

**Selbst bauen** statt das Image zu laden: `COMPOSE_FILE=docker-compose.yml:docker-compose.build.yml` in `.env`, dann `docker compose up -d --build`.

**Was liegt wo?** Alle Daten (PIN-Hash, Sitzungen, Shows, Zwischenspeicher, eigene Musik) liegen im Volume `showcase_data` (Pfad `/data`). Soll es ein Ordner sein: `SHOWCASE_DATA=./data`, `SHOWCASE_UID`/`SHOWCASE_GID` auf den Besitzer des Ordners setzen (`id -u`, `id -g`). Der Container läuft ohne Root, mit schreibgeschütztem Dateisystem und ohne Linux-Capabilities.

**Von außen erreichbar machen:** immer hinter einen Reverse-Proxy mit HTTPS (Nginx, Caddy, Traefik, Nginx Proxy Manager …) und `SHOWCASE_BIND=127.0.0.1` setzen, wenn der Proxy auf demselben Rechner läuft. Trägt der Proxy die Verbindung, die Adresse in `RAHMEN_WEB_PROXIES` eintragen. WebSocket-Unterstützung ist nicht nötig. Ein vertrautes Netz (`RAHMEN_WEB_LAN`) nur setzen, wenn Internetverkehr nicht mit einer internen Adresse ankommt.

**Fernseher einrichten:** in `.env` `RAHMEN_WEB_TV_ZIELE=wohnzimmer=Wohnzimmer`, am Fernseher im Browser `http://<server>:8090/tv/?ziel=wohnzimmer` öffnen und als Lesezeichen speichern (Smart-TV-Browser, Android TV, Shield, Chromecast mit Browser …).
**Bilderrahmen einrichten:** `RAHMEN_WEB_RAHMEN_ZIELE=rahmen=Bilderrahmen`; am Tablet (Browser im Vollbild oder Fully Kiosk) `http://<server>:8090/tv/?ziel=rahmen` als Startseite. Quellen und Gewichte des Dauerprogramms: `RAHMEN_WEB_RAHMEN_QUELLEN`.
**Eigene Musik (keine im Lieferumfang):** zwei Wege, beide mit eigener oder frei lizenzierter Musik (mp3, ogg, m4a):
1. *Ordner:* Dateien in Unterordner von `/data/musik` legen, jeder Ordner ist eine Sammlung (`/data/musik/Urlaub/01 Lied.mp3`), z. B. mit `- ./musik:/data/musik:ro` in der Compose-Datei. Titel und Künstler kommen aus den Dateimarken, sonst aus dem Dateinamen. Optional beschreibt eine `info.json` im Ordner (`name`, `stuecke` mit `datei`, `titel`, `urheber`, `lizenz`) die Titel genauer.
2. *In der App:* `RAHMEN_WEB_MUSIK_UPLOAD=1` setzen, dann erscheint im „Auf den Fernseher“-Fenster „Eigene Musik hinzufügen …“ (hinzufügen und entfernen, mit Größengrenzen).
Ausgewählt wird die Musik im selben Fenster („Hintergrundmusik“), auch „Alles bunt gemischt“ oder ein einzelner Titel über die Fernbedienung.

**Aktualisieren:** `docker compose pull && docker compose up -d` (oder mit `deploy/deploy.sh` samt Sicherung und automatischem Rückweg, siehe RELEASING.md).
**Störungen:** `docker compose logs showcase`. Zeigt die App „Einrichtung erforderlich“, ist Immich Showcase noch nicht mit Immich verbunden (Assistent unter `/setup/`). 401 in der App heißt: PIN oder Konto fehlt.

## Entwicklung und Auslieferung
Tests: `pip install -r requirements-dev.txt && python -m pytest`. Versionen werden per Tag (`v1.2.3`) von GitHub Actions gebaut und mit `deploy/deploy.sh` samt Sicherung und automatischem Rückweg ausgeliefert, siehe [RELEASING.md](RELEASING.md).

## Konfiguration
Alles Installationsspezifische steht in der `.env` (Vorlage mit Erklärung jeder Einstellung: [.env.example](.env.example)); eigene Einstellungen gehören nie ins Repository (`.env` ist ausgeschlossen). Wichtig: Ohne `RAHMEN_WEB_LAN` und `RAHMEN_WEB_PROXIES` verlangt jede Anfrage die PIN. Das ist die sichere Vorgabe.

## Sicherheit
- Die App kann Fotos **nie löschen**; der Schlüssel braucht keine Löschrechte.
- Anmeldung per PIN oder Immich-Konto, jeweils mit Sperre nach Fehlversuchen (je IP und je E-Mail), Pro Person ein eigener, in Immich widerrufbarer Schlüssel ohne Löschrechte, Sitzung 90 Tage, schreibende Aufrufe nur mit eigenem Header.
- Container: nicht-root, Dateisystem schreibgeschützt, ohne Linux-Capabilities, Speicher begrenzt.
- Die Fernseher-Seite zeigt Fotos ohne Anmeldung, wenn sie aus einem vertrauten Netz aufgerufen wird. Netze deshalb eng wählen.

## Einschränkungen (ehrlich)
- Ohne Datenbankzugang prüft die Motivsuche („am Strand“) die Ähnlichkeit nicht exakt, sondern nimmt die besten 60 Treffer der Rangliste (Immich liefert über die API keine Ähnlichkeitswerte). Filter und Sortierung sind über die API etwas langsamer, aber gleichwertig.
- Ohne `RAHMEN_WEB_RAHMEN_ZIELE` erwartet der „Bilderrahmen“-Weg einen immich-kiosk samt Hilfsskript auf dem Immich-Host (Legacy, hier nicht enthalten). Empfohlen ist der eingebaute Rahmen-Player.
- Die Oberfläche gibt es auf **Deutsch, Englisch, Spanisch, Französisch und Niederländisch** (automatisch nach Browsersprache, oder `?lang=xx`; Umschalter im Hilfe-Fenster). Die **Suche in ganzen Sätzen** versteht dieselben fünf Sprachen (Monate, Jahreszeiten, „letzte Wochen“, Weihnachten …). Die Übersetzungen ES/FR/NL sind maschinell erstellt – Korrekturen sind willkommen. Weitere Sprachen: `static/i18n/<sprache>.json` (Schlüssel wie in `en.json`) und ein Eintrag in `SPRACHEN` (`rahmen_helfer.py`).
- Anmeldung: Vorgabe ist eine gemeinsame PIN. Mit `RAHMEN_WEB_AUTH=immich` (oder `beide`) melden sich Personen mit ihrem **Immich-Konto** an und sehen nur ihre eigenen Fotos und Shows; Immich Showcase führt keine eigene Benutzerverwaltung. Dafür muss der Rahmen der eingebaute Player sein.
- Musik wird nicht mitgeliefert (Lizenzen): eigene MP3-Dateien in `data/musik/<sammlung>/` mit einer `info.json` (Titel, Urheber, Lizenz) ablegen.

## Fahrplan
1. Konfiguration entkoppeln (erledigt: Name, Netze, Proxys, Fernseher, Beispiele über Umgebungsvariablen; sichere Vorgaben)
2. Immich-API statt Datenbank (erledigt, Datenbank optional); Oberfläche und Suche in fünf Sprachen (erledigt)
3. Anmeldung mit dem Immich-Konto (erledigt, `RAHMEN_WEB_AUTH`); offen: Einrichtungsassistent, SSO/OIDC
4. Eigener Rahmen-Player statt immich-kiosk (erledigt: Dauerprogramm + Shows; offen: Albumquellen mit Gewichtung, Überwachung/Neustart)
5. Geräte-Kopplung per Code/QR, Lizenz festlegen, Veröffentlichung

## Lizenzen von Bestandteilen
Schrift *Cormorant Garamond* (SIL OFL 1.1). Das Logo ist eigens erzeugt. Keine Musik im Repository.

## Lizenz
[GNU Affero General Public License v3.0 oder neuer](LICENSE) (AGPL-3.0-or-later), wie Immich selbst. Wer die App als Dienst für andere betreibt, muss geänderten Quelltext ebenfalls bereitstellen. Schrift: siehe `static/fonts/OFL.txt`.

## Hinweis
Immich Showcase ist ein unabhängiges Projekt und steht in keiner Verbindung zum Immich-Team. Immich ist eine Marke seiner Urheber.
