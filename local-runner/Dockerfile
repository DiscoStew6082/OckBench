FROM ghcr.io/astral-sh/uv@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58

ARG OCKBENCH_SOURCE_REVISION=working-tree
LABEL org.opencontainers.image.title="OckBench pinned local runner"
LABEL org.opencontainers.image.revision="$OCKBENCH_SOURCE_REVISION"

ENV UV_PROJECT_ENVIRONMENT=/opt/ockbench/.venv \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/cache \
    TIKTOKEN_CACHE_DIR=/opt/ockbench/tiktoken-cache

WORKDIR /bench

COPY pyproject.toml uv.lock README.md ./
COPY main.py conftest.py ./
COPY src ./src
COPY tests ./tests
COPY configs ./configs
COPY data ./data
COPY docs ./docs
COPY scripts ./scripts
COPY local-runner/ockbench_local /opt/ockbench-local/ockbench_local

RUN uv sync --frozen --no-editable \
    && mkdir -p "$TIKTOKEN_CACHE_DIR" \
    && /opt/ockbench/.venv/bin/python -c 'import tiktoken; tiktoken.get_encoding("cl100k_base")' \
    && chmod -R a+rX /bench /opt/ockbench

ENV PYTHONPATH=/opt/ockbench-local:/bench

ENTRYPOINT ["/opt/ockbench/.venv/bin/python", "-m", "ockbench_local.main"]
CMD ["--help"]
