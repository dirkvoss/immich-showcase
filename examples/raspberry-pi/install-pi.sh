#!/usr/bin/env bash
# Einen Raspberry Pi (oder jeden Debian-Rechner) mit EINEM Befehl zum Frameside-Server machen:
# installiert Docker (falls noetig) und Frameside, meldet den Server im Netz an (Bonjour: die iPhone-App findet ihn selbst)
# und zeigt am Ende den Link zur Einrichtung. Vorher auf der SD-Karte "Raspberry Pi OS Lite (64-Bit)" mit dem Raspberry Pi Imager aufspielen
# (dort Name, WLAN und SSH einstellen).
#
#   curl -fsSL https://raw.githubusercontent.com/dirkvoss/frameside/main/examples/raspberry-pi/install-pi.sh | bash
#
# Optionen (bei curl | bash nach "bash -s --" angeben):
#   --hostname NAME    Rechnername setzen, dann ist der Pi auch unter NAME.local erreichbar (z. B. showcase)
#   --port N           Frameside auf Port N statt 8090 (80 = nur die IP-Adresse am Fernseher genuegt)
#   --ohne-bonjour     nicht im Netz anmelden
#   --version X.Y.Z    eine bestimmte Version statt der neuesten
# Hinweis: Das Skript ist auf einem Debian-12-System getestet, auf echter Raspberry-Pi-Hardware (arm64) noch nicht. Rueckmeldungen sind willkommen.
set -euo pipefail

HOSTNAME_NEU=""; PORT=""; BONJOUR=1; VERSION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --hostname) shift; HOSTNAME_NEU="${1:-}"; [[ "$HOSTNAME_NEU" =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,30}$ ]] || { echo "Bitte einen einfachen Namen angeben, z. B. --hostname showcase"; exit 1; } ;;
    --port) shift; PORT="${1:-}"; [[ "$PORT" =~ ^[0-9]{2,5}$ ]] || { echo "Bitte eine Portnummer angeben, z. B. --port 80"; exit 1; } ;;
    --ohne-bonjour) BONJOUR=0 ;;
    --version) shift; VERSION="${1:-}" ;;
    *) echo "Unbekannte Option: $1"; exit 1 ;;
  esac
  shift
done

[[ "$(uname -s)" == "Linux" ]] || { echo "Dieses Skript ist fuer Linux (Raspberry Pi OS / Debian)."; exit 1; }
command -v apt-get >/dev/null 2>&1 || { echo "apt-get fehlt. Bitte Raspberry Pi OS (Debian) verwenden."; exit 1; }
case "$(uname -m)" in
  aarch64|arm64|x86_64|amd64) ;;
  *) echo "Dieser Rechner ($(uname -m)) wird nicht unterstuetzt. Bitte die 64-Bit-Version von Raspberry Pi OS aufspielen (Raspberry Pi Imager: \"Raspberry Pi OS Lite (64-bit)\")."; exit 1 ;;
esac

if [[ $EUID -eq 0 ]]; then SUDO=""; BENUTZER="${SUDO_USER:-root}"; else SUDO="sudo"; BENUTZER="$USER"; command -v sudo >/dev/null 2>&1 || { echo "sudo fehlt - bitte als root starten."; exit 1; }; fi
HEIM="$(getent passwd "$BENUTZER" | cut -d: -f6)"; HEIM="${HEIM:-$HOME}"

echo "== 1/4  Grundpakete"
$SUDO apt-get update -qq
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq curl ca-certificates qrencode avahi-daemon >/dev/null

if [[ -n "$HOSTNAME_NEU" ]]; then
  echo "== Rechnername: $HOSTNAME_NEU"
  $SUDO hostnamectl set-hostname "$HOSTNAME_NEU" 2>/dev/null || echo "$HOSTNAME_NEU" | $SUDO tee /etc/hostname >/dev/null
  $SUDO sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$HOSTNAME_NEU/" /etc/hosts 2>/dev/null || true
  $SUDO systemctl restart avahi-daemon 2>/dev/null || true
fi

echo "== 2/4  Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | $SUDO sh >/dev/null 2>&1 || { echo "Docker konnte nicht installiert werden. Anleitung: https://docs.docker.com/engine/install/debian/"; exit 1; }
fi
$SUDO systemctl enable --now docker >/dev/null 2>&1 || true
if [[ "$BENUTZER" != "root" ]]; then $SUDO usermod -aG docker "$BENUTZER"; fi

echo "== 3/4  Frameside"
OPT=(--no-open)
[[ $BONJOUR == 1 ]] && OPT+=(--bonjour)
[[ -n "$PORT" ]] && OPT+=(--port "$PORT")
[[ -n "$VERSION" ]] && OPT+=(--version "$VERSION")
INSTALLER="$(mktemp)"; trap 'rm -f "$INSTALLER"' EXIT
curl -fsSL "https://raw.githubusercontent.com/dirkvoss/frameside/main/install.sh" -o "$INSTALLER"
chmod 755 "$INSTALLER"
if [[ "$BENUTZER" == "root" ]]; then
  SHOWCASE_DIR="$HEIM/immich-showcase" bash "$INSTALLER" "${OPT[@]}"
else
  # Die neue Docker-Gruppe gilt erst nach einer neuen Anmeldung - fuer diesen Lauf deshalb ueber "sg".
  chmod 644 "$INSTALLER"; $SUDO chown "$BENUTZER" "$INSTALLER" 2>/dev/null || true
  sg docker -c "SHOWCASE_DIR='$HEIM/immich-showcase' bash '$INSTALLER' ${OPT[*]}"
fi

echo
echo "== 4/4  Fertig"
echo "  Der Raspberry Pi laeuft jetzt als Frameside-Server. Den Einrichtungs-Link siehst du oben."
echo "  Die iPhone-App findet den Server im WLAN von selbst."
PORTTEIL=":${PORT:-8090}"; [[ "${PORT:-}" == "80" ]] && PORTTEIL=""
[[ -n "$HOSTNAME_NEU" ]] && echo "  Im Heimnetz erreichbar unter:  http://$HOSTNAME_NEU.local$PORTTEIL"
echo "  Als Bilderrahmen am angeschlossenen Fernseher: ./setup-kiosk.sh (Raspberry Pi OS mit Desktop), siehe README."
echo "  Aktualisieren:  cd ~/immich-showcase && docker compose pull && docker compose up -d"
