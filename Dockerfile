FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY app ./app
ARG INSTALL_ANOMALY_DEPENDENCIES=0
RUN if [ "$INSTALL_ANOMALY_DEPENDENCIES" = "1" ]; then \
        python -m pip wheel --no-cache-dir --wheel-dir /wheels '.[anomalies]'; \
    else \
        python -m pip wheel --no-cache-dir --wheel-dir /wheels .; \
    fi

FROM python:3.12-slim AS runtime

ARG INSTALL_ANOMALY_DEPENDENCIES=0
# Render mounts runtime secret files with group 1000.
RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --no-create-home --shell /usr/sbin/nologin appuser \
    && if [ "$INSTALL_ANOMALY_DEPENDENCIES" = "1" ]; then \
        (getent group 1000 >/dev/null || groupadd --gid 1000 render-secrets) \
        && usermod --append --groups 1000 appuser; \
    fi
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY deploy/render/start.py ./render-start.py
COPY deploy/render/integrated.py ./deploy/render/integrated.py
COPY deploy/render/runtime.py ./deploy/render/runtime.py
COPY docs/assistant/*.md ./assistant-corpus/
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
