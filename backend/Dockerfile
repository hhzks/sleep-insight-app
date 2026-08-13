# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build dependencies into a self-contained virtualenv.
# Kept separate so pip's build tooling never ships in the runtime image.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copied alone so the layer caches on requirements.txt, not on app source.
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: runtime.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# psycopg2-binary bundles its own libpq, so no runtime apt packages are needed.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY . .

# Baked into the image so boot is pure gunicorn: no per-start collectstatic,
# and the WhiteNoise hash manifest is identical across every machine running
# this image. Needs no database - only settings import.
RUN DJANGO_SECRET_KEY=build-only-not-used \
    python manage.py collectstatic --no-input

# Drop privileges. Done after collectstatic so /app can stay root-owned and
# read-only to the app user.
RUN useradd --system --create-home --uid 1001 appuser
USER appuser

EXPOSE 8000

# Worker sizing note: ai_insights/jobs.py runs generation in a daemon thread
# inside the web process for up to OLLAMA_TIMEOUT_SECONDS * (1 + retries).
# gthread keeps those threads cheap while the process stays responsive.
# At 512MB, 2 workers is the ceiling - if you see OOM kills, either drop to
# --workers 1 or raise the machine to 1GB in fly.toml.
#
# --graceful-timeout is deliberately short: a daemon thread cannot survive
# interpreter exit regardless, and reap_stale_jobs() converts the orphaned
# InsightJob row into a clean failure. Waiting longer just slows deploys.
CMD ["gunicorn", "sleep_tracker.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--worker-class", "gthread", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
