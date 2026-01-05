---
sidebar_position: 1
---

# Self-Hosted Deployment

Run Mother AI OS on your own infrastructure.

## System Requirements

- Python 3.11+
- 2GB RAM minimum
- Linux, macOS, or Windows

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install Mother AI OS
pip install mother-ai-os
```

## Configuration

Create `.env` file:

```bash
# Required
ANTHROPIC_API_KEY=your-claude-api-key

# Optional
MOTHER_HOST=0.0.0.0
MOTHER_PORT=8080
MOTHER_API_KEY=your-mother-api-key
MOTHER_LOG_LEVEL=INFO
```

## Running the Server

### Development

```bash
mother serve
```

### Production with Gunicorn

```bash
pip install gunicorn uvicorn

gunicorn mother.api.app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080
```

### Systemd Service

Create `/etc/systemd/system/mother.service`:

```ini
[Unit]
Description=Mother AI OS
After=network.target

[Service]
Type=simple
User=mother
WorkingDirectory=/opt/mother
Environment="PATH=/opt/mother/venv/bin"
EnvironmentFile=/opt/mother/.env
ExecStart=/opt/mother/venv/bin/gunicorn mother.api.app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable mother
sudo systemctl start mother
```

## Reverse Proxy (Nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name mother.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/mother.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mother.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support for streaming
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Security Checklist

- [ ] Use strong API keys
- [ ] Enable HTTPS
- [ ] Configure firewall
- [ ] Set up rate limiting
- [ ] Review plugin permissions
- [ ] Enable logging and monitoring
