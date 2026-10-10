# Frameside auf Unraid

1. Datei `frameside.xml` nach `/boot/config/plugins/dockerMan/templates-user/` auf dem Unraid-Stick kopieren (oder im Docker-Tab „Container hinzufügen“ → Vorlage wählen, sobald sie dort liegt).
2. Im Docker-Tab: **Container hinzufügen** → Vorlage **frameside** → **Anwenden**.
3. Auf das Symbol klicken → **WebUI**: der Einrichtungsassistent öffnet sich. Den **Einrichtungs-Code** zeigt das Protokoll des Containers (Symbol → *Log*), oder einfach dem angezeigten Link folgen.
4. Immich-Adresse im Assistenten: `http://<IP-von-Unraid>:2283`, dann E-Mail und Passwort deines Immich-Kontos.

Hinweise
- Der Ordner `/mnt/user/appdata/immich-showcase` muss dem Benutzer `nobody` (99:100) gehören; Unraid legt ihn meist richtig an.
- Automatische Updates: das Plugin *CA Auto Update Applications* oder Watchtower (siehe `examples/watchtower`).
- Diese Vorlage ist nicht auf einer echten Unraid-Installation getestet; Rückmeldungen willkommen (GitHub Issues).
