#!/usr/bin/env bash
# Frameside auf dem Server aktualisieren: Version aus der Registry holen, vorher sichern, umschalten, pruefen, bei Fehler zurueck.
#
#   deploy.sh 1.2.3            auf Version 1.2.3 wechseln
#   deploy.sh --rollback       zur vorherigen Version zurueck
#   deploy.sh --status         laufende Version zeigen
#   deploy.sh 1.2.3 --dry-run  nur pruefen (Image ziehen, nichts umschalten)
#
# Erwartet im Verzeichnis SHOWCASE_DIR (Vorgabe: Verzeichnis dieses Skripts/..): docker-compose.yml mit
#   image: ghcr.io/<konto>/frameside:${SHOWCASE_VERSION}
# und eine Datei .env mit der Zeile SHOWCASE_VERSION=<version> (Compose liest sie selbst). Die Registry-Anmeldung
# (docker login ghcr.io) muss einmal auf dem Server erfolgt sein, wenn das Image privat ist.
set -euo pipefail

# Optionale Server-Einstellungen (SHOWCASE_* Variablen) in deploy.conf neben diesem Skript
[[ -f "$(dirname "${BASH_SOURCE[0]}")/deploy.conf" ]] && source "$(dirname "${BASH_SOURCE[0]}")/deploy.conf"

# Altname: fruehere Installationen (Projekt hiess "Guckloch") setzen GUCKLOCH_* - diese Werte gelten weiter, solange SHOWCASE_* fehlt
for _v in $(compgen -A variable | grep '^GUCKLOCH_' || true); do _n="SHOWCASE_${_v#GUCKLOCH_}"; [[ -n "${!_n:-}" ]] || printf -v "$_n" '%s' "${!_v}"; done

DIR="${SHOWCASE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
IMAGE="${SHOWCASE_IMAGE:-ghcr.io/dirkvoss/frameside}"
HEALTH="${SHOWCASE_HEALTH_URL:-http://127.0.0.1:8090}"
DATA="${SHOWCASE_DATA_DIR:-$DIR/data}"
BACKUPS="${SHOWCASE_BACKUP_DIR:-$DIR/backups}"
KEEP="${SHOWCASE_KEEP_BACKUPS:-10}"
EXCLUDE="${SHOWCASE_BACKUP_EXCLUDE:-data/videos data/tv}"      # Pfade relativ zu SHOWCASE_DIR, die NICHT gesichert werden (Zwischenspeicher)
EXTRA="${SHOWCASE_EXTRA_BACKUP:-}"      # weitere Verzeichnisse (absolut, leerzeichengetrennt), z. B. "/var/lib/bilderrahmen"
WARTEN="${SHOWCASE_WAIT_SECONDS:-90}"
SERVICE="${SHOWCASE_SERVICE:-showcase}"                   # Name des Dienstes in der Compose-Datei
POSTDEPLOY="${SHOWCASE_POSTDEPLOY:-1}"                   # 0 = Pruefungen nach dem Deploy ueberspringen (nicht empfohlen)
LOG="$DIR/deploy.log"
ENVFILE="$DIR/.env"
PREV="$DIR/.previous-version"

log() { printf '%s %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG" >&2; }
fail() { log "FEHLER: $*"; exit 1; }
aktuell() { grep -E '^(SHOWCASE|GUCKLOCH)_VERSION=' "$ENVFILE" 2>/dev/null | tail -1 | cut -d= -f2- || true; }
setze() {
  touch "$ENVFILE"; local alt=0; grep -q '^GUCKLOCH_VERSION=' "$ENVFILE" && alt=1     # Altinstallation: Compose-Datei liest evtl. noch GUCKLOCH_VERSION
  grep -Ev '^(SHOWCASE|GUCKLOCH)_VERSION=' "$ENVFILE" > "$ENVFILE.tmp" || true
  echo "SHOWCASE_VERSION=$1" >> "$ENVFILE.tmp"; if [[ $alt == 1 ]]; then echo "GUCKLOCH_VERSION=$1" >> "$ENVFILE.tmp"; fi
  mv "$ENVFILE.tmp" "$ENVFILE"
}
compose() { (cd "$DIR" && docker compose "$@"); }

laeuft_version() { curl -fsS -m 5 "$HEALTH/api/config" 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get("version",""))' 2>/dev/null || true; }

gesund() {   # $1 = erwartete Version
  local ende=$((SECONDS + WARTEN)) v
  while (( SECONDS < ende )); do
    v="$(laeuft_version)"
    if [[ "$v" == "$1" ]] && curl -fsS -m 5 "$HEALTH/api/me" >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  return 1
}

sichern() {  # $1 = Version, die gerade laeuft
  umask 077                      # die Sicherung enthaelt Zugangsdaten (env-Dateien, PIN-Hash)
  mkdir -p "$BACKUPS"
  local ziel="$BACKUPS/showcase-$(date +%Y%m%d-%H%M%S)-v${1:-unbekannt}.tgz"
    local zusatz=() ausschluss=(--exclude=backups --exclude=deploy.log) p
  for p in $EXTRA; do [[ -e "$p" ]] && zusatz+=(-C / "${p#/}"); done
  for p in $EXCLUDE; do ausschluss+=("--exclude=$p"); done
  tar czf "$ziel" "${ausschluss[@]}" -C "$DIR" . ${zusatz[@]+"${zusatz[@]}"} 2>/dev/null || fail "Sicherung fehlgeschlagen"
  log "Sicherung: $ziel ($(du -h "$ziel" | cut -f1))"
  ls -1t "$BACKUPS"/showcase-*.tgz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
}

pruefungen() {  # $1 = Version: Pruefungen der laufenden Instanz (/app/postdeploy.py im Container), nur lesend
  [[ "$POSTDEPLOY" == "0" ]] && { log "Pruefungen nach dem Deploy uebersprungen (SHOWCASE_POSTDEPLOY=0)"; return 0; }
  log "Pruefungen nach dem Deploy ..."
  local aus
  if aus="$(compose exec -T "$SERVICE" python /app/postdeploy.py --version "$1" 2>&1)"; then
    printf '%s\n' "$aus" | tee -a "$LOG" >&2
    return 0
  fi
  printf '%s\n' "$aus" | tee -a "$LOG" >&2
  return 1
}

umschalten() {  # $1 = Version
  setze "$1"
  compose up -d --remove-orphans >>"$LOG" 2>&1 || return 1
  gesund "$1" || return 1
  pruefungen "$1"
}

case "${1:-}" in
  --status) echo "konfiguriert: $(aktuell) | laeuft: $(laeuft_version)"; exit 0 ;;
  --rollback)
    [[ -f "$PREV" ]] || fail "keine vorherige Version bekannt"
    ZIEL="$(cat "$PREV")"; ALT="$(aktuell)"
    log "Rollback: $ALT -> $ZIEL"
    sichern "$ALT"
    docker image inspect "$IMAGE:$ZIEL" >/dev/null 2>&1 || docker pull -q "$IMAGE:$ZIEL" >/dev/null || fail "Image $ZIEL nicht verfuegbar"
    if umschalten "$ZIEL"; then echo "$ALT" > "$PREV"; log "Rollback ok, laeuft: $ZIEL"; else fail "Rollback auf $ZIEL gescheitert - bitte von Hand pruefen (docker compose logs)"; fi
    exit 0 ;;
  ""|-h|--help) sed -n '2,12p' "$0"; exit 0 ;;
esac

NEU="${1#v}"; DRY=0; [[ "${2:-}" == "--dry-run" ]] && DRY=1
[[ "$NEU" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.]+)?$ ]] || fail "ungueltige Version '$NEU' (erwartet z. B. 1.2.3)"
[[ -f "$DIR/docker-compose.yml" ]] || fail "docker-compose.yml fehlt in $DIR"
command -v docker >/dev/null || fail "docker fehlt"

ALT="$(aktuell)"
log "=== Deploy $IMAGE:$NEU (bisher: ${ALT:-keine}) ==="
[[ "$NEU" == "$ALT" && "$(laeuft_version)" == "$NEU" ]] && { log "laeuft bereits"; exit 0; }

log "Image holen ..."
docker pull -q "$IMAGE:$NEU" >/dev/null || fail "Image $IMAGE:$NEU nicht abrufbar (Version vorhanden? docker login ghcr.io erfolgt?)"
(( DRY )) && { log "Trockenlauf ok - nichts geaendert"; exit 0; }

sichern "$ALT"
echo "$ALT" > "$PREV"
log "Umschalten ..."
if umschalten "$NEU"; then
  log "OK: Frameside $NEU laeuft, antwortet und hat die Pruefungen bestanden"
  # Alte Images aufraeumen, die vorherige Version bleibt fuer den Rueckweg
  docker images --format '{{.Repository}}:{{.Tag}}' "$IMAGE" | grep -v -e ":$NEU\$" -e ":${ALT:-__}\$" | xargs -r docker rmi >/dev/null 2>&1 || true
  exit 0
fi

log "Neue Version antwortet nicht oder besteht die Pruefungen nicht - Rueckweg auf ${ALT:-?}"
compose logs --tail 40 >>"$LOG" 2>&1 || true
if [[ -n "$ALT" ]] && umschalten "$ALT"; then
  fail "Version $NEU abgelehnt, $ALT laeuft wieder (Details in $LOG)"
fi
fail "Version $NEU UND Rueckweg gescheitert - Sicherung in $BACKUPS, bitte von Hand pruefen"
