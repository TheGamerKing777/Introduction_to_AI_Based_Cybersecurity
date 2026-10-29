FROM astral/uv:python3.11-trixie

WORKDIR /app

# Dependencies are declared in pyproject.toml and locked by uv.lock.
COPY pyproject.toml uv.lock* ./
RUN UV_PROJECT_ENVIRONMENT=/usr/local uv sync --frozen --no-dev --no-install-project

# Chainlit runs from a container-only runtime directory so .chainlit and .files
# are not created in the mounted source tree.
WORKDIR /chainlit-runtime

CMD ["/bin/bash"]
