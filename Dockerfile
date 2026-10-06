# Multi-stage: the build stage carries the toolchain, the runtime image does not.
FROM python:3.12-slim AS builder

WORKDIR /build
# Dependencies are installed before the source is copied, so editing code does
# not invalidate the dependency layer.
RUN pip install --no-cache-dir --prefix=/install \
    "fastapi>=0.115" "uvicorn>=0.30" "sqlalchemy[asyncio]>=2.0.30" \
    "aiosqlite>=0.20" "asyncpg>=0.29" "pydantic>=2.9" "pydantic-settings>=2.6" "httpx>=0.27"

FROM python:3.12-slim

# Running as a non-root user is the one hardening step that costs nothing.
RUN useradd --create-home --uid 1000 app
WORKDIR /srv

COPY --from=builder /install /usr/local
COPY src ./src

ENV PYTHONPATH=/srv/src \
    CACHE_DATABASE_URL="sqlite+aiosqlite:////srv/data/cache.db" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p /srv/data && chown -R app:app /srv
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://localhost:8000/health').status_code==200 else 1)"

CMD ["uvicorn", "cache_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
