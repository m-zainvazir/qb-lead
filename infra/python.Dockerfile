# One image for the API and the worker. Build with:
#   docker build -f infra/python.Dockerfile --build-arg PACKAGE=api -t leadgen-api .
FROM ghcr.io/astral-sh/uv:0.13.9 AS uv

FROM python:3.12-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
ARG PACKAGE
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/core packages/core
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/api/api apps/api/api
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY apps/worker/worker apps/worker/worker
RUN uv sync --frozen --no-dev --no-editable --package ${PACKAGE}

FROM python:3.12-slim
ARG GIT_COMMIT=dev
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 GIT_COMMIT=${GIT_COMMIT} \
    HOME=/tmp HF_HOME=/models/hf
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app  && mkdir -p /models && chown app:app /models
WORKDIR /app
COPY --from=build --chown=app:app /app/.venv /app/.venv
USER 10001
EXPOSE 8000
CMD ["uvicorn", "api.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
