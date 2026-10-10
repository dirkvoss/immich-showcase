"""deploy/deploy.sh gegen ein vorgetaeuschtes Docker: Erfolg, Ablehnung mit Rueckweg, Trockenlauf, Rollback, Sicherung."""
import http.server
import json
import os
import shutil
import stat
import subprocess
import threading

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKRIPT = os.path.join(RAIZ, "deploy", "deploy.sh")

FAKE_DOCKER = r'''#!/usr/bin/env bash
# Schein-Docker: "laufende" Version steht in $FAKE/laeuft, nicht ziehbare Versionen in $FAKE/fehlt, kaputte in $FAKE/kaputt
case "$1" in
  pull) v="${@: -1}"; v="${v##*:}"; grep -qx "$v" "$FAKE/fehlt" 2>/dev/null && { echo "manifest unknown" >&2; exit 1; }; touch "$FAKE/img-$v"; exit 0 ;;
  image) exit 0 ;;
  images) ls "$FAKE" | sed -n 's/^img-//p' | sed 's/^/img:/' ; exit 0 ;;
  rmi) exit 0 ;;
  compose)
    shift
    if [[ "$1" == "exec" ]]; then
      v="$(cat "$FAKE/laeuft")"
      if grep -qx "$v" "$FAKE/pruefung-faellt-durch" 2>/dev/null; then echo "FEHL Immich: Filter und Zaehler"; exit 1; fi
      echo "OK   Konfiguration erreichbar"; exit 0
    fi
    if [[ "$1" == "up" ]]; then
      v="$(grep -E '^SHOWCASE_VERSION=' .env | cut -d= -f2)"
      if grep -qx "$v" "$FAKE/kaputt" 2>/dev/null; then echo "" > "$FAKE/laeuft"; else echo "$v" > "$FAKE/laeuft"; fi
    fi
    exit 0 ;;
esac
exit 0
'''


class Health(http.server.BaseHTTPRequestHandler):
    fake = None

    def do_GET(self):
        v = open(os.path.join(Health.fake, "laeuft")).read().strip() if os.path.exists(os.path.join(Health.fake, "laeuft")) else ""
        if not v:
            self.send_response(503); self.end_headers(); return
        body = json.dumps({"name": "Frameside", "version": v}).encode() if self.path == "/api/config" else b"{}"
        self.send_response(200); self.end_headers(); self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def umgebung(tmp_path):
    fake = tmp_path / "fake"; fake.mkdir()
    bin_ = tmp_path / "bin"; bin_.mkdir()
    d = bin_ / "docker"; d.write_text(FAKE_DOCKER); d.chmod(d.stat().st_mode | stat.S_IEXEC)
    srv = tmp_path / "srv"; (srv / "data").mkdir(parents=True)
    (srv / "docker-compose.yml").write_text("services: {}\n")
    (srv / ".env").write_text("SHOWCASE_VERSION=1.0.0\n")
    (srv / "data" / "shows.json").write_text('{"shows": []}')
    (srv / "data" / "videos").mkdir(); (srv / "data" / "videos" / "gross.mp4").write_text("x" * 100)
    (fake / "laeuft").write_text("1.0.0\n")
    Health.fake = str(fake)
    httpd = http.server.HTTPServer(("127.0.0.1", 0), Health)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    env = dict(os.environ, PATH=f"{bin_}:{os.environ['PATH']}", FAKE=str(fake), SHOWCASE_DIR=str(srv),
               SHOWCASE_HEALTH_URL=f"http://127.0.0.1:{httpd.server_port}", SHOWCASE_WAIT_SECONDS="4", SHOWCASE_IMAGE="test/showcase")

    def lauf(*args, **zusatz):
        return subprocess.run(["bash", SKRIPT, *args], env={**env, **zusatz}, capture_output=True, text=True)
    yield lauf, srv, fake
    httpd.shutdown()


def laeuft(fake):
    return (fake / "laeuft").read_text().strip()


def test_erfolgreiches_update_mit_sicherung(umgebung):
    lauf, srv, fake = umgebung
    r = lauf("1.1.0")
    assert r.returncode == 0, r.stderr
    assert laeuft(fake) == "1.1.0" and "SHOWCASE_VERSION=1.1.0" in (srv / ".env").read_text()
    sicherungen = list((srv / "backups").glob("showcase-*-v1.0.0.tgz"))
    assert len(sicherungen) == 1
    inhalt = subprocess.run(["tar", "tzf", str(sicherungen[0])], capture_output=True, text=True).stdout
    assert "data/shows.json" in inhalt and ".env" in inhalt and "videos" not in inhalt     # Daten ja, Zwischenspeicher nein


def test_kaputte_version_wird_abgelehnt_und_alte_laeuft_wieder(umgebung):
    lauf, srv, fake = umgebung
    (fake / "kaputt").write_text("1.2.0\n")
    r = lauf("1.2.0")
    assert r.returncode == 1
    assert laeuft(fake) == "1.0.0" and "SHOWCASE_VERSION=1.0.0" in (srv / ".env").read_text()
    assert "abgelehnt" in r.stderr


def test_nicht_vorhandene_version_aendert_nichts(umgebung):
    lauf, srv, fake = umgebung
    (fake / "fehlt").write_text("9.9.9\n")
    r = lauf("9.9.9")
    assert r.returncode == 1 and laeuft(fake) == "1.0.0"
    assert not (srv / "backups").exists()


def test_trockenlauf(umgebung):
    lauf, srv, fake = umgebung
    r = lauf("1.3.0", "--dry-run")
    assert r.returncode == 0 and laeuft(fake) == "1.0.0" and "SHOWCASE_VERSION=1.0.0" in (srv / ".env").read_text()


def test_rollback(umgebung):
    lauf, srv, fake = umgebung
    assert lauf("1.1.0").returncode == 0
    r = lauf("--rollback")
    assert r.returncode == 0, r.stderr
    assert laeuft(fake) == "1.0.0"


def test_ungueltige_version(umgebung):
    lauf, _, fake = umgebung
    assert lauf("abc").returncode == 1
    assert lauf("1.2").returncode == 1


def test_status(umgebung):
    lauf, _, _ = umgebung
    assert "laeuft: 1.0.0" in lauf("--status").stdout


def test_zusaetzliche_verzeichnisse_werden_gesichert(umgebung, tmp_path):
    lauf, srv, fake = umgebung
    extra = tmp_path / "state"; extra.mkdir(); (extra / "zustand.json").write_text("{}")
    assert lauf("1.4.0", SHOWCASE_EXTRA_BACKUP=str(extra)).returncode == 0
    sicherung = next((srv / "backups").glob("showcase-*.tgz"))
    inhalt = subprocess.run(["tar", "tzf", str(sicherung)], capture_output=True, text=True).stdout
    assert "zustand.json" in inhalt and "data/shows.json" in inhalt


def test_fehlgeschlagene_pruefung_nach_dem_deploy_rollt_zurueck(umgebung):
    lauf, srv, fake = umgebung
    (fake / "pruefung-faellt-durch").write_text("1.5.0\n")
    r = lauf("1.5.0")
    assert r.returncode == 1
    assert laeuft(fake) == "1.0.0" and "SHOWCASE_VERSION=1.0.0" in (srv / ".env").read_text()      # trotz laufendem, gesundem Dienst
    assert "Pruefungen nicht" in r.stderr and "FEHL Immich" in r.stderr


def test_bestandene_pruefung_zeigt_ergebnis(umgebung):
    lauf, srv, fake = umgebung
    r = lauf("1.6.0")
    assert r.returncode == 0 and "OK   Konfiguration erreichbar" in r.stderr and "Pruefungen bestanden" in r.stderr


def test_pruefung_kann_abgeschaltet_werden(umgebung):
    lauf, srv, fake = umgebung
    (fake / "pruefung-faellt-durch").write_text("1.7.0\n")
    assert lauf("1.7.0", SHOWCASE_POSTDEPLOY="0").returncode == 0
