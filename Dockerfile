FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY apps/api ./apps/api
RUN pip install --no-cache-dir .

ENV SOFTWARE_FACTORY_WORKSPACE_ROOT=/app/workspaces
EXPOSE 8080
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
