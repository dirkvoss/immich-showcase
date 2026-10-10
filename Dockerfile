FROM python:3.13-slim
LABEL org.opencontainers.image.source="https://github.com/dirkvoss/immich-showcase" org.opencontainers.image.licenses="AGPL-3.0-or-later" org.opencontainers.image.title="Immich Showcase"
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 RAHMEN_HELFER_DIR=/app \
    RAHMEN_WEB_PIN_FILE=/data/pin RAHMEN_WEB_SECRET_FILE=/data/secret RAHMEN_WEB_AUTH_STATE=/data/auth.json \
    RAHMEN_WEB_SHOWS_FILE=/data/shows.json RAHMEN_WEB_BENUTZER_FILE=/data/benutzer.json RAHMEN_WEB_PUSHOVER_FILE=/data/pushover \
    RAHMEN_STATE_DIR=/data/state
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg adb \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
# Ein Datenverzeichnis /data (Volume): PIN, Sitzungen, Shows, Zwischenspeicher, Musik, Zustand des Helfers (/data/state).
RUN pip install --no-cache-dir -r requirements.txt \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin rahmen \
 && mkdir -p /data/state && chown -R 10001:10001 /data
COPY rahmen_helfer.py rahmen_web.py anzeige.py telefontermine.py sonne.py postdeploy.py bonjour.py docker-entrypoint.sh ./
COPY static ./static
RUN python -W error::SyntaxWarning -c "import ast,sys; [ast.parse(open(f, encoding='utf-8').read(), f) for f in sys.argv[1:]]" rahmen_helfer.py rahmen_web.py anzeige.py telefontermine.py sonne.py postdeploy.py bonjour.py
RUN chmod 755 /app/docker-entrypoint.sh
ARG SHOWCASE_VERSION=dev
ENV SHOWCASE_VERSION=$SHOWCASE_VERSION
VOLUME ["/data"]
USER 10001:10001
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/api/me',timeout=4).status==200 else 1)"
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "rahmen_web:app", "--host", "0.0.0.0", "--port", "8090", "--no-proxy-headers", "--no-server-header"]
