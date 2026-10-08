#!/usr/bin/env bash
# Unit-Tests im Simulator.   ./scripts/test.sh [Geraet]
set -euo pipefail
cd "$(dirname "$0")/.."
GERAET="${1:-iPhone 17 Pro}"
xcodegen generate >/dev/null
xcodebuild -project ShowcaseImmich.xcodeproj -scheme ShowcaseImmich -destination "platform=iOS Simulator,name=$GERAET" -derivedDataPath build/dd CODE_SIGNING_ALLOWED=NO test 2>&1 | grep -E "Test Suite|Executed|error:|FAILED|passed|failed" | tail -12
