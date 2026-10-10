#!/usr/bin/env bash
# Frameside in einem Schritt starten.
#
#   Direkt aus dem Netz (laedt alles nach ~/immich-showcase):
#     curl -fsSL https://raw.githubusercontent.com/dirkvoss/frameside/main/install.sh | bash
#   Aus dem heruntergeladenen Ordner:
#     ./install.sh                 Immich laeuft schon (wird auf diesem Rechner automatisch erkannt): nur Frameside starten
#     ./install.sh --with-immich   noch kein Immich: Immich UND Frameside zusammen starten
#     ./install.sh --port 80       Frameside auf Port 80 statt 8090 (dann genuegt am Fernseher die reine IP-Adresse)
#     ./install.sh --bonjour       zusaetzlich per Bonjour im Netz anmelden (die iPhone-App findet den Server selbst; nur Docker unter Linux)
#     ./install.sh --no-open       den Browser nicht selbst oeffnen
#     ./install.sh --vorbereiten   nur .env und Netzwerk vorbereiten, nichts starten (zum Pruefen)
# Am Ende steht ein fertiger Einrichtungs-Link (mit QR-Code, falls `qrencode` installiert ist). Eine Datei bearbeiten muss man nicht.
set -euo pipefail

REPO="dirkvoss/frameside"
ZIEL="${SHOWCASE_DIR:-$HOME/immich-showcase}"
MIT_IMMICH=0; PORT=""; BONJOUR=0; OEFFNEN=1; NUR_VORBEREITEN=0; VERSION="${SHOWCASE_VERSION:-}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-immich) MIT_IMMICH=1 ;;
    --bonjour) BONJOUR=1 ;;
    --no-open) OEFFNEN=0 ;;
    --vorbereiten) NUR_VORBEREITEN=1 ;;
    --version) shift; VERSION="${1:-}" ;;
    --port) shift; PORT="${1:-}"; [[ "$PORT" =~ ^[0-9]{2,5}$ ]] || { echo "Bitte eine Portnummer angeben, z. B. --port 80"; exit 1; } ;;
    *) echo "Unbekannte Option: $1"; exit 1 ;;
  esac
  shift
done

command -v docker >/dev/null 2>&1 || { echo "Docker fehlt. Bitte zuerst installieren: https://docs.docker.com/get-docker/"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose (Version 2) fehlt: https://docs.docker.com/compose/install/"; exit 1; }
if ! docker ps >/dev/null 2>&1; then
  echo "Docker laesst sich mit diesem Benutzer nicht bedienen."
  echo "  Linux: den Benutzer in die Gruppe docker aufnehmen (sudo usermod -aG docker \$USER, danach neu anmelden) oder das Skript mit sudo starten."
  exit 1
fi

# --- Wo sind wir? Im heruntergeladenen Ordner, oder per "curl | bash" ohne Dateien? -------------------------------------------------
SKRIPT="${BASH_SOURCE[0]:-}"
if [[ -n "$SKRIPT" && -f "$(dirname "$SKRIPT")/docker-compose.yml" ]]; then
  cd "$(dirname "$SKRIPT")"
else
  command -v curl >/dev/null 2>&1 || { echo "curl fehlt."; exit 1; }
  if [[ ! -f "$ZIEL/docker-compose.yml" ]]; then
    echo "Lade Frameside nach $ZIEL ..."
    mkdir -p "$ZIEL"
    REF="heads/main"; [[ -n "$VERSION" && "$VERSION" != latest ]] && REF="tags/v${VERSION#v}"
    curl -fsSL "https://github.com/$REPO/archive/refs/$REF.tar.gz" | tar xz --strip-components=1 -C "$ZIEL"
  fi
  cd "$ZIEL"
fi
[[ $MIT_IMMICH == 1 ]] && cd examples/immich-stack
[[ -f .env ]] || cp .env.example .env

# --- kleine Helfer fuer die .env ---------------------------------------------------------------------------------------------------
env_wert() { grep -E "^$1=" .env | tail -1 | cut -d= -f2- || true; }
env_setzen() {            # env_setzen NAME WERT  (ersetzt einen vorhandenen Eintrag, sonst haengt es an)
  if grep -q "^$1=" .env; then sed -i.bak "s|^$1=.*|$1=$2|" .env && rm -f .env.bak; else echo "$1=$2" >> .env; fi
}
env_leer() { [[ -z "$(env_wert "$1")" ]]; }
compose_datei() {         # compose_datei DATEI  (in COMPOSE_FILE aufnehmen, falls noch nicht drin)
  local cf; cf="$(env_wert COMPOSE_FILE)"
  case ":$cf:" in *":$1:"*) return ;; esac
  env_setzen COMPOSE_FILE "${cf:-docker-compose.yml}:$1"
}

if [[ $MIT_IMMICH == 1 ]] && ! grep -Eq '^DB_PASSWORD=.+' .env; then          # Datenbank-Passwort selbst wuerfeln
  PW="$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 24 || true)"
  env_setzen DB_PASSWORD "$PW"
  echo "Datenbank-Passwort wurde erzeugt und in .env gespeichert."
fi
[[ -n "$VERSION" && "$VERSION" != latest ]] && env_setzen SHOWCASE_VERSION "${VERSION#v}"

# --- Immich auf diesem Rechner erkennen und Frameside in dessen Docker-Netz haengen --------------------------------------------
if [[ $MIT_IMMICH == 0 ]] && env_leer RAHMEN_IMMICH_URL; then
  IMMICH_NAME="$(docker ps --format '{{.Names}}	{{.Image}}' | awk -F'\t' 'tolower($2) ~ /immich-server/ || tolower($1) ~ /immich[-_]server/ {print $1; exit}' || true)"
  if [[ -n "$IMMICH_NAME" ]]; then
    NETZ="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}' "$IMMICH_NAME" 2>/dev/null | grep -v -E '^(host|none)$' | head -1 || true)"
    ML_NAME="$(docker ps --format '{{.Names}}' | grep -i -E 'immich[-_]machine[-_]learning' | head -1 || true)"
    if [[ -n "$NETZ" ]]; then
      env_setzen SHOWCASE_IMMICH_NETWORK "$NETZ"
      compose_datei docker-compose.immich-network.yml
      env_setzen RAHMEN_IMMICH_URL "http://$IMMICH_NAME:2283/api"
      if env_leer RAHMEN_ML_URL && [[ -n "$ML_NAME" ]]; then env_setzen RAHMEN_ML_URL "http://$ML_NAME:3003/predict"; fi
      echo "Immich erkannt: Container \"$IMMICH_NAME\" im Docker-Netz \"$NETZ\" – Frameside wird dort angebunden."
    fi
  else
    echo "Hinweis: Immich laeuft nicht auf diesem Rechner (oder nicht in Docker). Die Adresse gibst du gleich im Einrichtungsassistenten an."
  fi
fi
if [[ $BONJOUR == 1 ]]; then
  if [[ $MIT_IMMICH == 0 ]]; then compose_datei docker-compose.bonjour.yml; echo "Bonjour ist eingeschaltet (nur mit Docker unter Linux)."
  else echo "Hinweis: --bonjour gilt nur fuer die Einzelinstallation (ohne --with-immich); bitte docker-compose.bonjour.yml von Hand einbinden."; fi
fi

if [[ -n "$PORT" ]]; then env_setzen SHOWCASE_PORT "$PORT"; fi                  # gewaehlter Port gilt dauerhaft (.env)
PORT="$(env_wert SHOWCASE_PORT)"; PORT="${PORT:-8090}"
PORTTEIL=":$PORT"; [[ "$PORT" == "80" ]] && PORTTEIL=""
IP="$( (hostname -I 2>/dev/null | awk '{print $1}') || true)"
[[ -n "$IP" ]] || IP="$( (ipconfig getifaddr en0 2>/dev/null) || true)"
[[ -n "$IP" ]] || IP="$( (ipconfig getifaddr en1 2>/dev/null) || true)"
if [[ -n "$IP" ]] && env_leer RAHMEN_WEB_TV_URL; then                            # Adresse fuer Tablets/Fernseher gleich richtig vorbelegen (in der App unter Einstellungen aenderbar)
  env_setzen RAHMEN_WEB_TV_URL "http://$IP$PORTTEIL"
  echo "Adresse fuer Tablets und Fernseher: http://$IP$PORTTEIL (in der App unter Einstellungen aenderbar)."
fi

# Ist der Port schon belegt? (nur wenn nicht gerade unser eigener Container dort laeuft)
if ! docker ps --format '{{.Ports}}' | grep -q ":$PORT->" 2>/dev/null; then
  if ( command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ":$PORT " ) || ( command -v lsof >/dev/null 2>&1 && lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 ); then
    echo "Der Port $PORT ist schon belegt. Starte neu mit einem anderen Port, zum Beispiel:  ./install.sh --port 8091"; exit 1
  fi
fi
if [[ $NUR_VORBEREITEN == 1 ]]; then echo "Vorbereitet (nichts gestartet). Weiter mit:  docker compose up -d"; exit 0; fi

# --- Starten ----------------------------------------------------------------------------------------------------------------------
docker compose up -d
echo -n "Warte auf Frameside "
BEREIT=0
for _ in $(seq 1 60); do
  if curl -fsS -m 2 "http://127.0.0.1:$PORT/api/config" >/dev/null 2>&1; then BEREIT=1; break; fi
  echo -n "."; sleep 2
done
echo
[[ $BEREIT == 1 ]] || { echo "Frameside antwortet noch nicht. Schau nach mit:  docker compose logs showcase"; exit 1; }

IP="${IP:-<server>}"
KONFIGURIERT="$(curl -fsS -m 3 "http://127.0.0.1:$PORT/api/config" 2>/dev/null | grep -o '"konfiguriert": *true' || true)"
if [[ -n "$KONFIGURIERT" ]]; then
  echo; echo "Frameside ist schon eingerichtet und laeuft:  http://$IP$PORTTEIL"
  exit 0
fi
CODE="$(docker compose logs showcase 2>&1 | grep -o 'Einrichtungs-Code ein: [0-9]*' | tail -1 | grep -o '[0-9]*$' || true)"
LINK="http://$IP$PORTTEIL/setup/${CODE:+?code=$CODE}"
echo
echo "Fertig! Jetzt noch kurz im Browser einrichten (3 Schritte, etwa 1 Minute):"
echo
echo "      $LINK"
echo
if command -v qrencode >/dev/null 2>&1; then echo "  (oder den QR-Code mit dem Handy scannen)"; qrencode -t ANSIUTF8 "$LINK" || true; echo; fi
if [[ $MIT_IMMICH == 1 ]]; then echo "  Zuerst Immich einrichten:  http://$IP:2283   (erstes Konto = Administrator). Adresse von Immich im Assistenten: http://immich-server:2283"; fi
if [[ -z "$CODE" ]]; then echo "  Einrichtungs-Code:  docker compose logs showcase"; fi
echo "  Der Link ist nur zur Einrichtung gedacht; danach ist er ohne Wirkung."
echo "  Fernseher/Tablet: dort im Browser nur  $IP$PORTTEIL  eingeben und mit dem angezeigten Code koppeln (App -> Geraete)."
if [[ $OEFFNEN == 1 ]]; then                                                      # Browser oeffnen, wenn es einen Bildschirm gibt
  if command -v open >/dev/null 2>&1; then open "$LINK" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1 && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then xdg-open "$LINK" >/dev/null 2>&1 || true; fi
fi
