# Versionen veröffentlichen und ausliefern

## Ablauf
1. **Entwickeln und testen** (Entwicklungsinstanz, `python -m pytest`).
2. **Push** auf `main`. GitHub Actions führt die Tests aus und baut das Docker-Image (ohne es zu veröffentlichen).
3. **Version freigeben:** `git tag v1.2.3 && git push origin v1.2.3`. Nur wenn die Tests grün sind, baut Actions das Image und legt es unter `ghcr.io/<konto>/immich-showcase:1.2.3` ab.
4. **Auf dem Server:** `deploy/deploy.sh 1.2.3`.

## Was `deploy.sh` tut
1. Image holen (bricht ab, wenn es die Version nicht gibt) – `--dry-run` hört hier auf.
2. **Sicherung** von Compose-Datei, `.env`, `container.env` und `data/` (ohne Zwischenspeicher, `SHOWCASE_BACKUP_EXCLUDE`) nach `backups/showcase-<zeit>-v<alt>.tgz`; die letzten 10 bleiben.
3. Version in `.env` umstellen, `docker compose up -d`.
4. **Gesundheit:** `/api/config` meldet die neue Version und `/api/me` antwortet (bis 90 s).
5. **Prüfungen nach dem Deploy** (`postdeploy.py` im Container, nur lesend): Konfiguration und Version, Oberfläche und Dateien, Übersetzung, Sperre ohne Anmeldung, Rahmen-/Fernseher-Dienste, Musik, und gegen Immich Filter/Zähler, Vorschaubild, Suche und das Dauerprogramm des Rahmens. Es startet nichts auf Fernseher oder Rahmen.
6. **Bei Fehler automatisch zurück** auf die vorherige Version (wieder geprüft). Meldet auch das nichts Gutes, bleibt die Sicherung für den Handbetrieb.

Weitere Aufrufe: `deploy.sh --rollback` (zurück zur vorherigen Version), `deploy.sh --status`.

## Einmalige Einrichtung auf dem Server
- `docker-compose.yml` nach `docker-compose.example.yml`, mit `image: ghcr.io/<konto>/immich-showcase:${SHOWCASE_VERSION}`.
- Heißt der Dienst in deiner Compose-Datei nicht `showcase`: in `deploy.conf` `SHOWCASE_SERVICE=<name>` setzen.
- Ist das Repository (und damit das Image) privat: einmal anmelden – Token mit dem Recht *read:packages*, **nicht** im Chat oder in Dateien im Repository ablegen:
  ```
  read -rs T; echo "$T" | docker login ghcr.io -u <konto> --password-stdin; unset T
  ```
- `deploy/deploy.sh` nach `<verzeichnis>/deploy/` kopieren, daneben optional `deploy.conf` mit `SHOWCASE_*`-Einstellungen (Beispiel: `SHOWCASE_EXTRA_BACKUP="/var/lib/bilderrahmen"`, `SHOWCASE_BACKUP_EXCLUDE="data/videos data/tv data/musik"`, `SHOWCASE_IMAGE=ghcr.io/<konto>/immich-showcase`).

## Testebenen
1. **Vor der Freigabe (GitHub Actions, blockiert das Veröffentlichen):** `python -m pytest` (Suchsprache, Zugang, Filter, Fernseher, Rahmen, Musik, Anmeldung, Deploy-Skript, `postdeploy.py`), Prüfung der Compose-Dateien, Image-Bau und **Rauchtest des fertigen Containers** (`tests/smoke_container.sh`).
2. **Beim Deploy (auf dem Server, mit automatischem Rückweg):** `postdeploy.py` gegen die laufende Instanz, siehe oben. Läuft jedes Mal; ausschalten nur mit `SHOWCASE_POSTDEPLOY=0`.
3. **Von Hand:** `docker compose exec showcase python /app/postdeploy.py` jederzeit, auch als Überwachung (z. B. täglich per Cron).

Der Selbsttest-Zugang von `postdeploy.py` gilt nur von der Loopback-Adresse im Container, nur lesend und nur mit einem beim Start erzeugten Geheimnis aus einer nur im Container lesbaren Datei.

## Tests
`pip install -r requirements-dev.txt && python -m pytest`. Sie prüfen die Suchsprache (de/en), die Übersetzungsdatei, Zugang/PIN/Sperre, Filter, Fernseher, den Rahmen-Player, die Betriebsarten und das Deploy-Skript selbst (mit vorgetäuschtem Docker) – ohne Netzwerk und ohne echtes Immich.

## Entwicklungsinstanz
`dev/`: ein eigenes Test-Immich (`dev/seed_immich.py` füllt es mit erfundenen Fotos, Personen und zwei Konten) plus Immich Showcase aus dem Arbeitsverzeichnis (`dev/docker-compose.dev.yml`). `DEV_EXEC="ssh root@dev-rechner" dev/push.sh` überträgt den Stand und baut neu. Echte Fotos gehören nicht auf die Entwicklungsinstanz.
