FROM python:3.13-alpine as base

ENV PYTHONUNBUFFERED=1

WORKDIR /app


FROM base as builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_FROZEN=1
ENV UV_LINK_MODE=copy

RUN apk add --no-cache gcc musl-dev libffi-dev

COPY --from=ghcr.io/astral-sh/uv /uv /bin/uv

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-install-project --no-dev --no-editable

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-editable


FROM builder as test

RUN apk add --no-cache make

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-editable

RUN make lint


FROM base as final

ENV PATH="/app/.venv/bin:$PATH"
COPY --from=builder /app/.venv .venv

ENTRYPOINT [ "discord-music-bot" ]
