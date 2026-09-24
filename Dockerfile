# Multi-stage build: Node builds the frontend, and the final image contains only Python and the
# built files. Build stages don't end up in the final image, so it stays small.

# ---- Stage 1: build the React app ----
FROM node:22-alpine AS frontend
WORKDIR /frontend
# Copy the dependency files first: Docker caches this layer, so npm ci only re-runs when they change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: the server ----
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY fitflow/ fitflow/
RUN pip install --no-cache-dir ".[postgres]"

COPY --from=frontend /frontend/dist ./frontend/dist
ENV FRONTEND_DIST=/app/frontend/dist

# Don't run as root: if the app is ever compromised, the attacker has fewer permissions.
RUN useradd --create-home fitflow && chown -R fitflow /app
USER fitflow

# Hosting platforms pass the port in $PORT; default to 8000 locally.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn fitflow.web:web --host 0.0.0.0 --port ${PORT:-8000}"]
