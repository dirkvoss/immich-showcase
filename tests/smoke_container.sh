#!/usr/bin/env bash
# Rauchtest des fertigen Images (braucht Docker): startet es nur mit den Pflichtangaben und prueft Start, erste PIN, Login, Neustart.
#   tests/smoke_container.sh [image]      (Vorgabe: showcase:smoke, wird aus dem Verzeichnis gebaut)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
IMG="${1:-showcase:smoke}"
[[ $# -ge 1 ]] || docker build -q -t "$IMG" . >/dev/null
N="showcase-smoke-$$"; V="$N-data"; PORT="${SMOKE_PORT:-18090}"
trap 'docker rm -f "$N" >/dev/null 2>&1; docker volume rm "$V" >/dev/null 2>&1' EXIT
ok() { echo "OK   $*"; }; fail() { echo "FEHL $*"; docker logs "$N" 2>&1 | tail -20 || true; exit 1; }
start() { docker run -d --name "$N" -p "$PORT:8090" -v "$V:/data" --read-only --tmpfs /tmp --cap-drop ALL \
  -e RAHMEN_IMMICH_URL=http://127.0.0.1:1/api -e RAHMEN_IMMICH_KEY=test "$@" "$IMG" >/dev/null; }
warte() { for _ in $(seq 1 40); do curl -fsS "http://127.0.0.1:$PORT/api/config" >/dev/null 2>&1 && return 0; sleep 1; done; return 1; }

# 1. Ohne Pflichtangaben: Einrichtungsmodus mit Code im Protokoll, App-Daten gesperrt (503), Assistent erreichbar
start2() { docker run -d --name "$N" -p "$PORT:8090" -v "$V:/data" --read-only --tmpfs /tmp --cap-drop ALL "$@" "$IMG" >/dev/null; }
start2
warte || fail "Dienst startet im Einrichtungsmodus nicht"
curl -fsS "http://127.0.0.1:$PORT/api/config" | grep -q '"konfiguriert":false' && ok "Einrichtungsmodus ohne Pflichtangaben" || fail "kein Einrichtungsmodus"
docker logs "$N" 2>&1 | grep -q "Einrichtungs-Code" && ok "Einrichtungs-Code im Protokoll" || fail "kein Einrichtungs-Code im Protokoll"
code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/neueste")"; [[ "$code" == 503 ]] && ok "App-Daten im Einrichtungsmodus gesperrt (503)" || fail "erwartet 503, war $code"
code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/setup/")"; [[ "$code" == 200 ]] && ok "Einrichtungsseite erreichbar" || fail "Einrichtungsseite $code"
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'X-Rahmen: 1' -H 'Content-Type: application/json' -d '{"code":"000000","url":"http://x:1"}' "http://127.0.0.1:$PORT/api/setup/pruefen")"; [[ "$code" == 403 ]] && ok "falscher Einrichtungs-Code abgelehnt" || fail "falscher Code: $code"
docker rm -f "$N" >/dev/null; docker volume rm "$V" >/dev/null

# 2. Erster Start: PIN wird erzeugt und einmalig protokolliert
start
warte || fail "Dienst startet nicht"
ok "Dienst laeuft nur mit URL und Schluessel"
PIN="$(docker logs "$N" 2>&1 | sed -n 's/.*Erste PIN[^:]*: \([0-9]\{6\}\).*/\1/p' | head -1)"
[[ -n "$PIN" ]] && ok "erste PIN im Protokoll" || fail "keine PIN im Protokoll"
curl -fsS "http://127.0.0.1:$PORT/api/config" | grep -q '"auth":"pin"' && ok "Vorgabe: PIN-Anmeldung"
code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/neueste")"; [[ "$code" == 401 ]] && ok "ohne Anmeldung gesperrt (401)" || fail "App ist ohne Anmeldung offen ($code)"
curl -fsS -X POST -H 'X-Rahmen: 1' -H 'Content-Type: application/json' -d "{\"pin\":\"$PIN\"}" "http://127.0.0.1:$PORT/api/login" | grep -q '"ok":true' && ok "Login mit der erzeugten PIN" || fail "Login scheitert"

# 2b. Pruefungen nach dem Deploy laufen im Container gegen die laufende Instanz (ohne Immich)
docker exec "$N" python /app/postdeploy.py --ohne-immich >/tmp/postdeploy-$$.txt 2>&1 && ok "postdeploy.py besteht im Container" || { cat /tmp/postdeploy-$$.txt; fail "postdeploy.py scheitert"; }
rm -f /tmp/postdeploy-$$.txt

# 3. Neustart: PIN bleibt, wird nicht neu erzeugt
docker restart "$N" >/dev/null; warte || fail "Dienst startet nach Neustart nicht"
[[ "$(docker logs "$N" 2>&1 | grep -c 'Erste PIN')" == 1 ]] && ok "PIN bleibt nach Neustart (Volume)" || fail "PIN wurde neu erzeugt"
curl -fsS -X POST -H 'X-Rahmen: 1' -H 'Content-Type: application/json' -d "{\"pin\":\"$PIN\"}" "http://127.0.0.1:$PORT/api/login" | grep -q '"ok":true' && ok "alte PIN gilt weiter" || fail "alte PIN gilt nicht mehr"

# 4. Vorgegebene PIN
docker rm -f "$N" >/dev/null; docker volume rm "$V" >/dev/null; start -e SHOWCASE_PIN=135790
warte || fail "Dienst startet mit SHOWCASE_PIN nicht"
curl -fsS -X POST -H 'X-Rahmen: 1' -H 'Content-Type: application/json' -d '{"pin":"135790"}' "http://127.0.0.1:$PORT/api/login" | grep -q '"ok":true' && ok "SHOWCASE_PIN wird uebernommen" || fail "SHOWCASE_PIN gilt nicht"
echo "Rauchtest bestanden."
