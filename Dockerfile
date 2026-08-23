FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SOFTWARE_FACTORY_WORKSPACE_ROOT=/app/workspaces \
    SOFTWARE_FACTORY_DATABASE_URL=sqlite:////app/data/software_factory.db

RUN groupadd --system factory && useradd --system --gid factory --home /app factory

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY apps/api ./apps/api
RUN pip install --no-cache-dir . \
    && mkdir -p /app/workspaces /app/data \
    && chown -R factory:factory /app

USER factory
EXPOSE 8080

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
