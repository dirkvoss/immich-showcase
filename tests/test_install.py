"""install.sh: erkennt Immich auf dem Rechner und bereitet die .env vor (mit einem nachgemachten `docker`, ohne etwas zu starten)."""
import os
import shutil
import stat
import subprocess

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAKE_DOCKER = r'''#!/usr/bin/env bash
# Nachgemachtes docker: antwortet nur auf das, was install.sh fragt.
case "$1" in
  compose) [[ "$2" == "version" ]] && echo "Docker Compose version v2.0.0"; exit 0 ;;
  ps)
    case "$*" in
      *"{{.Names}}	{{.Image}}"*) [[ -n "${FAKE_IMMICH:-}" ]] && printf '%s\tghcr.io/immich-app/immich-server:release\n' "$FAKE_IMMICH"; printf 'redis\tdocker.io/valkey/valkey:9\n'; exit 0 ;;
      *"{{.Names}}"*) [[ -n "${FAKE_IMMICH:-}" ]] && { echo "$FAKE_IMMICH"; echo "${FAKE_ML:-}"; }; echo redis; exit 0 ;;
      *) exit 0 ;;
    esac ;;
  inspect) echo "${FAKE_NETZ:-immich_default}"; exit 0 ;;
esac
exit 0
'''


def aktiv(datei):
    """Nur die wirksamen Zeilen der .env (ohne die erklaerenden Kommentare der Vorlage)."""
    return "\n".join(z for z in datei.read_text().splitlines() if z.strip() and not z.lstrip().startswith("#")) if datei.exists() else ""


def vorbereiten(tmp_path, env_extra=None, args=("--vorbereiten", "--no-open"), env_inhalt=None):
    ordner = tmp_path / "ziel"
    ordner.mkdir()
    for f in ("install.sh", "docker-compose.yml", "docker-compose.immich-network.yml", "docker-compose.bonjour.yml", ".env.example"):
        shutil.copy(os.path.join(RAIZ, f), ordner / f)
    if env_inhalt is not None:
        (ordner / ".env").write_text(env_inhalt)
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    d = bin_ / "docker"
    d.write_text(FAKE_DOCKER)
    d.chmod(d.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "HOME": str(tmp_path), "FAKE_NETZ": "meinimmich_default", **(env_extra or {})}
    r = subprocess.run(["bash", str(ordner / "install.sh"), *args], capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=60)
    return r, aktiv(ordner / ".env")


def test_immich_wird_erkannt_und_angebunden(tmp_path):
    r, env = vorbereiten(tmp_path, {"FAKE_IMMICH": "immich_server", "FAKE_ML": "immich_machine_learning"})
    assert r.returncode == 0, r.stderr
    assert "Immich erkannt" in r.stdout and "meinimmich_default" in r.stdout
    assert "SHOWCASE_IMMICH_NETWORK=meinimmich_default" in env
    assert "COMPOSE_FILE=docker-compose.yml:docker-compose.immich-network.yml" in env
    assert "RAHMEN_IMMICH_URL=http://immich_server:2283/api" in env
    assert "RAHMEN_ML_URL=http://immich_machine_learning:3003/predict" in env


def test_ohne_immich_gibt_es_einen_hinweis_und_keine_aenderung(tmp_path):
    r, env = vorbereiten(tmp_path)
    assert r.returncode == 0 and "Immich laeuft nicht auf diesem Rechner" in r.stdout
    assert "SHOWCASE_IMMICH_NETWORK" not in env and "COMPOSE_FILE" not in env


def test_vorhandene_adresse_wird_nicht_ueberschrieben(tmp_path):
    r, env = vorbereiten(tmp_path, {"FAKE_IMMICH": "immich_server"}, env_inhalt="RAHMEN_IMMICH_URL=http://mein-immich.lan:2283/api\n")
    assert "RAHMEN_IMMICH_URL=http://mein-immich.lan:2283/api" in env and "immich_server:2283" not in env


def test_bonjour_wird_nur_einmal_eingetragen(tmp_path):
    r, env = vorbereiten(tmp_path, {"FAKE_IMMICH": "immich_server"}, args=("--vorbereiten", "--no-open", "--bonjour"))
    assert "docker-compose.bonjour.yml" in env
    assert env.count("docker-compose.bonjour.yml") == 1
    ordner = tmp_path / "ziel"
    env2 = {**os.environ, "PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}", "HOME": str(tmp_path), "FAKE_IMMICH": "immich_server"}
    subprocess.run(["bash", str(ordner / "install.sh"), "--vorbereiten", "--no-open", "--bonjour"], capture_output=True, text=True, env=env2, timeout=60)
    spaeter = aktiv(ordner / ".env")
    assert spaeter.count("docker-compose.bonjour.yml") == 1                                            # zweiter Lauf: keine Doppelten
    assert spaeter.count("docker-compose.immich-network.yml") == 1


def test_port_und_tv_adresse(tmp_path):
    r, env = vorbereiten(tmp_path, args=("--vorbereiten", "--no-open", "--port", "8123"))
    assert "SHOWCASE_PORT=8123" in env


def test_unbekannte_option(tmp_path):
    r, _ = vorbereiten(tmp_path, args=("--quatsch",))
    assert r.returncode == 1 and "Unbekannte Option" in r.stdout
