# Multi-stage build for fable-mcp (paper-only MCP + health sidecar).
# Datei: Dockerfile
# Zweck: Release-Binary fuer Cursor MCP Clients und Compose health mode.

FROM rust:1.85-bookworm AS builder
WORKDIR /src
COPY Cargo.toml Cargo.lock* ./
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && useradd --create-home --uid 10001 fable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /src/target/release/fable-mcp /usr/local/bin/fable-mcp
USER fable
ENV FABLE_MCP_MODE=health \
    FABLE_MCP_HEALTH_PORT=9100 \
    FABLE_MCP_BRIDGE_URL=http://api:8000 \
    FABLE_MCP_BRIDGE_ENABLED=true \
    FABLE_MCP_DEFAULT_PAIR=ADAUSD
EXPOSE 9100
# Health mode keeps the container alive; attach /usr/local/bin/fable-mcp for MCP stdio.
CMD ["fable-mcp", "--health"]
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD curl -fsS http://127.0.0.1:9100/ || exit 1
