#!/usr/bin/env bash
# Immich Showcase in einem Schritt starten.
#   ./install.sh                 Immich ist schon vorhanden: nur Immich Showcase starten
#   ./install.sh --with-immich   noch kein Immich: Immich UND Immich Showcase zusammen starten
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
MIT_IMMICH=0; [[ "${1:-}" == "--with-immich" ]] && MIT_IMMICH=1

command -v docker >/dev/null 2>&1 || { echo "Docker fehlt. Bitte zuerst installieren: https://docs.docker.com/get-docker/"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose (Version 2) fehlt: https://docs.docker.com/compose/install/"; exit 1; }
[[ $MIT_IMMICH == 1 ]] && cd examples/immich-stack
[[ -f .env ]] || cp .env.example .env
if [[ $MIT_IMMICH == 1 ]] && ! grep -Eq '^DB_PASSWORD=.+' .env; then          # Datenbank-Passwort selbst wuerfeln
  PW="$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 24 || true)"
  sed -i.bak "s/^DB_PASSWORD=.*/DB_PASSWORD=$PW/" .env && rm -f .env.bak
  echo "Datenbank-Passwort wurde erzeugt und in .env gespeichert."
fi

docker compose up -d
echo -n "Warte auf Immich Showcase "
for _ in $(seq 1 60); do
  curl -fsS -m 2 http://127.0.0.1:8090/api/config >/dev/null 2>&1 && break
  echo -n "."; sleep 2
done
echo

IP="$( (hostname -I 2>/dev/null | awk '{print $1}') || true)"
[[ -n "$IP" ]] || IP="$( (ipconfig getifaddr en0 2>/dev/null) || true)"; IP="${IP:-<server>}"
CODE="$(docker compose logs showcase 2>&1 | grep -o 'Einrichtungs-Code eingeben: [0-9]*' | tail -1 | grep -o '[0-9]*$' || true)"
echo
echo "Fertig. Weiter im Browser:"
[[ $MIT_IMMICH == 1 ]] && echo "  1. Immich einrichten:            http://$IP:2283   (erstes Konto = Administrator)"
echo "  $([[ $MIT_IMMICH == 1 ]] && echo 2 || echo 1). Immich Showcase einrichten:  http://$IP:8090"
[[ -n "$CODE" ]] && echo "     Einrichtungs-Code:            $CODE" || echo "     Einrichtungs-Code:            docker compose logs showcase"
[[ $MIT_IMMICH == 1 ]] && echo "     Adresse von Immich im Assistenten: http://immich-server:2283"
echo "  Fernseher/Tablet: dort die Seite http://$IP:8090/tv/ oeffnen und mit dem angezeigten Code koppeln (App -> Geraete)."
