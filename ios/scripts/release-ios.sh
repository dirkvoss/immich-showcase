#!/usr/bin/env bash
# Baut ein Archiv für TestFlight und lädt es zu App Store Connect hoch.
#   ./scripts/release-ios.sh                 # testen, bauen, hochladen
#   ./scripts/release-ios.sh --nur-bauen     # Archiv erzeugen, nicht hochladen
#   ./scripts/release-ios.sh --version 0.2   # Marketing-Version mitsetzen
# Einmalig: App-Eintrag in App Store Connect, scripts/release.env (KEY_ID, ISSUER_ID, TEAM_ID), Profil: node scripts/asc.js profil
set -euo pipefail
cd "$(dirname "$0")/.."
export DEVELOPER_DIR="${DEVELOPER_DIR:-$(xcode-select -p)}"
SCHEMA="ShowcaseImmich"; BUNDLE_ID="com.dirk-voss.showcase"; PROFIL="Showcase Immich App Store"
PROFIL_TEILEN="Showcase Immich Teilen App Store"; PROFIL_WIDGET="Showcase Immich Widget App Store"
ARCHIV_ORDNER="build/archive"; NUR_BAUEN=0; VERSION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --nur-bauen) NUR_BAUEN=1; shift ;;
    --version) VERSION="${2:?--version braucht eine Zahl, z. B. 0.2}"; shift 2 ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
  esac
done
meldung() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
abbruch() { printf '\n\033[31mAbbruch: %s\033[0m\n' "$1" >&2; exit 1; }
[[ -f scripts/release.env ]] && source scripts/release.env
: "${KEY_ID:?KEY_ID fehlt in scripts/release.env}"; : "${ISSUER_ID:?ISSUER_ID fehlt}"; : "${TEAM_ID:?TEAM_ID fehlt}"
SCHLUESSEL="${SCHLUESSEL:-$HOME/.appstoreconnect/private_keys/AuthKey_$KEY_ID.p8}"
[[ -f "$SCHLUESSEL" ]] || abbruch "API-Schlüssel nicht gefunden: $SCHLUESSEL"
command -v xcodegen >/dev/null || abbruch "xcodegen fehlt (brew install xcodegen)"
security find-identity -v -p codesigning | grep -q "Apple Distribution" || abbruch "Kein Apple-Distribution-Zertifikat im Schlüsselbund"
for P in "$PROFIL" "$PROFIL_TEILEN" "$PROFIL_WIDGET"; do
  gefunden=0
  for f in "$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles"/*.mobileprovision; do grep -a -q "$P" "$f" 2>/dev/null && { gefunden=1; break; }; done
  [[ "$gefunden" == 1 ]] || abbruch "Verteilungsprofil '$P' fehlt – einmalig: node scripts/asc.js profil"
done

meldung "Tests"; ./scripts/test.sh | tail -3
BUILD="$(date +%Y%m%d%H%M)"                                   # steigt immer; App Store Connect nimmt keine Nummer zweimal
[[ -n "$VERSION" ]] || VERSION="$(grep -m1 'MARKETING_VERSION:' project.yml | sed 's/.*"\(.*\)".*/\1/')"
meldung "Version $VERSION (Build $BUILD)"
xcodegen generate --quiet
rm -rf "$ARCHIV_ORDNER"; mkdir -p "$ARCHIV_ORDNER"; ARCHIV="$ARCHIV_ORDNER/$SCHEMA.xcarchive"
meldung "Archiv bauen"
xcodebuild archive -project "$SCHEMA.xcodeproj" -scheme "$SCHEMA" -configuration Release -destination "generic/platform=iOS" -archivePath "$ARCHIV" \
  -allowProvisioningUpdates -authenticationKeyPath "$SCHLUESSEL" -authenticationKeyID "$KEY_ID" -authenticationKeyIssuerID "$ISSUER_ID" \
  DEVELOPMENT_TEAM="$TEAM_ID" MARKETING_VERSION="$VERSION" CURRENT_PROJECT_VERSION="$BUILD" | tail -5
[[ -d "$ARCHIV" ]] || abbruch "Kein Archiv entstanden"
meldung "Archiv fertig: $ARCHIV"
[[ "$NUR_BAUEN" == "1" ]] && { echo "Nicht hochgeladen (--nur-bauen)."; exit 0; }

meldung "Zu App Store Connect hochladen"
cat > "$ARCHIV_ORDNER/export.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>method</key><string>app-store-connect</string>
  <key>destination</key><string>upload</string>
  <key>uploadSymbols</key><true/>
  <key>manageAppVersionAndBuildNumber</key><false/>
  <key>signingStyle</key><string>manual</string>
  <key>signingCertificate</key><string>Apple Distribution</string>
  <key>teamID</key><string>${TEAM_ID}</string>
  <key>provisioningProfiles</key><dict><key>${BUNDLE_ID}</key><string>${PROFIL}</string><key>${BUNDLE_ID}.teilen</key><string>${PROFIL_TEILEN}</string><key>${BUNDLE_ID}.widget</key><string>${PROFIL_WIDGET}</string></dict>
</dict></plist>
PLIST
xcodebuild -exportArchive -archivePath "$ARCHIV" -exportOptionsPlist "$ARCHIV_ORDNER/export.plist" -allowProvisioningUpdates \
  -authenticationKeyPath "$SCHLUESSEL" -authenticationKeyID "$KEY_ID" -authenticationKeyIssuerID "$ISSUER_ID" | tail -8
meldung "Hochgeladen: Version $VERSION (Build $BUILD)"
echo "In App Store Connect → TestFlight erscheint der Build nach ein paar Minuten (Verarbeitung). Stand prüfen:  node scripts/asc.js app"
