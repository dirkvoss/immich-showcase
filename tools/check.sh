#!/usr/bin/env bash
# Vor jedem Push ausfuehren: prueft dieselben Dinge wie die CI (ohne die schweren Docker-Tests; mit --docker auch den Container-Rauchtest).
#   tools/check.sh            schnell (Quelltext, Skripte, YAML, Compose, Tests)
#   tools/check.sh --docker   zusaetzlich Container bauen und testen (braucht Docker)
# Mit PYTHON=/pfad/zu/python eine andere Python-Umgebung (mit den Paketen aus requirements-dev.txt) nutzen.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY="${PYTHON:-python3}"

echo "== Quelltext ohne Warnungen lesen (z. B. ungueltige Escape-Zeichen)"
"$PY" -W error::SyntaxWarning - <<'PYEOF'
import ast, glob
for f in sorted(glob.glob("*.py") + glob.glob("tests/*.py") + glob.glob("dev/*.py")):
    ast.parse(open(f, encoding="utf-8").read(), f)
PYEOF

echo "== Shell-Skripte"
for f in $(git ls-files '*.sh'); do bash -n "$f" || { echo "Syntaxfehler in $f"; exit 1; }; done

echo "== YAML (Workflows, Beispiele, Compose)"
"$PY" - <<'PYEOF'
import glob, sys
try:
    import yaml
except ImportError:
    print("(PyYAML fehlt - uebersprungen; pip install pyyaml)"); sys.exit(0)
dateien = glob.glob(".github/**/*.yml", recursive=True) + glob.glob("examples/**/*.y*ml", recursive=True) + glob.glob("*.yml") + glob.glob("dev/*.yml")
for f in sorted(dateien):
    yaml.safe_load(open(f, encoding="utf-8"))
print(len(dateien), "Dateien gueltig")
PYEOF

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "== Compose-Dateien"
  sed -e 's|^RAHMEN_IMMICH_URL=$|RAHMEN_IMMICH_URL=http://immich:2283/api|' -e 's|^RAHMEN_IMMICH_KEY=$|RAHMEN_IMMICH_KEY=x|' .env.example > .env
  trap 'rm -f .env' EXIT
  docker compose config -q
  (cd examples/immich-stack && DB_PASSWORD=x docker compose config -q)
else
  echo "== Compose-Dateien: uebersprungen (kein Docker)"
fi

echo "== Tests"
"$PY" -m pytest -q

echo "== Keine Backup-/Env-Dateien im Arbeitsbaum"
if git ls-files --others --exclude-standard | grep -E '\.(bak|orig|tmp)$|(^|/)\.env$|container\.env'; then echo "Unerwartete Dateien (siehe oben)"; exit 1; fi

if [[ "${1:-}" == "--docker" ]]; then echo "== Container-Rauchtest"; bash tests/smoke_container.sh; fi
echo "Alles in Ordnung."
