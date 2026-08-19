# syntax=docker/dockerfile:1.7
ARG NODE_VERSION=20-alpine
ARG PYTHON_VERSION=3.12-slim
ARG APP_VERSION=1.02beta
ARG YTDLP_VERSION=2026.06.09

FROM node:${NODE_VERSION} AS ui
WORKDIR /build
COPY package.json package-lock.json* .npmrc* vite.config.js tailwind.config.js postcss.config.js ./
COPY ui ./ui
RUN mkdir -p app/static \
 && npm config set registry https://registry.npmjs.org/ && npm ci --no-fund --no-audit \
 && npm run build \
 && test -f app/static/index.html \
 && test -d app/static/assets \
 && echo "UI build OK: $(ls app/static/assets | wc -l) assets"

FROM python:${PYTHON_VERSION} AS runtime
ARG APP_VERSION
ARG YTDLP_VERSION=2026.06.09
LABEL org.opencontainers.image.title="mediaos" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.source="https://github.com/newguy467/MediaOs" \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    APP_VERSION=${APP_VERSION} YOUTUBE_YTDLP_PATH=yt-dlp \
    CARDIGANN_DEFINITIONS_PATH=/app/definitions
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates ffmpeg gosu postgresql-client smartmontools \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "yt-dlp==${YTDLP_VERSION}" \
    && yt-dlp --version
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY ai ./ai
COPY scripts ./scripts
COPY definitions ./definitions
COPY docs ./docs
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
# Full Vite output (index, hashed assets, logos from ui/public)
COPY --from=ui /build/app/static/ ./app/static/
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Run as non-root
RUN groupadd --system --gid 1000 mediaos \
 && useradd --system --uid 1000 --gid mediaos --home-dir /app --shell /usr/sbin/nologin mediaos \
 && mkdir -p /app/data /app/static \
 && chown -R mediaos:mediaos /app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
