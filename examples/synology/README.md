# Immich Showcase auf einer Synology (Container Manager)

Voraussetzung: **Container Manager** (DSM 7.2 oder neuer; früher „Docker“) ist installiert. Immich läuft schon (oder du installierst es zuerst).

1. In **File Station** einen Ordner anlegen, z. B. `docker/immich-showcase`.
2. Die Datei `docker-compose.yml` aus diesem Projekt hineinlegen (Download: <https://github.com/dirkvoss/immich-showcase/raw/main/docker-compose.yml>). Eine `.env` ist nicht nötig.
3. **Container Manager → Projekt → Erstellen**
   - Projektname: `immich-showcase`
   - Pfad: der Ordner von eben
   - Quelle: **Vorhandene docker-compose.yml verwenden**
4. Auf *Weiter* klicken, nichts ändern, **Fertig**. Das Projekt startet.
5. Im Browser `http://<IP-der-Synology>:8090` öffnen, der Einrichtungsassistent beginnt. Den **Einrichtungs-Code** zeigt **Container Manager → Container → showcase → Protokoll**.
6. Adresse von Immich im Assistenten: `http://<IP-der-Synology>:2283` (oder die Adresse, unter der du Immich öffnest).

Hinweise
- Der Benutzer `10001` im Container muss in `/data` schreiben dürfen; das Docker-Volume aus der `docker-compose.yml` ist dafür schon richtig eingerichtet.
- Tablets und Fernseher öffnen `http://<IP-der-Synology>:8090`.
- Zugriff von außen nur mit VPN oder über den DSM-Reverse-Proxy (Systemsteuerung → Anmeldeportal → Erweitert); die Rahmen-Seiten brauchen dann HTTPS.
- Updates: Projekt auswählen → **Erstellen/Neu erstellen** mit „Neuestes Image laden“, oder Watchtower (`examples/watchtower`).
- Nicht auf allen DSM-Versionen getestet; bitte Rückmeldungen als GitHub-Issue.
