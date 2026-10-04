# Immich Showcase

<p align="center"><img src="static/icon-192.png" width="96" alt="Symbol von Immich Showcase"></p>

**Zeige deine [Immich](https://immich.app)-Fotos auf dem Fernseher und im Bilderrahmen – und lass die ganze Familie das vom Handy aus tun.**
Suche in ganzen Sätzen („Oma und Anna Weihnachten 2019 am Strand“), tippe die Fotos an, gib der Show einen Namen und schick sie an den Fernseher im Wohnzimmer oder den Bilderrahmen im Flur. Mit Hintergrundmusik, Videos und einem Dauerprogramm, wenn gerade niemand etwas ausgewählt hat.

🇬🇧 [English instructions](README.md)

> Immich Showcase ist ein unabhängiges Community-Projekt und steht in keiner Verbindung zum Immich-Projekt oder dessen Betreibern. „Immich“ ist der Name der Software, mit der es zusammenarbeitet.

| Anmelden | Neueste Fotos | Auswahl | Auf den Fernseher |
|---|---|---|---|
| ![Anmelden](docs/screenshots/login.png) | ![Neueste](docs/screenshots/neueste.png) | ![Auswahl](docs/screenshots/auswahl.png) | ![Fernseher](docs/screenshots/fernseher.png) |

| Fernbedienung am Handy | Suche in ganzen Sätzen |
|---|---|
| ![Fernbedienung](docs/screenshots/fernbedienung.png) | ![Suche](docs/screenshots/suche.png) |

Der Bilderrahmen (Dauerprogramm mit unscharfem Hintergrund, Datum, Ort und Uhr):

![Rahmen](docs/screenshots/rahmen.png)

*(Alle Bilder zeigen erfundene Beispielfotos und die englische Oberfläche.)*

## Was es kann
- **Suche in ganzen Sätzen** in fünf Sprachen: Personen, Zeit, Ort, Motiv.
- **Verknüpfte Filter** (Person, Jahr, Land, Fotos/Videos), „alle Fotos eines Tages“ auswählen, Rückgängig.
- **Shows** speichern, benennen und später wieder starten.
- **Fernseher:** eine Webseite, die du einmal im TV-Browser öffnest (LG webOS, Android TV, Shield, Chromecast mit Browser …). Steuerung vom Handy: Pause, vor/zurück, Musik, Stopp. Videos werden vorab für den Fernseher umgewandelt.
- **Bilderrahmen:** eigener Player für jedes Tablet (Browser oder [Fully Kiosk](https://www.fully-kiosk.com)). Ohne Wunsch läuft ein Dauerprogramm mit Uhr; eine Show aus der App unterbricht es, „Stopp“ bringt es zurück.
- **Hintergrundmusik** aus eigenen Ordnern (es wird keine mitgeliefert).
- **Sicher gebaut:** Die App kann **nie ein Foto löschen**, läuft ohne Root in einem schreibgeschützten Container, und jede Person kann ihr eigenes Immich-Konto nutzen.

## Was du brauchst
- Ein laufendes **Immich** (getestet mit 3.2.x) und ein Benutzerkonto dort.
- Einen Rechner mit **Docker und Docker Compose** (NAS, Mini-PC, Raspberry Pi – Images für amd64 und arm64).
- Für den Bilderrahmen ein **Tablet** (oder ein anderes Gerät mit Browser). Für den Fernseher einen Fernseher mit Webbrowser.

## Installation (ca. 5 Minuten)

```bash
git clone https://github.com/dirkvoss/immich-showcase.git
cd immich-showcase
cp .env.example .env
docker compose up -d
docker compose logs showcase       # zeigt einen einmaligen Einrichtungs-Code
```

Öffne `http://<server>:8090` im Browser. Der **Einrichtungsassistent** führt dich durch:

1. **Einrichtungs-Code** aus dem Protokoll eingeben (damit niemand sonst in deinem Netz die Einrichtung übernehmen kann),
2. die **Adresse deines Immich** eingeben (zum Beispiel `http://192.168.1.10:2283`),
3. mit deinem **Immich-Konto** (E-Mail + Passwort) anmelden. Immich Showcase legt einen eigenen API-Schlüssel an, **ohne Löschrechte** – dein Passwort wird nicht gespeichert,
4. eine **PIN** wählen.

Danach startet die App von selbst neu. Auf dem iPhone: Teilen → „Zum Home-Bildschirm“.

**Immich läuft im Docker auf demselben Rechner?** Entweder die IP-Adresse des Rechners wie oben nehmen, oder die App in Immichs Docker-Netzwerk hängen: in `.env` `COMPOSE_FILE=docker-compose.yml:docker-compose.immich-network.yml` und `SHOWCASE_IMMICH_NETWORK=immich_default` (Name per `docker network ls`) setzen und `http://immich_server:2283` als Adresse verwenden.

**Lieber ohne Assistent?** `RAHMEN_IMMICH_URL` und `RAHMEN_IMMICH_KEY` in die `.env` eintragen. Werte aus der `.env` haben immer Vorrang vor dem Assistenten.

## Fernseher einrichten
1. In der `.env`: `RAHMEN_WEB_TV_ZIELE=wohnzimmer=Wohnzimmer` (`kennung=Anzeigename`, bei mehreren Fernsehern kommagetrennt).
2. `docker compose up -d`
3. Am Fernseher im Browser `http://<server>:8090/tv/?ziel=wohnzimmer` öffnen und als Lesezeichen speichern. Die Seite offen lassen – sie zeigt „bereit“ und wartet.
4. Am Handy: Fotos auswählen → **Auf den Fernseher** → Fernseher, Zeit pro Foto, Reihenfolge und Musik wählen → **Start**.

## Bilderrahmen einrichten
1. In der `.env`: `RAHMEN_WEB_RAHMEN_ZIELE=rahmen=Bilderrahmen`
2. Festlegen, was der Rahmen zeigt, wenn niemand etwas ausgewählt hat (`RAHMEN_WEB_RAHMEN_*`, alles optional):
   - **Alben:** `RAHMEN_WEB_RAHMEN_ALBEN=<album-id>,<album-id>` (die IDs stehen in der Immich-Adresse des Albums)
   - **Marker-Alben:** `RAHMEN_WEB_RAHMEN_MARKER=1` – jedes Album, dessen **Beschreibung einen Marker mit „rahmen“ enthält** (z. B. `#rahmen`, `#bilderrahmen`; englisch `#frame`), kommt automatisch ins Programm. Ein Marker wie `#nurrahmen` (englisch `#onlyframe`) zeigt **nur** dieses Album, in der in der App gewählten Reihenfolge. Marker entfernen = zurück zum Normalbetrieb.
   - **Gewichtete Quellen:** `RAHMEN_WEB_RAHMEN_QUELLEN=<album-id>:70, neu14:20, *:10` (ein Album, „in den letzten 14 Tagen hochgeladen“, die ganze Bibliothek – mit Gewichten)
   - Sekunden pro Foto `RAHMEN_WEB_RAHMEN_SEK`, Hintergrund `RAHMEN_WEB_RAHMEN_FUELLUNG` (`unscharf`, `zuschnitt` oder `balken`), Bildunterschrift `RAHMEN_WEB_RAHMEN_ANZEIGE=datum,ort`, Nachtruhe `RAHMEN_WEB_RAHMEN_NACHT=22:00-06:30`
3. `docker compose up -d`
4. Am Tablet `http://<server>:8090/tv/?ziel=rahmen` im Vollbild öffnen – oder als Startseite in Fully Kiosk eintragen.
   *Tipp (Fully Kiosk):* Nutzt du die Adresse als **Bildschirmschoner**, trage sie in der Bildschirmschoner-Playlist ein und starte die App einmal neu – Fully Kiosk liest Änderungen an der Playlist erst nach einem Neustart.

## Alltag
1. App am Handy öffnen und anmelden (PIN, oder dein Immich-Konto bei `RAHMEN_WEB_AUTH=immich`).
2. **Neueste** zeigt aktuelle Fotos mit Filtern, **Suche** versteht ganze Sätze, **Meine Shows** speichert Shows.
3. Fotos antippen, um sie auszuwählen. **Diashow** läuft im Browser des Handys, **Auf den Fernseher** und **Auf den Rahmen** schicken sie an ein Gerät.
4. Während eine Show läuft, ist das Handy die Fernbedienung. **Stopp** bringt am Rahmen das Dauerprogramm zurück.

## Anmeldung
`RAHMEN_WEB_AUTH=pin` (Vorgabe: eine gemeinsame 6-stellige PIN), `immich` (jede Person meldet sich mit ihrem Immich-Konto an und sieht **nur ihre eigenen** Fotos und Shows) oder `beide`. Ohne `RAHMEN_WEB_LAN` und `RAHMEN_WEB_PROXIES` braucht jede Anfrage PIN oder Konto – das ist die sichere Vorgabe. PIN später ändern:
`docker compose exec showcase python /app/rahmen_web.py --set-pin 123456`

## Von außen erreichbar machen
Immer hinter einem **Reverse-Proxy mit HTTPS** (Nginx Proxy Manager, Caddy, Traefik …). `SHOWCASE_BIND=127.0.0.1` setzen, wenn der Proxy auf demselben Rechner läuft, und die Adresse des Proxys in `RAHMEN_WEB_PROXIES` eintragen. WebSocket-Unterstützung ist nicht nötig. Netze nur dann in `RAHMEN_WEB_LAN` aufnehmen, wenn Internetverkehr nie mit einer internen Adresse ankommen kann.

## Eigene Musik
Es wird keine mitgeliefert (Lizenzen). Zwei Wege:
- **Ordner:** mp3/ogg/m4a-Dateien in Unterordner von `/data/musik` legen (jeder Ordner = eine Sammlung), z. B. per Mount `./musik:/data/musik:ro`. Titel und Künstler kommen aus den Dateimarken oder dem Dateinamen. Eine optionale `info.json` beschreibt die Titel genauer (`name`, `stuecke` mit `datei`, `titel`, `urheber`, `lizenz`).
- **In der App:** `RAHMEN_WEB_MUSIK_UPLOAD=1` setzen, dann erscheint im Fenster „Auf den Fernseher“ der Eintrag „Eigene Musik hinzufügen …“.

## Aktualisieren
`docker compose pull && docker compose up -d` – oder `deploy/deploy.sh <version>` (Sicherung, Prüfungen, automatischer Rückweg; siehe [RELEASING.md](RELEASING.md)).

## Wenn etwas nicht klappt
| Beobachtung | Lösung |
|---|---|
| „Einrichtung erforderlich“ in der App | Noch nicht mit Immich verbunden – `/setup/` öffnen |
| HTTP 401 in der App | PIN oder Konto fehlt bzw. ist abgelaufen |
| Fernseher steht in der App auf „nicht geöffnet“ | Die TV-Adresse im Fernseher-Browser öffnen und offen lassen |
| Rahmen bleibt auf dem alten Bild / Schoner-Adresse wird ignoriert | Fully Kiosk: App nach Änderung der Playlist neu starten |
| Container erreicht Immich nicht | IP des Rechners statt `localhost` verwenden oder Immichs Docker-Netzwerk nutzen (siehe oben) |
| Sonst | `docker compose logs showcase`; im **Hilfe**-Fenster der App lässt sich ein *Support-Paket* (Diagnose ohne Geheimnisse) für einen Fehlerbericht erzeugen |

## Einstellungen
Alles Installationsspezifische steht in der `.env` – jede Einstellung ist in [.env.example](.env.example) erklärt. Deine eigene `.env` ist nie Teil des Repositorys.

## Sprachen
Oberfläche und Satzsuche gibt es auf **Deutsch, Englisch, Spanisch, Französisch und Niederländisch** (automatisch nach Browsersprache oder `?lang=xx`; Umschalter im Hilfe-Fenster). Die Übersetzungen ES/FR/NL sind maschinell erstellt – Korrekturen sind willkommen (`static/i18n/<sprache>.json`).

## Sicherheit
- Die App kann **nie Fotos löschen**; ihr API-Schlüssel hat keine Löschrechte.
- Anmeldung per PIN oder Immich-Konto, nach Fehlversuchen gesperrt (je IP und je E-Mail). Jede Person bekommt einen eigenen, widerrufbaren Schlüssel. Sitzungen laufen 90 Tage, schreibende Aufrufe brauchen einen eigenen Header.
- Der Container läuft ohne Root, mit schreibgeschütztem Dateisystem, ohne Linux-Capabilities und mit Speichergrenze.
- Die Fernseher- und Rahmen-Seiten zeigen Fotos **ohne Anmeldung** für Geräte im vertrauten Netz (`RAHMEN_WEB_LAN`) – dieses Netz klein halten.
- Sicherheitslücke gefunden? Siehe [SECURITY.md](SECURITY.md).

## Einschränkungen
- Ohne Datenbankzugang nimmt die Motivsuche („am Strand“) die besten 60 Treffer der Rangliste, statt die Ähnlichkeit exakt zu prüfen. Filter sind etwas langsamer, aber gleichwertig. Datenbankzugang ist optional (`RAHMEN_DB_DSN`).
- Noch keine Kopplung per QR-Code: Die Adresse muss einmal an jedem Gerät eingegeben werden.
- Es wird keine Musik mitgeliefert.

## Entwicklung
`pip install -r requirements-dev.txt && python -m pytest`. Versionen baut GitHub Actions aus Versions-Tags; siehe [RELEASING.md](RELEASING.md) und [CONTRIBUTING.md](CONTRIBUTING.md).

## Lizenzen von Bestandteilen
Schrift *Cormorant Garamond* (SIL OFL 1.1). Das Logo ist eigens erzeugt. Keine Musik im Repository.

## Lizenz
[GNU Affero General Public License v3.0 oder neuer](LICENSE) (AGPL-3.0-or-later), wie Immich selbst. Wer die App als Dienst für andere betreibt, muss geänderten Quelltext ebenfalls bereitstellen. Schrift: siehe `static/fonts/OFL.txt`.
