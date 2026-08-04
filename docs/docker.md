# Docker Guide

## Images

The image (`Dockerfile`) is deliberately minimal:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
COPY app/ ./app/
COPY config/ ./config/
COPY frontend/ ./frontend/
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Key points:

- `app/`, `config/`, and `frontend/` are copied **before** `pip install .`:
  hatchling only auto-detects packages named after the project (`falso`), so
  `[tool.hatch.build.targets.wheel]` declares `packages = ["app", "config"]`
  explicitly and ships the frontend inside the wheel via `force-include`
  (the app resolves the frontend relative to the installed package).
- `pip install .` installs the app (module `app.main`) plus runtime deps
  (FastAPI, uvicorn, pydantic, httpx, psutil) from `pyproject.toml`.
- The single-page frontend is served from the installed package; `/app/config`
  provides the system prompt for the default CWD-relative path.
- No `backend/` directory exists anymore; everything lives at the repo root.
- Default command runs one worker on port 8000.

## docker-compose

`docker-compose.yml` wires the basics:

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
```

## Quick start

```bash
# 1. Configuration (see below — Ollama needs explicit wiring in containers)
copy .env.example .env        # Windows / adjust for your shell

# 2. Build and run
docker compose up --build

# 3. Open
# http://localhost:8000
```

## Reaching Ollama from the container

`OLLAMA_BASE_URL` defaults to `http://localhost:11434`, which inside a
container points at the container itself. Point it at the host's Ollama:

| Host platform | `OLLAMA_BASE_URL` |
| --- | --- |
| Docker Desktop (Windows/macOS) | `http://host.docker.internal:11434` |
| Linux (default bridge network) | `http://<host-ip>:11434` — or run compose with `network_mode: host` and keep `http://localhost:11434` |

```bash
# .env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Ollama by default listens on `127.0.0.1` only; for Linux bridge networking
you must also run it with `OLLAMA_HOST=0.0.0.0`.

## Volumes

| Mount | Purpose |
| --- | --- |
| `./logs:/app/logs` | Reserved for future file logging (the app currently logs to stdout) |
| `./data:/app/data` | Reserved for future data files |

Conversations are written to `chats/` **inside the container** (repo root
`/app/chats`) — they are not mounted in the default compose file. To persist
them, add a mount:

```yaml
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
      - ./chats:/app/chats
```

## Environment

The full variable set is the same as local deployment — see
[deployment.md](deployment.md#configuration). `.env` is read via
`env_file`. Container-specific notes:

- `FASTAPI_HOST` / `FASTAPI_PORT` are already covered by the `CMD`; only
  override via env if you change the command.
- Set `API_TOKEN` when exposing the port beyond localhost.
- `GPU_REFRESH_INTERVAL_SECONDS` works inside containers, but the
  `nvidia-smi` probe only returns data if the NVIDIA driver is available to
  the container; otherwise GPU fields are `null`.

## Rebuild after changes

```bash
docker compose up --build --force-recreate
```

The image runs `pip install .` at build time, so any change to
`pyproject.toml` requires a rebuild (`--build` handles this); the frontend is
copied in at build time too — rebuild to pick up `frontend/index.html`
changes.
