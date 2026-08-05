# Falso

A production-grade AI assistant. Falso pairs a single-page dark-themed chat UI
with a pluggable AI provider layer: a FastAPI backend streams chat responses
from **OpenAI** by default (or your own **Ollama** instance) and executes local
tools (time, system info, file operations) from plain-language prompts.

**Version:** 0.1.0 — **Requires:** Python 3.11+ and an OpenAI API key
(or a local Ollama installation).

## Features

- **AI chat** — streaming responses from a pluggable provider (`openai` by
  default; `ollama` optional). Switch providers with the single
  `AI_PROVIDER` config value; the UI never changes. Streams are delivered to
  the browser as newline-delimited JSON (`text/event-stream`).
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
- An OpenAI API key (set `OPENAI_API_KEY` in `.env`). To use the optional
  local provider instead, run [Ollama](https://ollama.com) with the model
  pulled:

  ```bash
  ollama pull qwen2.5:3b   # only needed if AI_PROVIDER=ollama
  ```

Setup:

```bash
# 1. Create a virtual environment and install
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell)
# source .venv/bin/activate     # Linux/macOS

pip install -e ".[dev]"

# 2. Configure — add your OpenAI key
copy .env.example .env          # Windows
# cp .env.example .env          # Linux/macOS
# then edit .env: OPENAI_API_KEY=sk-...

# 3. Run
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. The API docs (OpenAPI) are at
<http://localhost:8000/docs>.

> **Switching providers** — set `AI_PROVIDER=openai` (default, cloud) or
> `AI_PROVIDER=ollama` (local). The UI and API stay identical; only the
> provider class changes. See [docs/architecture.md](docs/architecture.md#ai-provider-layer).

## Quick start (Docker)

```bash
docker compose up --build
```

Requires `.env` (see [docs/docker.md](docs/docker.md); the OpenAI key is read
from `.env` automatically via `env_file`).

## Configuration

All configuration comes from environment variables / `.env`
(copy `.env.example`, see [docs/deployment.md](docs/deployment.md#configuration)
for the full table):

| Variable | Default | Purpose |
| --- | --- | --- |
| `FASTAPI_HOST` / `FASTAPI_PORT` / `FASTAPI_DEBUG` | `0.0.0.0` / `8000` / `true` | Server binding |
| `LOG_LEVEL` | `INFO` | Logging level |
| `AI_PROVIDER` | `openai` | Chat provider: `openai` (cloud, default) or `ollama` (local). Future: `claude`, `deepseek` |
| `OPENAI_API_KEY` | *(empty)* | OpenAI key (server-side only, never exposed to the browser) |
| `OPENAI_MODEL` | `gpt-5` | OpenAI model name |
| `OPENAI_BASE_URL` | *(empty)* | Optional OpenAI-compatible gateway/proxy URL |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint (only when `AI_PROVIDER=ollama`) |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Ollama model name (only when `AI_PROVIDER=ollama`) |
| `SYSTEM_PROMPT_PATH` | `./config/system_prompt.txt` | Assistant system prompt (core identity for the default personality) |
| `ASSISTANT_PERSONALITY` | `default` | Personality used to build the system prompt: `default`, `technician`, `ultron`, `jarvis`, `minimal`, `friendly` |
| `USER_LANGUAGE` / `USER_VERBOSITY` | `English` / `concise` | User preferences folded into the generated system prompt |
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
  providers/              AI provider layer: base contract, OpenAI, Ollama, factory
  routes/                 brain (chat), conversations, system (stats), tools
  schemas/                Pydantic request/response models
  services/               brain.py (routing/LLM), context.py, system_monitor.py
  tools/                  base, registry, manager, time/system/file tools
config/                   settings (pydantic-settings), logging, system prompt
frontend/index.html       Single-page web UI
chats/                    Conversation JSON files (gitignored, created at runtime)
tests/                    pytest suite (121 tests)
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
