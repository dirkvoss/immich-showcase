#!/bin/sh
# Start von Immich Showcase im Container: prueft die Pflichtangaben, richtet beim ersten Start die PIN ein und startet den Dienst.
set -eu

fehler() { echo "FEHLER: $*" >&2; exit 1; }

# Pflichtangaben: entweder in .env (RAHMEN_IMMICH_URL + RAHMEN_IMMICH_KEY) oder spaeter per Einrichtungsassistent unter /setup/ (Code im Protokoll).
if [ -z "${RAHMEN_IMMICH_URL:-}" ] || [ -z "${RAHMEN_IMMICH_KEY:-}" ]; then
  if [ ! -s "${RAHMEN_WEB_EINSTELLUNGEN:-/data/einstellungen.json}" ]; then
    echo "Hinweis: RAHMEN_IMMICH_URL/RAHMEN_IMMICH_KEY nicht gesetzt - Immich Showcase startet im Einrichtungsmodus (http://<server>:8090/setup/)." >&2
    NICHT_EINGERICHTET=1
  fi
fi

mkdir -p /data "${RAHMEN_STATE_DIR:-/data/state}" 2>/dev/null || true

# PIN: nur noetig, wenn die Anmeldung per PIN erlaubt ist (Vorgabe). Beim ersten Start aus SHOWCASE_PIN, sonst zufaellig und einmalig im Protokoll.
if [ "${NICHT_EINGERICHTET:-0}" != "1" ] && [ "${RAHMEN_WEB_AUTH:-pin}" != "immich" ] && [ ! -s "${RAHMEN_WEB_PIN_FILE:-/data/pin}" ]; then
  PIN="${SHOWCASE_PIN:-}"
  if [ -z "$PIN" ]; then
    PIN="$(python -c 'import secrets; print("%06d" % secrets.randbelow(10**6))')"
    ERZEUGT=1
  fi
  case "$PIN" in [0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) fehler "SHOWCASE_PIN muss genau 6 Ziffern haben." ;; esac
  python /app/rahmen_web.py --set-pin "$PIN" >/dev/null
  if [ "${ERZEUGT:-0}" = "1" ]; then
    echo "=================================================================="
    echo " Erste PIN (bitte merken, sie wird nur jetzt angezeigt): $PIN"
    echo " Aendern: docker compose exec showcase python /app/rahmen_web.py --set-pin 123456"
    echo "=================================================================="
  else
    echo "PIN aus SHOWCASE_PIN eingerichtet."
  fi
fi

exec "$@"
