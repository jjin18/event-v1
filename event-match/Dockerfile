# Top-level Dockerfile that Railway / Render / Fly.io / Cloud Run auto-detect.
#
# Builds the event-match matching API. Mirrors event-v1's Dockerfile so
# they deploy with the same pattern.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of the repo (prompts/, packages/, apps/, data/.gitkeep files).
COPY . .

# Railway / Render / Fly inject $PORT. Default 8001 to match local dev.
ENV PORT=8001
EXPOSE 8001

CMD ["sh", "-c", "python -m uvicorn apps.api:app --host 0.0.0.0 --port ${PORT:-8001}"]
