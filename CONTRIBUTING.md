# Mitmachen

Schön, dass du helfen möchtest! Fehler, Wünsche und Pull Requests sind willkommen.

## Entwicklung
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q          # alle Tests, ohne Netzwerk und ohne echtes Immich
```
- Die Tests nutzen ein Schein-Immich (`tests/conftest.py`). Neue Funktionen bitte mit Tests.
- Für die Oberfläche gibt es eine Entwicklungsumgebung mit eigenem Test-Immich: siehe `dev/` und [RELEASING.md](RELEASING.md).
- Neue deutsche Texte in der Oberfläche brauchen einen Eintrag in `static/i18n/en.json` (mit `?lang=en` prüfen, `RW_MISS` in der Browser-Konsole listet Fehlendes).
- Nichts Persönliches einchecken (Adressen, Namen, Schlüssel); ein Test prüft das grob.

## Pull Requests
1. Fork, Branch, kleine nachvollziehbare Commits.
2. `python -m pytest -q` muss grün sein; GitHub Actions führt dieselben Tests plus den Container-Rauchtest aus.
3. Beschreibe, **was** und **warum**; bei Oberflächenänderungen gern ein Bild.

## Lizenz
Mit deinem Beitrag stimmst du zu, dass er unter der [AGPL-3.0-or-later](LICENSE) veröffentlicht wird.
