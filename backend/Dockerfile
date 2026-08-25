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

# The executable bit does not survive a clone on Windows, so set it in the
# image regardless of what the host filesystem reports.
RUN chmod +x bin/web bin/worker

# Drop privileges. Done after collectstatic so /app can stay root-owned and
# read-only to the app user.
RUN useradd --system --create-home --uid 1001 appuser
USER appuser

EXPOSE 8000

# Both process commands live in bin/. fly.toml's [processes] references the
# same scripts, so there is one definition of how each process starts.
CMD ["/app/bin/web"]
