FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml .
COPY app/ ./app/
COPY config/ ./config/
COPY frontend/ ./frontend/
RUN pip install --no-cache-dir .

# Create non-root user for security
RUN groupadd --system falso && useradd --system --gid falso falso \
    && mkdir -p /app/chats /app/logs \
    && chown -R falso:falso /app/chats /app/logs

USER falso

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
