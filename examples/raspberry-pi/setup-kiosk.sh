#!/usr/bin/env bash
# Raspberry Pi als Bilderrahmen / Fernseher-Anzeige fuer Immich Showcase einrichten (Chromium im Kiosk-Modus, startet beim Einschalten).
# Fuer Raspberry Pi OS mit Desktop (Bookworm oder neuer). Als normaler Benutzer ausfuehren (nicht root); fuer die Installation fragt sudo nach dem Passwort.
#
#   ./setup-kiosk.sh http://192.168.1.20:8090/tv/?ziel=rahmen     fester Rahmen (Kennung wie in .env: RAHMEN_WEB_RAHMEN_ZIELE)
#   ./setup-kiosk.sh http://192.168.1.20:8090/tv/                 ohne Kennung: zeigt einen Code zum Koppeln in der App (empfohlen)
#   ./setup-kiosk.sh --entfernen                                  Autostart wieder entfernen
#
# Hinweis: Dieses Skript wurde geschrieben, aber nicht auf jedem Pi-Modell getestet. Rueckmeldungen sind willkommen.
set -euo pipefail

STARTER="$HOME/immich-showcase-kiosk.sh"
DESKTOP="$HOME/.config/autostart/immich-showcase-kiosk.desktop"
LABWC="$HOME/.config/labwc/autostart"
MARKE="# immich-showcase-kiosk"
marke_entfernen() { [[ -f "$LABWC" ]] && { grep -v "$MARKE" "$LABWC" > "$LABWC.tmp" || true; mv "$LABWC.tmp" "$LABWC"; } || true; }

if [[ "${1:-}" == "--entfernen" ]]; then
  rm -f "$STARTER" "$DESKTOP"
  marke_entfernen
  echo "Autostart entfernt. Beim naechsten Neustart startet der Kiosk nicht mehr."
  exit 0
fi

URL="${1:-}"
[[ "$URL" =~ ^https?://[^[:space:]]+$ ]] || { echo "Aufruf: $0 <Adresse>   z. B. $0 http://192.168.1.20:8090/tv/"; exit 1; }
[[ $EUID -ne 0 ]] || { echo "Bitte nicht als root ausfuehren, sondern als der Benutzer, der am Desktop angemeldet ist."; exit 1; }

echo "== Chromium installieren (falls noetig)"
if ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y chromium || sudo apt-get install -y chromium-browser
fi
BROWSER="$(command -v chromium || command -v chromium-browser)"

echo "== Bildschirm nicht mehr ausgehen lassen"
command -v raspi-config >/dev/null 2>&1 && sudo raspi-config nonint do_blanking 1 || echo "(raspi-config nicht gefunden - Energiesparen des Bildschirms bitte selbst ausschalten)"

echo "== Starter schreiben: $STARTER"
cat > "$STARTER" <<STARTER_EOF
#!/usr/bin/env bash
# Wartet, bis Immich Showcase erreichbar ist, und startet Chromium im Kiosk-Modus. Stuerzt der Browser ab, startet er neu.
exec 9>/tmp/immich-showcase-kiosk.lock; flock -n 9 || exit 0      # nur eine Instanz (falls zwei Autostart-Wege greifen)
URL="$URL"
HOST="\${URL#*://}"; HOST="\${HOST%%/*}"
until curl -fsS -m 3 -o /dev/null "http://\$HOST/api/config" 2>/dev/null || curl -fsS -m 3 -k -o /dev/null "https://\$HOST/api/config" 2>/dev/null; do sleep 5; done
while true; do
  "$BROWSER" --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --no-first-run \\
    --check-for-update-interval=31536000 --autoplay-policy=no-user-gesture-required --overscroll-history-navigation=0 \\
    --disable-features=TranslateUI "\$URL"
  sleep 3
done
STARTER_EOF
chmod +x "$STARTER"

echo "== Autostart eintragen"
mkdir -p "$(dirname "$DESKTOP")" "$(dirname "$LABWC")"
cat > "$DESKTOP" <<DESKTOP_EOF
[Desktop Entry]
Type=Application
Name=Immich Showcase Kiosk
Exec=$STARTER
X-GNOME-Autostart-enabled=true
DESKTOP_EOF
touch "$LABWC"; marke_entfernen; echo "$STARTER & $MARKE" >> "$LABWC"      # Wayland (labwc, Raspberry Pi OS Bookworm)

echo
echo "Fertig. Neu starten:  sudo reboot"
echo "Danach startet der Pi von selbst im Vollbild mit:  $URL"
[[ "$URL" == */tv/ ]] && echo "Auf dem Bildschirm erscheint ein Code: in der App unter 'Geraete' eingeben (oder den QR-Code scannen)."
echo "Zum Beenden des Kiosk-Modus: Tastatur anschliessen, Alt+F4. Entfernen: $0 --entfernen"
