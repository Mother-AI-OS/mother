---
sidebar_position: 2
---

# Docker Deployment

Run Mother AI OS in a container.

## Quick Start

```bash
docker run -d \
  --name mother \
  -p 8080:8080 \
  -e ANTHROPIC_API_KEY=your-key \
  -e MOTHER_API_KEY=your-mother-key \
  ghcr.io/mother-ai-os/mother:latest
```

## Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  mother:
    image: ghcr.io/mother-ai-os/mother:latest
    container_name: mother
    ports:
      - "8080:8080"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - MOTHER_API_KEY=${MOTHER_API_KEY}
      - MOTHER_LOG_LEVEL=INFO
    volumes:
      - ./plugins:/app/plugins:ro
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Run:

```bash
docker-compose up -d
```

## Building from Source

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application
COPY src/ src/

# Create non-root user
RUN useradd -m mother && chown -R mother:mother /app
USER mother

EXPOSE 8080

CMD ["python", "-m", "mother.api.app"]
```

Build and run:

```bash
docker build -t mother-ai-os .
docker run -d -p 8080:8080 -e ANTHROPIC_API_KEY=xxx mother-ai-os
```

## Volume Mounts

| Path | Purpose |
|------|---------|
| `/app/plugins` | Custom plugins |
| `/app/data` | Persistent data |
| `/app/.env` | Environment file |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Claude API key |
| `MOTHER_API_KEY` | No | auto | API authentication key |
| `MOTHER_HOST` | No | 0.0.0.0 | Bind address |
| `MOTHER_PORT` | No | 8080 | Server port |
| `MOTHER_LOG_LEVEL` | No | INFO | Logging level |

## Health Checks

The container exposes a health endpoint:

```bash
curl http://localhost:8080/health
```

Docker health check is configured automatically.

## Scaling with Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mother
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mother
  template:
    metadata:
      labels:
        app: mother
    spec:
      containers:
      - name: mother
        image: ghcr.io/mother-ai-os/mother:latest
        ports:
        - containerPort: 8080
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: mother-secrets
              key: anthropic-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
```
