# Sicherheit

## Eine Lücke melden
Bitte **nicht** öffentlich als Issue, sondern über die private Meldung von GitHub (Reiter *Security* → *Report a vulnerability*). Du bekommst eine Antwort innerhalb von sieben Tagen.

## Was Immich Showcase darf (und was nicht)
- **Keine Löschrechte:** Der Immich-Schlüssel braucht nur Lese-Rechte plus Alben-Verwaltung. Immich Showcase löscht nie Fotos. Beim Anmelden mit dem Immich-Konto legt es für jede Person einen eigenen, in Immich einsehbaren und widerrufbaren Schlüssel „Immich Showcase“ ohne Lösch-Rechte an. Das Passwort wird nur an Immich weitergereicht und nicht gespeichert; die Immich-Sitzung wird sofort wieder beendet.
- **Zugang:** Ohne Angabe verlangt jede Anfrage eine PIN oder ein Konto. Ein vertrautes Netz (`RAHMEN_WEB_LAN`) gilt nur, wenn du es einträgst. Falsche PINs/Passwörter werden je Adresse und je E-Mail gesperrt (5 Versuche, 15 Minuten); schreibende Aufrufe brauchen einen eigenen Header.
- **Container:** läuft ohne Root, mit schreibgeschütztem Dateisystem, ohne Linux-Capabilities und mit Speichergrenze.
- **Geheimnisse:** PIN nur als scrypt-Hash, Sitzungs-Cookies signiert (90 Tage, `HttpOnly`, `SameSite=Strict`, `Secure` hinter HTTPS). Eigene Einstellungen und Schlüssel gehören in `.env` bzw. das Datenvolumen, nie ins Repository.
- **Musik-Upload** ist standardmäßig aus; wenn an, nur für angemeldete Personen, nur mp3/ogg/m4a, mit Größengrenzen, Dateien werden mit `ffprobe` geprüft.
- **Selbsttest nach dem Deploy** (`postdeploy.py`) hat einen rein lesenden Zugang nur von der Loopback-Adresse im Container mit einem beim Start erzeugten Geheimnis.

## Empfehlungen für den Betrieb
- Immer hinter einen Reverse-Proxy mit HTTPS; `SHOWCASE_BIND=127.0.0.1`, wenn der Proxy auf demselben Rechner läuft.
- Die Adresse eines Tunnels/Proxys, über den Internetverkehr hereinkommt, **nie** in `RAHMEN_WEB_LAN` eintragen.
- Updates regelmäßig einspielen (`docker compose pull && docker compose up -d`).
