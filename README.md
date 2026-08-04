# Falso

A production-grade local AI assistant. Falso runs entirely on your machine: a
FastAPI backend serves a single-page dark-themed chat UI, talks to a local
Ollama model, and executes local tools (time, system info, file operations)
from plain-language prompts.

**Version:** 0.1.0 — **Requires:** Python 3.11+, Ollama

## Features

- **Local chat** — streaming responses from a local Ollama model (default
  `qwen2.5:3b`), streamed to the browser as newline-delimited JSON
  (`text/event-stream`).
- **Tool execution** — the assistant routes requests to built-in tools:
  - `time` — current local time, date, timezone.
  - `system` — CPU usage/model, RAM, disk, OS, hostname, battery.
  - `file` — read, write, append, mkdir, list, search, rename, delete,
    sandboxed to `Documents`, `Desktop`, `Downloads` and an optional
    configured workspace.
- **Natural-language intent matching** — prompts like *"create a file notes.txt
  with hello"* or *"delete report.md"* are parsed into tool calls; file
  deletions require a confirmation ("yes"/"no") before they run.
- **Conversation management** — conversations persist as JSON in `chats/` and
  can be saved, listed, and loaded from the UI.
- **Live system dashboard** — the UI polls `/api/v1/system/stats` once per
  second; all metrics (CPU, RAM, disk, GPU, network, temperatures, battery)
  are sampled in the background by a single worker thread, so monitoring costs
  the request path nothing.
- **Web UI extras** — microphone audio visualizer, optional camera-based hand
  tracking (MediaPipe, client-side), startup animation, keyboard shortcuts.
- **Security layer** — optional bearer token, origin allowlist, two-layer
  request body size enforcement (declared `Content-Length` and streamed/chunked
  bodies), and hardened response headers incl. a strict CSP. See
  [docs/security.md](docs/security.md).

Not yet implemented (planned): long-term memory, voice I/O, vision/OCR,
multi-agent orchestration, automation.

## Quick start (local)

Prerequisites:

- Python 3.11+
- [Ollama](https://ollama.com) running locally with the model pulled:

  ```bash
  ollama pull qwen2.5:3b
  ```

Setup:

```bash
# 1. Create a virtual environment and install
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell)
# source .venv/bin/activate     # Linux/macOS

pip install -e ".[dev]"

# 2. Configure (optional — defaults work for local use)
copy .env.example .env          # Windows
# cp .env.example .env          # Linux/macOS

# 3. Run
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. The API docs (OpenAPI) are at
<http://localhost:8000/docs>.

> On Windows, Ollama also exposes the model at the default `localhost:11434`
> which is what `OLLAMA_BASE_URL` points at. If you run the API in Docker,
> point it at `http://host.docker.internal:11434` — see [docs/docker.md](docs/docker.md).

## Quick start (Docker)

```bash
docker compose up --build
```

Requires `.env` (see [docs/docker.md](docs/docker.md) for the Ollama wiring).

## Configuration

All configuration comes from environment variables / `.env`
(copy `.env.example`, see [docs/deployment.md](docs/deployment.md#configuration)
for the full table):

| Variable | Default | Purpose |
| --- | --- | --- |
| `FASTAPI_HOST` / `FASTAPI_PORT` / `FASTAPI_DEBUG` | `0.0.0.0` / `8000` / `true` | Server binding |
| `LOG_LEVEL` | `INFO` | Logging level |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Model name |
| `SYSTEM_PROMPT_PATH` | `./config/system_prompt.txt` | Assistant system prompt |
| `API_TOKEN` | *(empty)* | Optional bearer token for `/api/*` |
| `ALLOWED_ORIGINS` | localhost origins | CORS + origin allowlist (JSON array) |
| `MAX_REQUEST_BYTES` | `10000000` | Max `/api/*` request body (both layers) |
| `GPU_REFRESH_INTERVAL_SECONDS` | `5` | Background stats refresh interval |
| `FILE_TOOL_WORKSPACE` | *(empty)* | Extra sandboxed directory for the file tool |
| `MAX_FILE_READ_BYTES` | `1000000` | Max bytes a file tool read returns |
| `MAX_FILE_WRITE_BYTES` | `5000000` | Max bytes a file tool write/append allows |
| `MAX_SEARCH_RESULTS` / `MAX_LIST_ITEMS` | `500` / `5000` | File tool result caps |

## Project layout

```
app/
  main.py                 FastAPI app, lifespan, middleware wiring, SPA serving
  middleware/security.py  Auth, origin checks, body limits, security headers
  routes/                 brain (chat), conversations, system (stats), tools
  schemas/                Pydantic request/response models
  services/               brain.py (routing/LLM), context.py, system_monitor.py
  tools/                  base, registry, manager, time/system/file tools
config/                   settings (pydantic-settings), logging, system prompt
frontend/index.html       Single-page web UI
chats/                    Conversation JSON files (gitignored, created at runtime)
tests/                    pytest suite (64 tests)
docs/                     This documentation set
```

## Development

```bash
python -m pytest -q            # run the full test suite
python -m ruff check app config tests   # lint
```

See [docs/testing.md](docs/testing.md) for details.

## Documentation

- [API reference](docs/api.md)
- [Architecture](docs/architecture.md)
- [Deployment guide](docs/deployment.md)
- [Docker guide](docs/docker.md)
- [Security guide](docs/security.md)
- [Testing guide](docs/testing.md)
- [Troubleshooting](docs/troubleshooting.md)
