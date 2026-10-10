# Frameside auf TrueNAS SCALE

1. **Apps → Discover Apps → Custom App** (oder **Install via YAML**, je nach Version).
2. Den Inhalt der Datei `docker-compose.yml` dieses Projekts einfügen (Download: <https://github.com/dirkvoss/frameside/raw/main/docker-compose.yml>).
3. Unter `volumes` statt des benannten Volumes einen Datensatz verwenden, z. B. `/mnt/pool/apps/immich-showcase:/data`, und dem Datensatz Rechte für die Benutzer-ID `10001` geben (oder in der YAML `user:` auf die ID des Datensatz-Besitzers setzen).
4. Installieren. Danach `http://<IP-des-NAS>:8090` öffnen; der Einrichtungsassistent beginnt. Den **Einrichtungs-Code** zeigt das Protokoll der App.
5. Adresse von Immich im Assistenten: `http://<IP-des-NAS>:<Immich-Port>` (bei der TrueNAS-App meist 30041).

Nicht auf einer echten TrueNAS-Installation getestet; Rückmeldungen willkommen (GitHub Issues).
