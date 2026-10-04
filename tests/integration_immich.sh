#!/usr/bin/env bash
# Integrationstest gegen ein ECHTES Immich einer bestimmten Version: startet Immich (ohne ML), fuellt es mit erfundenen Fotos/Personen/Konten,
# baut Immich Showcase, laesst es sich per API-Schluessel verbinden und fuehrt postdeploy.py + Zusatzpruefungen aus.
#   tests/integration_immich.sh [immich-version] [showcase-image]      z. B. v3.2.4
# Braucht Docker, Python 3 mit Pillow, exiftool, ffmpeg, curl. Laeuft in GitHub Actions fuer mehrere Immich-Versionen.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
IMV="${1:-v3.2.4}"; IMG="${2:-showcase:int}"
P="glint$$"; W="$(mktemp -d)"; PORT="${IMMICH_PORT:-12283}"; GPORT="${SHOWCASE_PORT:-18093}"
export IMMICH_VERSION="$IMV" IMMICH_PORT="$PORT" IMMICH_PREFIX="$P" UPLOAD_LOCATION="$W/upload" DB_DATA_LOCATION="$W/postgres" DB_PASSWORD="ci-$$"
mkdir -p "$W/upload" "$W/postgres"
nett() { docker rm -f "${P}_showcase" >/dev/null 2>&1 || true; docker compose -p "$P" -f dev/docker-compose.immich.yml down -v >/dev/null 2>&1 || true; sudo rm -rf "$W" 2>/dev/null || rm -rf "$W"; }
trap nett EXIT
ok() { echo "OK   $*"; }
fail() {
  echo "FEHL $*"
  echo "--- Container"; docker ps -a --filter "name=$P" --format '{{.Names}}: {{.Status}}' || true
  for c in $(docker ps -aq --filter "name=$P"); do docker inspect -f '{{.Name}} OOMKilled={{.State.OOMKilled}} ExitCode={{.State.ExitCode}}' "$c" || true; done
  echo "--- Immich Showcase"; docker logs "${P}_showcase" 2>&1 | grep -v 'GET /api/me' | tail -25 || true
  echo "--- Immich"; docker compose -p "$P" -f dev/docker-compose.immich.yml logs --tail 15 immich-server 2>&1 || true
  exit 1
}

echo "== Immich $IMV starten"
docker compose -p "$P" -f dev/docker-compose.immich.yml up -d >/dev/null
for _ in $(seq 1 90); do curl -fs "http://127.0.0.1:$PORT/api/server/version" >/dev/null 2>&1 && break; sleep 2; done
curl -fs "http://127.0.0.1:$PORT/api/server/version" | grep -q major && ok "Immich antwortet: $(curl -s http://127.0.0.1:$PORT/api/server/version)" || fail "Immich startet nicht"

echo "== Testdaten einspielen"
python3 dev/seed_immich.py --url "http://127.0.0.1:$PORT" --fotos 30 --sparsam --ausgabe "$W/zugang.json" | tail -1
KEY="$(python3 -c "import json;print(json.load(open('$W/zugang.json'))['api_key'])")"

echo "== Immich Showcase starten"
[[ $# -ge 2 ]] || docker build -q -t "$IMG" . >/dev/null
docker run -d --name "${P}_showcase" --network "${P}_default" -p "127.0.0.1:$GPORT:8090" --read-only --tmpfs /tmp --cap-drop ALL \
  -e RAHMEN_IMMICH_URL="http://immich-server:2283/api" -e RAHMEN_IMMICH_KEY="$KEY" -e SHOWCASE_PIN=123456 \
  -e RAHMEN_WEB_RAHMEN_ZIELE=rahmen=Rahmen -e RAHMEN_WEB_AUTH=beide "$IMG" >/dev/null
for _ in $(seq 1 40); do curl -fsS "http://127.0.0.1:$GPORT/api/config" >/dev/null 2>&1 && break; sleep 1; done
curl -fsS "http://127.0.0.1:$GPORT/api/config" | grep -q '"konfiguriert":true' && ok "Immich Showcase laeuft gegen Immich $IMV" || fail "Immich Showcase startet nicht"

echo "== Pruefungen (Immich verarbeitet die Fotos noch: bis zu 6 Minuten warten)"
ende=$((SECONDS + 360)); ERG=1
while (( SECONDS < ende )); do
  docker exec "${P}_showcase" python /app/postdeploy.py > "$W/pd.txt" 2>&1 && { ERG=0; break; } || true
  sleep 10
done
cat "$W/pd.txt"
[[ $ERG == 0 ]] && ok "postdeploy.py besteht" || fail "postdeploy.py scheitert"

echo "== Zusatzpruefungen: Filter nach Land/Person, Anmeldung mit Immich-Konto"
docker exec -i "${P}_showcase" python - <<PY || fail "Zusatzpruefung"
import json, time, urllib.request
tok = open('/tmp/showcase-selbsttest').read().strip()
def hole(p):
    return json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8090'+p, headers={'X-Selbsttest': tok}), timeout=60))
ende = time.time() + 60
while True:                                    # Immich ordnet Orte (Reverse-Geocoding) erst nach der Metadaten-Verarbeitung zu
    f = hole('/api/facetten?typ=foto')
    if len(f['laender']) >= 3 or time.time() > ende:
        break
    time.sleep(15)
assert f['gesamt'] == 30, f"Fotos sichtbar: {f['gesamt']} (erwartet 30)"
assert len(f['personen']) == 3, f"Personen: {[p['name'] for p in f['personen']]}"
assert len(f['jahre']) >= 3, f"Jahre: {f['jahre']}"
if len(f['laender']) < 3: print('WARNUNG: Laender leer - Immich-Geocoding in CI nicht fertig (nicht blockierend)')
print('Facetten ok:', f['gesamt'], 'Fotos,', len(f['laender']), 'Laender,', len(f['personen']), 'Personen')
PY
ok "Filter und Zaehler stimmen"
ADMIN="$(python3 -c "import json;z=json.load(open('$W/zugang.json'));print(z['admin']['email'])")"; APW="$(python3 -c "import json;z=json.load(open('$W/zugang.json'));print(z['admin']['password'])")"
curl -fsS -c "$W/cj" -X POST -H 'X-Rahmen: 1' -H 'Content-Type: application/json' -d "{\"pin\":\"123456\"}" "http://127.0.0.1:$GPORT/api/login" | grep -q '"ok":true' && ok "Anmeldung per PIN" || fail "PIN-Login"
curl -fsS -c "$W/cj2" -X POST -H 'X-Rahmen: 1' -H 'Content-Type: application/json' -d "{\"email\":\"$ADMIN\",\"passwort\":\"$APW\"}" "http://127.0.0.1:$GPORT/api/login" | grep -q '"ok":true' && ok "Anmeldung mit dem Immich-Konto (eigener Schluessel wird angelegt)" || fail "Immich-Login"
curl -fsS -b "$W/cj2" "http://127.0.0.1:$GPORT/api/facetten?typ=foto" | grep -q '"gesamt":30' && ok "Konto sieht seine 30 Fotos" || fail "Konto sieht nicht seine Fotos"
echo "Integrationstest gegen Immich $IMV bestanden."
