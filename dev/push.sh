#!/usr/bin/env bash
# Arbeitsverzeichnis auf die Entwicklungsinstanz uebertragen und dort neu bauen/starten.
#   DEV_EXEC  ssh-artiger Befehl, der eine Befehlszeile auf dem Entwicklungsrechner ausfuehrt (liest stdin), z. B.
#             "ssh root@showcase-dev"  oder  "ssh root@prox1 pct exec 120 --"
#   DEV_DIR   Zielverzeichnis dort (Vorgabe /opt/showcase-dev)
# Die Dateien dev/container.env und data/ auf dem Entwicklungsrechner werden NICHT ueberschrieben.
set -euo pipefail
: "${DEV_EXEC:?DEV_EXEC setzen, z. B. DEV_EXEC='ssh root@showcase-dev'}"
DEV_DIR="${DEV_DIR:-/opt/showcase-dev}"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
COPYFILE_DISABLE=1 tar czf - --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache --exclude=dev/container.env --exclude=dev/data --exclude=dev/state . \
  | $DEV_EXEC "$(printf '%q ' bash -c "mkdir -p $DEV_DIR && tar xzf - -C $DEV_DIR 2>/dev/null")"
$DEV_EXEC "$(printf '%q ' bash -c "cd $DEV_DIR/dev && docker compose -f docker-compose.dev.yml up -d --build 2>&1 | tail -3")"
echo "Entwicklungsinstanz aktualisiert."
