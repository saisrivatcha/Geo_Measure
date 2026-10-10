# GeoMeasure backend image.
#
# GDAL, PROJ and GEOS come from the pyogrio / pyproj / shapely manylinux wheels,
# which bundle matching, tested native libraries (including the PROJ database and
# the Shapefile/KML/LIBKML drivers). That avoids version skew between a distro
# GDAL and the Python bindings; scripts/check_geo_stack.py verifies the stack at
# build time so a broken image never ships.

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------- builder ----
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv /opt/venv

WORKDIR /build
COPY requirements.txt requirements-dev.txt ./

ARG INSTALL_DEV=false
RUN pip install -r requirements.txt \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install -r requirements-dev.txt; fi

# ---------------------------------------------------------------- runtime ----
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    STORAGE_DIR=/app/storage

# Match the host user's UID so the bind-mounted ./storage stays writable.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --system --gid "${APP_GID}" app \
    && useradd --system --uid "${APP_UID}" --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app . .

RUN python scripts/check_geo_stack.py \
    && mkdir -p /app/storage \
    && chown app:app /app/storage \
    && chmod +x scripts/docker-entrypoint.sh

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]

ENTRYPOINT ["scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers"]
