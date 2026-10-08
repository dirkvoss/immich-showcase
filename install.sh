#!/usr/bin/env bash
# Immich Showcase in einem Schritt starten.
#   ./install.sh                 Immich ist schon vorhanden: nur Immich Showcase starten
#   ./install.sh --with-immich   noch kein Immich: Immich UND Immich Showcase zusammen starten
#   ./install.sh --port 80       Immich Showcase auf Port 80 statt 8090 (dann genuegt am Fernseher die reine IP-Adresse)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
MIT_IMMICH=0; PORT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-immich) MIT_IMMICH=1 ;;
    --port) shift; PORT="${1:-}"; [[ "$PORT" =~ ^[0-9]{2,5}$ ]] || { echo "Bitte eine Portnummer angeben, z. B. --port 80"; exit 1; } ;;
    *) echo "Unbekannte Option: $1"; exit 1 ;;
  esac
  shift
done

command -v docker >/dev/null 2>&1 || { echo "Docker fehlt. Bitte zuerst installieren: https://docs.docker.com/get-docker/"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose (Version 2) fehlt: https://docs.docker.com/compose/install/"; exit 1; }
[[ $MIT_IMMICH == 1 ]] && cd examples/immich-stack
[[ -f .env ]] || cp .env.example .env
if [[ $MIT_IMMICH == 1 ]] && ! grep -Eq '^DB_PASSWORD=.+' .env; then          # Datenbank-Passwort selbst wuerfeln
  PW="$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 24 || true)"
  sed -i.bak "s/^DB_PASSWORD=.*/DB_PASSWORD=$PW/" .env && rm -f .env.bak
  echo "Datenbank-Passwort wurde erzeugt und in .env gespeichert."
fi

if [[ -n "$PORT" ]]; then                                                         # gewaehlter Port gilt dauerhaft (.env)
  if grep -q '^SHOWCASE_PORT=' .env; then sed -i.bak "s|^SHOWCASE_PORT=.*|SHOWCASE_PORT=$PORT|" .env && rm -f .env.bak; else echo "SHOWCASE_PORT=$PORT" >> .env; fi
fi
PORT="$(grep -E '^SHOWCASE_PORT=[0-9]+' .env | tail -1 | cut -d= -f2)"; PORT="${PORT:-8090}"
PORTTEIL=":$PORT"; [[ "$PORT" == "80" ]] && PORTTEIL=""
IP="$( (hostname -I 2>/dev/null | awk '{print $1}') || true)"
[[ -n "$IP" ]] || IP="$( (ipconfig getifaddr en0 2>/dev/null) || true)"
if [[ -n "$IP" ]] && ! grep -Eq '^RAHMEN_WEB_TV_URL=.+' .env; then               # Adresse fuer Tablets/Fernseher gleich richtig vorbelegen (in der App unter Einstellungen aenderbar)
  if grep -q '^RAHMEN_WEB_TV_URL=' .env; then sed -i.bak "s|^RAHMEN_WEB_TV_URL=.*|RAHMEN_WEB_TV_URL=http://$IP$PORTTEIL|" .env && rm -f .env.bak; else echo "RAHMEN_WEB_TV_URL=http://$IP$PORTTEIL" >> .env; fi
  echo "Adresse fuer Tablets und Fernseher: http://$IP$PORTTEIL (in der App unter Einstellungen aenderbar)."
fi

docker compose up -d
echo -n "Warte auf Immich Showcase "
for _ in $(seq 1 60); do
  curl -fsS -m 2 http://127.0.0.1:$PORT/api/config >/dev/null 2>&1 && break
  echo -n "."; sleep 2
done
echo

IP="${IP:-<server>}"
CODE="$(docker compose logs showcase 2>&1 | grep -o 'Einrichtungs-Code ein: [0-9]*' | tail -1 | grep -o '[0-9]*$' || true)"
echo
echo "Fertig. Weiter im Browser:"
[[ $MIT_IMMICH == 1 ]] && echo "  1. Immich einrichten:            http://$IP:2283   (erstes Konto = Administrator)"
echo "  $([[ $MIT_IMMICH == 1 ]] && echo 2 || echo 1). Immich Showcase einrichten:  http://$IP$PORTTEIL"
[[ -n "$CODE" ]] && echo "     Einrichtungs-Code:            $CODE" || echo "     Einrichtungs-Code:            docker compose logs showcase"
[[ $MIT_IMMICH == 1 ]] && echo "     Adresse von Immich im Assistenten: http://immich-server:2283"
echo "  Fernseher/Tablet: dort im Browser nur  $IP$PORTTEIL  eingeben (der Fernseher findet seine Seite selbst) und mit dem angezeigten Code koppeln (App -> Geraete)."
