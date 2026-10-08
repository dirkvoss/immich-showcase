#!/usr/bin/env bash
# Baut die App und startet sie im iPhone-Simulator.   ./scripts/run-sim.sh [Geraet]
set -euo pipefail
cd "$(dirname "$0")/.."
GERAET="${1:-iPhone 17 Pro}"
xcodegen generate >/dev/null
xcodebuild -project ShowcaseImmich.xcodeproj -scheme ShowcaseImmich -destination "platform=iOS Simulator,name=$GERAET" -derivedDataPath build/dd CODE_SIGNING_ALLOWED=NO build | tail -3
xcrun simctl boot "$GERAET" 2>/dev/null || true
open -a Simulator
xcrun simctl install "$GERAET" build/dd/Build/Products/Debug-iphonesimulator/ShowcaseImmich.app
xcrun simctl launch "$GERAET" com.dirk-voss.showcase
