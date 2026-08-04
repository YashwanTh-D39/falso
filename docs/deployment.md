# Deployment Guide

Falso runs as a single process on a machine that also runs Ollama. This guide
covers local/manual deployment and containerized deployment
([docker.md](docker.md) for Docker specifics).

## Prerequisites

- **Python 3.11+** (tested on 3.14)
- **Ollama** with the model pulled (default `qwen2.5:3b`):

  ```bash
  ollama pull qwen2.5:3b
  ```

## 1. Install

```bash
git clone <repo> falso
cd falso

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

pip install -e ".[dev]"        # app + test/lint tooling
# or: pip install .            # runtime only
```

## 2. Configure

```bash
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/macOS
```

### Configuration

All variables are optional — the app runs out of the box with defaults.

| Variable | Default | Description |
| --- | --- | --- |
| `FASTAPI_HOST` | `0.0.0.0` | Bind address |
| `FASTAPI_PORT` | `8000` | Bind port |
| `FASTAPI_DEBUG` | `true` | Enables debug output in `/health` |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama HTTP endpoint |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Chat model (must be pulled in Ollama) |
| `SYSTEM_PROMPT_PATH` | `./config/system_prompt.txt` | System prompt file; missing file = no system prompt |
| `API_TOKEN` | *(empty)* | **Required for any non-local exposure.** Bearer token for all `/api/*` requests (constant-time comparison) |
| `ALLOWED_ORIGINS` | `["http://localhost:8000","http://127.0.0.1:8000"]` | JSON array; cross-origin browser requests (mutating methods) are only accepted from these origins |
| `MAX_REQUEST_BYTES` | `10000000` | Max `/api/*` request body, enforced on declared `Content-Length` and on the actual stream (chunked uploads included) |
| `GPU_REFRESH_INTERVAL_SECONDS` | `5` | Background stats refresh interval (> 0); `/stats` always serves the cache |
| `FILE_TOOL_WORKSPACE` | *(empty)* | Extra directory the file tool may access (absolute or relative path) |
| `MAX_FILE_READ_BYTES` | `1000000` | Reject file reads larger than this |
| `MAX_FILE_WRITE_BYTES` | `5000000` | Reject writes/appends above this total size |
| `MAX_SEARCH_RESULTS` | `500` | Cap on file search results |
| `MAX_LIST_ITEMS` | `5000` | Cap on directory listings |

Environment variables override `.env` (pydantic-settings, case-insensitive).
Note: the token variable is `API_TOKEN` — a `FALSO_API_TOKEN` variable is
**not** read.

## 3. Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- UI: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

For production use, run uvicorn with multiple workers *behind* a process
manager — but note **chat pending-state is per-process**
(`ConversationContext` is in-memory), so stick to a single worker, or run
`--workers 1` explicitly. A full example:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

## 4. Exposing beyond localhost

Any public/network exposure **must** set a token:

```bash
# .env
API_TOKEN=generate-a-long-random-value
ALLOWED_ORIGINS=["http://your-ui-origin"]
FASTAPI_DEBUG=false
```

1. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
2. Clients send `Authorization: Bearer <token>` or `X-Falso-Token: <token>`.
3. If you proxy (nginx/Caddy), put the API behind TLS and keep the proxy
   from caching `/api/v1/chat` (streaming).

The middleware also rejects cross-origin mutating requests from unknown
origins and caps request bodies at `MAX_REQUEST_BYTES` — see
[security.md](security.md) for the full threat model and known limits.

## 5. Update

```bash
git pull
pip install -e ".[dev]"      # re-resolve dependencies
python -m pytest -q          # run the suite before restarting
```

Runtime data (`chats/`) is gitignored and survives updates; back it up
alongside `.env`.

## Verified stack

- Python 3.14.6 (Windows) — 64 tests passing, ruff clean
- Windows PowerShell / Linux shell supported; the app is cross-platform,
  with platform-specific degradations (no temperature/battery sensors on
  some OSes → `null` in stats, no GPU → `null` GPU fields)
