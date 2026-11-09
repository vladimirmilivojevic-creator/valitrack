# One image: the React app is built first and then served by the FastAPI server.

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    STATIC_DIR=/app/static
WORKDIR /app
COPY backend/ ./
RUN pip install .
COPY --from=web /web/dist ./static
RUN useradd --create-home --uid 10001 valitrack && chown -R valitrack /app
USER valitrack
EXPOSE 8000
CMD ["sh", "start.sh"]
