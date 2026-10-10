# Frameside

<p align="center"><img src="static/icon-192.png" width="96" alt="Symbol von Frameside"></p>

**Zeige deine [Immich](https://immich.app)-Fotos auf dem Fernseher und im Bilderrahmen – und lass die ganze Familie das vom Handy aus tun.**
Suche in ganzen Sätzen („Oma und Anna Weihnachten 2019 am Strand“), tippe die Fotos an, gib der Show einen Namen und schick sie an den Fernseher im Wohnzimmer oder den Bilderrahmen im Flur. Mit Hintergrundmusik, Videos und einem Dauerprogramm, wenn gerade niemand etwas ausgewählt hat.

🇬🇧 [English instructions](README.md) · ☕ [Danke sagen auf Ko-fi](https://ko-fi.com/frameside) (Frameside ist kostenlos, Spenden sind freiwillig)

> Frameside ist ein unabhängiges Community-Projekt und steht in keiner Verbindung zum Immich-Projekt oder dessen Betreibern. „Immich“ ist der Name der Software, mit der es zusammenarbeitet.

<p align="center"><img src="docs/demo.gif" width="720" alt="Frameside Ablauf"><br><sub><em>(Ablauf aus den Screenshots darunter; alle Fotos sind erfundene Beispiele.)</em></sub></p>

| Anmelden | Neueste Fotos | Auswahl | Auf den Fernseher |
|---|---|---|---|
| ![Anmelden](docs/screenshots/login.png) | ![Neueste](docs/screenshots/neueste.png) | ![Auswahl](docs/screenshots/auswahl.png) | ![Fernseher](docs/screenshots/fernseher.png) |

| Fernbedienung am Handy | Suche in ganzen Sätzen |
|---|---|
| ![Fernbedienung](docs/screenshots/fernbedienung.png) | ![Suche](docs/screenshots/suche.png) |

Der Bilderrahmen (Dauerprogramm mit unscharfem Hintergrund, Datum, Ort und Uhr):

![Rahmen](docs/screenshots/rahmen.png)

Mit Wetter und Terminen oben rechts, Gerätekopplung per Code/QR am Fernseher und die Geräte-Ansicht in der App:

| Rahmen mit Wetter und Terminen | Gerät koppeln (TV/Tablet) | Geräte-Ansicht |
|---|---|---|
| ![Wetter](docs/screenshots/rahmen-zusatz.png) | ![Kopplung](docs/screenshots/koppeln.png) | ![Geräte](docs/screenshots/geraete.png) |

*(Alle Bilder zeigen erfundene Beispielfotos und die englische Oberfläche.)*

## Was es kann
- **Suche in ganzen Sätzen** in fünf Sprachen: Personen, Zeit, Ort, Motiv.
- **Verknüpfte Filter** (Person, Jahr, Land, Fotos/Videos), „alle Fotos eines Tages“ auswählen, Rückgängig.
- **Shows** speichern, benennen und später wieder starten.
- **Fernseher:** eine Webseite, die du einmal im TV-Browser öffnest (LG webOS, Android TV, Shield, Chromecast mit Browser …). Steuerung vom Handy: Pause, vor/zurück, Musik, Stopp. Videos werden vorab für den Fernseher umgewandelt.
- **Bilderrahmen:** eigener Player für jedes Tablet – **ein ganz normaler Browser genügt** ([Fully Kiosk](https://www.fully-kiosk.com) ist ein optionales Extra). Ohne Wunsch läuft ein Dauerprogramm mit Uhr; eine Show aus der App unterbricht es, „Stopp“ bringt es zurück. **Mehrere Rahmen** sind möglich: in der App anlegen und einstellen (Programm-Quellen, Zeitplan, Nachtruhe, Fully Kiosk), eine Show an einen oder mehrere schicken – oder jedem Rahmen eine eigene Show geben.
- **Hintergrundmusik** aus eigenen Ordnern (es wird keine mitgeliefert).
- **Sicher gebaut:** Die App kann **nie ein Foto löschen**, läuft ohne Root in einem schreibgeschützten Container, und jede Person kann ihr eigenes Immich-Konto nutzen.

## Was du brauchst
- Ein laufendes **Immich** (getestet mit 3.2.x) und ein Benutzerkonto dort.
- Einen Rechner mit **Docker und Docker Compose** (NAS, Mini-PC, Raspberry Pi – Images für amd64 und arm64).
- Für den Bilderrahmen ein **Tablet** (oder ein anderes Gerät mit Browser). Für den Fernseher einen Fernseher mit Webbrowser.

## Installation (ca. 5 Minuten)

> 📖 **Mit Bildern, Schritt für Schritt:** [Erste Schritte – illustrierte Anleitung](docs/anleitung.md) · [Frameside auf einem anderen Rechner (z. B. Raspberry Pi)](docs/anleitung-externer-rechner.md)

**Ein Befehl** auf dem Rechner mit Docker (Linux, NAS, Mini-PC; Raspberry Pi geht auch):

```bash
curl -fsSL https://raw.githubusercontent.com/dirkvoss/frameside/main/install.sh | bash
```

Das Programm
- lädt Frameside nach `~/immich-showcase`,
- **erkennt Immich**, wenn es auf demselben Rechner in Docker läuft, und bindet die App an dessen Docker-Netz an (keine Datei zu bearbeiten),
- startet alles und zeigt am Ende einen **fertigen Einrichtungs-Link** (mit QR-Code, wenn `qrencode` installiert ist), den du im Browser öffnest.

Der **Einrichtungsassistent** hat drei kurze Schritte:
1. **Immich verbinden:** Immich wird meist von selbst gefunden. Sonst die Adresse eintragen (z. B. `http://192.168.1.10:2283`).
2. **Anmelden** mit deinem Immich-Konto (E-Mail + Passwort). Frameside legt einen eigenen API-Schlüssel an, **ohne Löschrechte**; dein Passwort wird nicht gespeichert.
3. **Wer darf zugreifen?** **Gemeinsame PIN** (empfohlen; im Heimnetz auf Wunsch ohne Eingabe) oder **Immich-Konten** (jede Person sieht nur ihre eigenen Fotos).

Am Ende zeigt die Seite einen **QR-Code für die iPhone-App** und die Adresse für Fernseher und Tablets. Danach am Fernseher oder Tablet im Browser diese Adresse öffnen: Das Gerät erscheint in der App unter „Geräte → ＋ Gerät hinzufügen“ von selbst, du gibst nur einen Namen ein (der Code bleibt als Ausweg). Eine „Erste Schritte“-Liste in der Oberfläche begleitet dich, bis alles läuft.

Weitere Wege:
- **Noch kein Immich?** `./install.sh --with-immich` startet Immich **und** Frameside zusammen.
- **Anderer Port:** `./install.sh --port 80` (dann genügt am Fernseher die reine IP-Adresse).
- **Per Hand** (ohne Skript): `cp .env.example .env`, `docker compose up -d`, `docker compose logs showcase` zeigt den Einrichtungs-Code, dann `http://<server>:8090/setup/` öffnen. Lieber ohne Assistent? `RAHMEN_IMMICH_URL` und `RAHMEN_IMMICH_KEY` in die `.env` eintragen; Werte aus der `.env` haben immer Vorrang.
- **NAS und Heimserver mit Oberfläche:** Fertige Anleitungen für **Synology** (Container Manager), **Unraid** (Vorlage), **TrueNAS** und **Portainer** liegen in `examples/`.
- Auf dem iPhone ohne App: Teilen → „Zum Home-Bildschirm“. Mit App (die iPhone-App kommt bald in den App Store, bis dahin über TestFlight): sie **findet den Server im WLAN selbst**.

## Was kann als Bilderrahmen dienen?
Jedes Gerät mit einem **Webbrowser**, das eine Adresse öffnen kann. **Ein Kiosk-Modus oder Zusatz-Apps wie Fully Kiosk sind nicht nötig** – der Browser genügt. Die Seite bittet den Browser, den Bildschirm wach zu halten; wo das nicht klappt, stellst du die Auto-Sperre des Geräts auf „Nie“. Ein Kiosk-Modus (Vollbild, nichts anderes erreichbar) ist nur ein Komfort, den du bei Bedarf dazunehmen kannst.

| Gerät | So geht es |
|---|---|
| **Raspberry Pi + beliebiger Monitor/Fernseher** (günstigste Dauerlösung) | `./examples/raspberry-pi/setup-kiosk.sh http://<server>:8090/tv/` – installiert Chromium im Kiosk-Modus und startet es beim Einschalten (siehe unten) |
| **Android-Tablet oder altes Handy** | Kostenlos und ausreichend: Chrome → Adresse öffnen → „Zum Startbildschirm hinzufügen“ → von dort öffnen (Vollbild) und die Bildschirm-Auszeit auf „nie“ stellen. *Optional:* [Fully Kiosk](https://www.fully-kiosk.com) (einmalig ca. 8 €) schaltet den Bildschirm nachts wirklich aus und meldet den Akkustand |
| **iPad / altes iPhone** | Safari → Adresse öffnen → Teilen → „Zum Home-Bildschirm“; als Kiosk-Modus den **Geführten Zugriff** nutzen (Einstellungen → Bedienungshilfen) und die Auto-Sperre auf „Nie“ stellen |
| **Fernseher, Fire TV, Android TV, Chromecast mit Google TV, Shield** | Browser öffnen, Adresse eingeben, als Lesezeichen speichern |
| **Alter Laptop / Mini-PC** | Chrome mit `--kiosk <Adresse>` im Autostart |

Die Adresse `http://<server>:8090/tv/` **ohne** `?ziel=…` öffnen, um das Gerät per Code zu koppeln: Es zeigt einen Code (und einen QR-Code), den du in der App unter **📡 Geräte** eingibst und dabei wählst, welcher Fernseher/Rahmen es ist.

**Nicht möglich:** fertige Rahmen mit geschlossener Software (z. B. Aura, Skylight, Nixplay, Pix-Star, Frameo). Sie nehmen Fotos nur über ihre eigene App oder per E-Mail an und lassen keine freie Adresse zu.

### Raspberry Pi als Server in einem Befehl
Auf dem Pi (Raspberry Pi OS **Lite, 64-Bit**, im Raspberry Pi Imager Name, WLAN und SSH einstellen) per SSH:
`curl -fsSL https://raw.githubusercontent.com/dirkvoss/frameside/main/examples/raspberry-pi/install-pi.sh | bash -s -- --hostname showcase`
Das Skript installiert Docker und Frameside, meldet den Server im Netz an (die iPhone-App findet ihn selbst, im Heimnetz auch `http://showcase.local:8090`) und zeigt den Einrichtungs-Link. Läuft Immich auf einem anderen Rechner, trägst du dessen Adresse im Assistenten ein, siehe [die Anleitung dazu](docs/anleitung-externer-rechner.md).

### Raspberry Pi als Bilderrahmen-Anzeige in 5 Minuten
1. **Raspberry Pi OS mit Desktop** aufspielen (Raspberry Pi Imager), dort WLAN/SSH einrichten, starten und automatisch am Desktop anmelden lassen.
2. Auf dem Pi im Terminal: `curl -O https://raw.githubusercontent.com/dirkvoss/frameside/main/examples/raspberry-pi/setup-kiosk.sh && chmod +x setup-kiosk.sh && ./setup-kiosk.sh http://<server>:8090/tv/`
3. `sudo reboot`. Der Pi startet im Vollbild und zeigt den Kopplungs-Code. Entfernen: `./setup-kiosk.sh --entfernen`.

*Das Raspberry-Pi-Skript ist für Raspberry Pi OS (Bookworm) geschrieben, aber nicht auf jedem Pi-Modell getestet – Rückmeldungen sind willkommen.*

## Fernseher einrichten
1. In der `.env`: `RAHMEN_WEB_TV_ZIELE=wohnzimmer=Wohnzimmer` (`kennung=Anzeigename`, bei mehreren Fernsehern kommagetrennt).
2. `docker compose up -d`
3. Am Fernseher im Browser `http://<server>:8090/tv/?ziel=wohnzimmer` öffnen und als Lesezeichen speichern. Die Seite offen lassen – sie zeigt „bereit“ und wartet.
4. Am Handy: Fotos auswählen → **Auf den Fernseher** → Fernseher, Zeit pro Foto, Reihenfolge und Musik wählen → **Start**.

## Bilderrahmen einrichten
**Fernseher ohne lange Adresse:** Am Fernseher genügt im Browser die Adresse des Servers (zum Beispiel `192.168.1.20:8090`, oder nur die IP mit `./install.sh --port 80`). Fernseher-Browser (LG, Samsung, Android TV, Fire TV, Chromecast) werden automatisch auf die Fernseher-Seite geleitet, die einen Code zum Koppeln in der App zeigt. Der Geräte-Assistent zeigt diese kurze Adresse und lässt sie ändern. Für Fortgeschrittene, nur bei **Android TV / Shield / Fire TV**: Der Server kann die Seite per ADB selbst öffnen (Geräte-Assistent → „Für Fortgeschrittene: per ADB direkt am Fernseher öffnen“). Dafür muss am Fernseher die Entwickler-Funktion „Netzwerk-Debugging“ (ADB) eingeschaltet sein – bei den meisten Geräten ist sie aus – und der Server den Fernseher im Netz erreichen. Bei allen anderen Fernsehern ist die kurze Adresse der Weg.

**Einstellungen in der App:** Konto-Menü → **⚙ Einstellungen** enthält Vorgaben für alle Rahmen, Wetter-Ort und Kalender-Link (mit Test), Pushover-Benachrichtigungen, Spitznamen für Personen und die Adresse der Fernseher-Seite. Dort gespeicherte Werte haben Vorrang vor den Umgebungsvariablen; Sicherheitsrelevantes (Anmeldeart, vertrautes Netz, Proxys, Immich-Schlüssel) bleibt in der `.env`. **Tablet-Steuerung:** Läuft die Rahmen-Seite in Fully Kiosk mit aktivierter *JavaScript-Schnittstelle* (Fully Plus), schaltet das Tablet seinen Bildschirm nachts selbst aus und meldet den Akku – ohne Adresse und Passwort. Sonst trägst du in den Geräte-Einstellungen Adresse und Passwort der Fully-Fernbedienung ein. Beides ist optional.

**Am einfachsten in der App:** **📡 Geräte** → **＋ Gerät hinzufügen** → Art „Bilderrahmen“, Name vergeben, mit ⚙ später Sekunden pro Foto, Hintergrund, Bildunterschrift, Nachtruhe, Dauerprogramm (Quellen mit Gewicht), Zeitplan und Fully Kiosk einstellen. Die Geräteliste liegt dann in `rahmen_web_geraete.json` im Datenordner und hat Vorrang vor den Variablen unten (die gelten nur als Startwerte, bis du in der App etwas änderst). Am Tablet öffnest du `http://<server>:8090/tv/` und koppelst es mit dem Code.

Der Weg über die `.env`:
1. In der `.env`: `RAHMEN_WEB_RAHMEN_ZIELE=rahmen=Bilderrahmen`
2. Festlegen, was der Rahmen zeigt, wenn niemand etwas ausgewählt hat (`RAHMEN_WEB_RAHMEN_*`, alles optional):
   - **Alben:** `RAHMEN_WEB_RAHMEN_ALBEN=<album-id>,<album-id>` (die IDs stehen in der Immich-Adresse des Albums)
   - **Marker-Alben:** `RAHMEN_WEB_RAHMEN_MARKER=1` – jedes Album, dessen **Beschreibung einen Marker mit „rahmen“ enthält** (z. B. `#rahmen`, `#bilderrahmen`; englisch `#frame`), kommt automatisch ins Programm. Ein Marker wie `#nurrahmen` (englisch `#onlyframe`) zeigt **nur** dieses Album, in der in der App gewählten Reihenfolge. Marker entfernen = zurück zum Normalbetrieb.
   - **Gewichtete Quellen:** `RAHMEN_WEB_RAHMEN_QUELLEN=<album-id>:70, neu14:20, *:10` (ein Album, „in den letzten 14 Tagen hochgeladen“, die ganze Bibliothek – mit Gewichten)
   - Sekunden pro Foto `RAHMEN_WEB_RAHMEN_SEK`, Hintergrund `RAHMEN_WEB_RAHMEN_FUELLUNG` (`unscharf`, `zuschnitt` oder `balken`), Bildunterschrift `RAHMEN_WEB_RAHMEN_ANZEIGE=datum,zeit,ort`, Nachtruhe `RAHMEN_WEB_RAHMEN_NACHT=22:00-06:30`
3. `docker compose up -d`
4. Am Tablet `http://<server>:8090/tv/?ziel=rahmen` im Browser öffnen (Vollbild) – wer Fully Kiosk nutzt, trägt sie dort als Startseite ein.
   *Tipp (Fully Kiosk):* Nutzt du die Adresse als **Bildschirmschoner**, trage sie in der Bildschirmschoner-Playlist ein und starte die App einmal neu – Fully Kiosk liest Änderungen an der Playlist erst nach einem Neustart.

## Geräte per Code koppeln (keine Adressen tippen)
1. Am Fernseher oder Tablet **`http://<server>:8090/tv/`** öffnen (ohne `?ziel=`). Es erscheint ein 6-stelliger **Code** und ein **QR-Code**.
2. In der App **📡 Geräte → ＋ Gerät hinzufügen** antippen. Das Gerät erscheint dort von selbst („LG-Fernseher gefunden“): Namen eingeben, **Verbinden** tippen. Klappt das nicht, den Code vom Bildschirm unter *Gerät koppeln* eingeben (oder den QR-Code mit der Handykamera scannen).
3. Das Gerät merkt sich seine Rolle. Danach genügt `/tv/` allein. (Welche Fernseher und Rahmen es gibt, steht weiterhin in der `.env`, siehe unten.)

## Die Geräte-Ansicht
**📡 Geräte** in der App listet jeden Fernseher und Rahmen: online oder offline, was gerade läuft, seit wann das aktuelle Bild zu sehen ist und wann das Gerät zuletzt gesehen wurde.

## Mehrere Rahmen, Zeitplan, „Heute vor Jahren“
- **Mehrere Rahmen:** In der Auswahlleiste setzt du Häkchen bei den Rahmen, die die Show zeigen sollen (dieselbe Show an mehrere, oder nacheinander verschiedene). Unter „Meine Shows“ verteilt „Shows auf die Rahmen verteilen“ je Rahmen eine eigene Show. Jeder Rahmen hat seinen eigenen Zustand – laufende Show, „Zurück“, Reihenfolge; der Banner oben wechselt zwischen ihnen.
- **Eigenes Programm je Rahmen:** `RAHMEN_WEB_RAHMEN_QUELLEN_FLUR=<album-id>:70, neu14:30` (Kennung in Großbuchstaben) – siehe `.env.example`.
- **Zeitplan:** `RAHMEN_WEB_RAHMEN_ZEITPLAN=Mo-Fr 18:00-22:00 = <album-id>:1; Sa,So 08:00-20:00 = heute:50, *:50` – zu verschiedenen Zeiten andere Quellen (auch je Rahmen, Bereiche über Mitternacht sind erlaubt).
- **Heute vor Jahren:** die Quelle `heute` (oder `heute5` = ±5 Tage) zeigt Fotos von diesem Tag aus früheren Jahren.
- **Einblendungen am Rahmen – frei anordnen:** Uhrzeit, heutiges Datum, Datum und Ort des Fotos, Wetter, Termine, Geburtstage und der Show-Titel lassen sich einzeln ein- und ausschalten, per Ziehen an eine beliebige Stelle der Vorschau legen, in der Größe ändern und in Farbe und Schrift anpassen – **für jeden Rahmen einzeln** unter Geräte → ⚙ → „Anzeige auf diesem Rahmen“ (ein neuer Rahmen startet mit den Standardwerten; „Anordnung übernehmen von“ kopiert die eines anderen Rahmens). Änderungen erscheinen am laufenden Rahmen sofort, auch während einer Show.
- **Familie und Feste:** Grüße mit Foto an einen Rahmen (ein Tipp am Rahmen schickt ein ❤️ zurück) und ein **Gäste-Upload per QR-Code** für Feiern – Gäste laden Fotos ohne Anmeldung hoch, sie erscheinen gleich am Rahmen.
- **Mehr Leben am Rahmen** (je Rahmen unter Geräte → ⚙ einstellbar): sanfter Zoom, zwei Hochkant-Fotos nebeneinander, Erinnerungen „An diesem Tag“ mit „Vor 5 Jahren“, mehr Fotos einer Person an ihrem Geburtstag, Notizen an den Rahmen („Heute Abend Pizza“) und Nachtruhe nach Sonnenstand. Per Pushover kommen Meldungen bei Ausfällen von Rahmen oder Immich, knappem Speicher, einem veralteten Handy-Kalender und ein Monatsbrief.
- **Wetter und Termine** am Rahmen: `RAHMEN_WEB_WETTER_ORT=52.52,13.40` (open-meteo.com, kostenlos, ohne Konto – dein **Server** fragt ab, nur die Koordinaten werden übertragen). Der Wetter-Ort lässt sich je Rahmen einstellen (z. B. Belgrad für einen Rahmen in Serbien; ohne eigenen Ort gilt der aus den Einstellungen). Die Termine kommen entweder von den **Handys** der Familie (iPhone-App → App-Einstellungen → „Meine Termine auf dem Rahmen zeigen“: jede Person wählt ihre Kalender, es sind keine Links oder Passwörter nötig, auch iCloud-, Google- und Exchange-Kalender gehen; **welcher Rahmen die Termine eines Handys zeigt, legst du beim Rahmen unter ⚙ fest** – neue Handys erscheinen zunächst auf keinem) und/oder aus einem öffentlichen **iCalendar-Link** (`RAHMEN_WEB_KALENDER_URL`, Google/Nextcloud/Apple „geheime iCal-Adresse“). Der Rahmen zeigt die nächsten Termine des heutigen Tages, ist heute nichts mehr, die von morgen; teilen mehrere Handys, steht ein farbiges Kürzel der Person davor. Geburtstage aus dem iPhone-Geburtstagskalender erscheinen als eigene Zeile („🎂 Omas Geburtstag“). Es erscheint nur, was du einrichtest.

## Rahmenprogramm nach Person
`person=<name>` bei den Quellen: `RAHMEN_WEB_RAHMEN_QUELLEN=person=Anna Muster:60, person=oma:20, *:20` zeigt Fotos dieser Person (Name wie in Immich oder ein Spitzname aus `RAHMEN_WEB_ALIASE`; `Anna+Ben` = beide zusammen). Ein unbekannter Name wird übersprungen, die anderen Quellen laufen weiter.

## Server per Bonjour anmelden (iPhone-App findet ihn selbst)
Die iPhone-App sucht Server im eigenen WLAN (/24) und über bekannte Namen. Zusätzlich kann sich der Server **per Bonjour (mDNS)** anmelden, dann erscheint er in der App auch dann, wenn er in einem anderen Netz steht (der Router muss Bonjour weiterleiten, bei UniFi die Einstellung „mDNS“).
- Einschalten: `./install.sh --bonjour`, oder in `.env` `COMPOSE_FILE=docker-compose.yml:docker-compose.bonjour.yml` eintragen und `docker compose up -d`.
- Dahinter läuft ein kleiner zusätzlicher Container (`bonjour.py`) im **Host-Netzwerk**, weil Bonjour-Meldungen aus dem normalen Docker-Netz nicht ins Heimnetz kommen. Er meldet nur Name, Port und Anmeldeart (`_showcase._tcp`), keine Daten.
- **Nur Docker unter Linux.** Unter Docker Desktop (Mac/Windows) gibt es kein Host-Netzwerk zum LAN; dort bleibt die Suche im eigenen Netz.

## Eigene Fotos vom Handy senden („📤 Meine Fotos“)
Fotos aus der Mediathek des Handys werden an den Server geschickt, dort in **Immich** im Album „Showcase-Uploads“ abgelegt und zur Auswahl gelegt – so lassen sie sich mit Fotos aus Immich mischen und auf den Rahmen schicken. Die Fotos sind danach dauerhaft in Immich (der Schlüssel hat kein Löschrecht).
- **Anmeldung mit PIN:** ein gemeinsamer Immich-Schlüssel mit Upload-Recht (`RAHMEN_IMMICH_UPLOAD_KEY`, Rechte siehe `.env.example`). Der Einrichtungsassistent trägt ihn ein, wenn er den Schlüssel selbst anlegt.
- **Anmeldung mit dem Immich-Konto** (`RAHMEN_WEB_AUTH=immich`): **jede Person lädt in ihr eigenes Konto** hoch, mit ihrem eigenen Schlüssel und ihrem eigenen Album. Ältere Schlüssel ohne Upload-Recht werden beim nächsten Anmelden mit E-Mail und Passwort automatisch ersetzt.
- Nur Fotos (JPEG, PNG, HEIC, WebP), höchstens 40 MB je Foto.

## Rahmen an einem anderen Ort (Eltern, Ferienhaus)
Ein Tablet außerhalb deines Heimnetzes holt sich Programm und Fotos über das Internet von deinem Server und lässt sich wie jeder andere Rahmen aus der App beschicken.
1. **Server von außen erreichbar machen:** Der Server braucht eine Adresse mit HTTPS, die das Tablet erreicht (zum Beispiel über einen Reverse-Proxy). Beschränke sie, wenn möglich, auf das, was die Rahmen-Seite braucht: `/tv/`, `/api/tv/`, `/api/vorschau/`, `/api/rahmen/`, `/api/bildinfo/`, `/api/koppeln/`, `/api/version`, `/api/config`, `/api/login` (nur für PIN-Geräte) und die Dateien `/i18n.js`, `/i18n/`, `/fonts/`, `/qrcode.js`, `/icon-512.png`; die App selbst muss nicht von außen erreichbar sein.
2. **Rahmen anlegen:** App → **📡 Geräte** → **＋ Gerät hinzufügen** → Bilderrahmen, mit eigenem Namen und eigenem **Dauerprogramm** (zum Beispiel ein Album „Für die Eltern“ und „neu in den letzten 14 Tagen“).
3. **Koppeln, solange das Tablet noch bei dir ist:** Am Tablet im Browser `https://<deine-adresse>/tv/` öffnen, es zeigt einen Code. In der App unter *Geräte → Gerät koppeln* den Code eingeben und den Rahmen wählen. Außerhalb des Heimnetzes bekommt das Tablet dabei einen **eigenen, lange gültigen Zugang**, der nur die Rahmen-Seiten öffnet (nicht die App, nicht deine Fotos-Übersicht) und je Gerät widerrufbar ist (⚙ am Gerät → *Zugang widerrufen*). Er wird bei jeder Nutzung erneuert und läuft praktisch nie ab (nur nach über 400 Tagen ohne Verbindung).
4. **Testen wie von außen:** Das Tablet über den Hotspot deines Handys laufen lassen, Strom ziehen, WLAN aus und an. Das Dauerprogramm läuft mit den geladenen Fotos weiter, wenn das Netz ausfällt; kommt es zurück, verbindet sich die Seite von selbst.
5. **Wenn niemand vor Ort ist:** Mit **Fully Kiosk Plus** startet das Tablet nach einem Neustart die Seite von selbst (*Start-URL*, *Beim Start öffnen*, *Bildschirm anlassen*, *Neu laden bei Netzwerk-Wiederkehr*, *Neustart der Anzeige nachts*). Unter ⚙ → *Wartung und Zugang von außen* kannst du aus der Ferne die **Seite neu laden** und die **Anzeige neu starten** und einstellen, nach wie vielen Minuten ohne Verbindung du eine **Meldung aufs Handy** bekommst (Pushover). Bei komplett leerem Akku muss jemand den Einschalter drücken.

## Tablet-Bildschirm nachts ausschalten (optional, mit Fully Kiosk)
*Nur ein Komfort:* Im normalen Browser wird der Rahmen nachts einfach schwarz und läuft weiter; der Bildschirm bleibt dabei eingeschaltet.

Mit `RAHMEN_WEB_RAHMEN_NACHT=22:00-06:30` wird der Rahmen schwarz. Fully Kiosk kann den **Bildschirm wirklich ausschalten** (spart Strom, schont das Display): In Fully *Remote Administration* aktivieren und ein Passwort setzen, dann `RAHMEN_WEB_FULLY_RAHMEN=<Adresse des Tablets>` und `RAHMEN_WEB_FULLY_PASSWORT=…` eintragen. Geschaltet wird nur beim **Wechsel** (ein Aufwecken von Hand wird nicht überstimmt). Unter **📡 Geräte** kannst du den Bildschirm von Hand schalten, siehst den **Akkustand** und bekommst eine Pushover-Meldung, wenn das Tablet fast leer ist und nicht lädt.

## Home Assistant
Fertige Sensoren, Knöpfe und Beispiele stehen in [`examples/home-assistant/immich_showcase.yaml`](examples/home-assistant/immich_showcase.yaml): Zustand jedes Fernsehers/Rahmens (offline / bereit / spielt / Dauerprogramm), ein Online-Sensor und Befehle (Pause, weiter, Stopp, gespeicherte Show starten, Bildschirm an/aus) als `rest_command`. Die Adresse von Home Assistant muss in `RAHMEN_WEB_LAN` stehen. API: `GET /api/ha/status`, `POST /api/ha/steuer|show|bildschirm` (Header `X-Rahmen: 1`).

## Installationshilfe
`./install.sh` startet Frameside und zeigt Adresse und Einrichtungs-Code. **Noch kein Immich?** `./install.sh --with-immich` startet **Immich und Frameside zusammen** (siehe `examples/immich-stack/`).

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
Im Ordner mit der `docker-compose.yml`: `docker compose pull && docker compose up -d`. Daten und Einstellungen bleiben erhalten (oder `deploy/deploy.sh <version>` mit Sicherung, Prüfungen und automatischem Rückweg, siehe [RELEASING.md](RELEASING.md)). Die Statusseite („Alles in Ordnung?“ im Konto-Menü) **weist auf neuere Versionen hin** (sie fragt dafür höchstens alle 6 Stunden bei GitHub nach; abschaltbar mit `RAHMEN_WEB_UPDATE_PRUEFEN=0`).

**Automatisch:** Mit [Watchtower](examples/watchtower/docker-compose.yml) aktualisiert sich Frameside jede Nacht von selbst (der Container trägt schon das nötige Label).

## Wenn etwas nicht klappt
| Beobachtung | Lösung |
|---|---|
| „Einrichtung erforderlich“ in der App | Noch nicht mit Immich verbunden – `/setup/` öffnen |
| HTTP 401 in der App | PIN oder Konto fehlt bzw. ist abgelaufen |
| Fernseher steht in der App auf „nicht geöffnet“ | Die TV-Adresse im Fernseher-Browser öffnen und offen lassen |
| Rahmen bleibt auf dem alten Bild / Schoner-Adresse wird ignoriert | Fully Kiosk: App nach Änderung der Playlist neu starten |
| Container erreicht Immich nicht | IP des Rechners statt `localhost` verwenden oder Immichs Docker-Netzwerk nutzen (siehe oben) |
| Sonst | `docker compose logs showcase`; im **Hilfe**-Fenster der App lässt sich ein *Support-Paket* (Diagnose ohne Geheimnisse) für einen Fehlerbericht erzeugen |

## Problem melden oder etwas vorschlagen
- In der App: **Hilfe → 🐞 Problem melden** (öffnet GitHub mit eingetragener Version) – bitte das **Support-Paket** aus demselben Fenster anhängen (Diagnose ohne Passwörter, PIN oder Schlüssel).
- Wünsche und Ideen: **Hilfe → 💡 Wunsch oder Idee** oder der [Issue-Tracker](https://github.com/dirkvoss/frameside/issues).
- Fragen und Hilfe bei der Einrichtung: [Diskussionen](https://github.com/dirkvoss/frameside/discussions) – Deutsch und Englisch sind beide in Ordnung.

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
- Es wird keine Musik mitgeliefert.

## Entwicklung
`pip install -r requirements-dev.txt && python -m pytest`. Versionen baut GitHub Actions aus Versions-Tags; siehe [RELEASING.md](RELEASING.md) und [CONTRIBUTING.md](CONTRIBUTING.md).

## Lizenzen von Bestandteilen
Schrift *Cormorant Garamond* (SIL OFL 1.1). QR-Code-Erzeuger *qrcode-generator* von Kazuhiko Arase (MIT, `static/qrcode.js`). Das Logo ist eigens erzeugt. Keine Musik im Repository.

## Lizenz
[GNU Affero General Public License v3.0 oder neuer](LICENSE) (AGPL-3.0-or-later), wie Immich selbst. Wer die App als Dienst für andere betreibt, muss geänderten Quelltext ebenfalls bereitstellen. Schrift: siehe `static/fonts/OFL.txt`.
