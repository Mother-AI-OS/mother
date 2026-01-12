# Mother AI OS - Container Deployment
# https://github.com/Mother-AI-OS/mother

FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md LICENSE ./
COPY mother/ ./mother/

# Build wheel
RUN pip install --no-cache-dir build && \
    python -m build --wheel

# --- Runtime Stage ---
FROM python:3.11-slim

LABEL org.opencontainers.image.title="Mother AI OS"
LABEL org.opencontainers.image.description="AI agent operating system with policy governance"
LABEL org.opencontainers.image.url="https://github.com/Mother-AI-OS/mother"
LABEL org.opencontainers.image.source="https://github.com/Mother-AI-OS/mother"
LABEL org.opencontainers.image.licenses="MIT"

# Create non-root user for security
RUN groupadd --gid 1000 mother && \
    useradd --uid 1000 --gid mother --shell /bin/bash --create-home mother

WORKDIR /app

# Install runtime dependencies (for PDF processing, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install wheel from builder
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Create directories for runtime data
RUN mkdir -p /app/workspace /app/logs /home/mother/.config/mother && \
    chown -R mother:mother /app /home/mother/.config

# Switch to non-root user
USER mother

# Environment defaults (override at runtime)
ENV MOTHER_HOST=0.0.0.0
ENV MOTHER_PORT=8080
ENV MOTHER_SAFE_MODE=true
ENV MOTHER_SANDBOX_MODE=true
ENV MOTHER_REQUIRE_AUTH=true
ENV MOTHER_AUDIT_ENABLED=true
ENV MOTHER_LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:${MOTHER_PORT}/health').raise_for_status()"

EXPOSE 8080

# Run the server
CMD ["mother", "serve"]
