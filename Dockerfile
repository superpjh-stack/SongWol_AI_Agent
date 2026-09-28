FROM node:22-alpine AS web-build
WORKDIR /build/v2/web
COPY v2/web/package.json v2/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY v2/web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SONGWOL_DB_PATH=/app/data/songwol_demo.db
WORKDIR /app
COPY v2/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --disable-pip-version-check -r /tmp/requirements.lock \
 && useradd --system --uid 10001 --create-home appuser \
 && mkdir -p /app/data
COPY --chown=10001:10001 songwol_agent/ /app/songwol_agent/
COPY --chown=10001:10001 sample_docs/ /app/sample_docs/
COPY --chown=10001:10001 v2/ /app/v2/
COPY --from=web-build --chown=10001:10001 /build/v2/web/dist/ /app/v2/web/dist/
RUN chown -R 10001:10001 /app/data
USER 10001:10001
EXPOSE 8513
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8513/api/health', timeout=3)" || exit 1
CMD ["uvicorn", "v2.api:app", "--host", "0.0.0.0", "--port", "8513", "--no-proxy-headers"]
