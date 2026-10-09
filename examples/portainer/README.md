# Immich Showcase mit Portainer

1. **Stacks → Add stack**, Name `immich-showcase`.
2. **Web editor**: den Inhalt von `docker-compose.yml` einfügen (Download: <https://github.com/dirkvoss/immich-showcase/raw/main/docker-compose.yml>).
3. Weiter unten bei **Environment variables** (alle freiwillig): `SHOWCASE_PORT` (Standard 8090), `TZ`, `RAHMEN_IMMICH_URL`. Der Assistent im Browser fragt alles Wichtige selbst.
4. **Deploy the stack**. Danach `http://<Server-IP>:8090` öffnen. Den **Einrichtungs-Code** zeigt **Containers → showcase → Logs**.
5. Immich im selben Docker-Netzwerk? Dann in der `docker-compose.yml` unter `services.showcase` `networks: [default, immich]` und unten `networks: immich: {external: true, name: <Netzwerk von Immich>}` ergänzen; die Adresse im Assistenten lautet dann `http://immich_server:2283`.
6. Updates: Stack → **Pull and redeploy**.
