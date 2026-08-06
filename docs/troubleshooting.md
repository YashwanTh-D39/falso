# Troubleshooting Guide

Symptom → cause → fix. Logs go to stdout with the format
`timestamp | LEVEL | module:line — message`; set `LOG_LEVEL=DEBUG` for more
detail.

## Chat / LLM

### "OpenAI error: ..." or "OpenAI connection failed" in the chat stream

**Cause:** `OPENAI_API_KEY` is missing/invalid, the model name is wrong, or
the OpenAI API is unreachable.

**Fix:**

```bash
# .env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5
```

- **401** → wrong or revoked key / insufficient credit — regenerate at
  https://platform.openai.com/api-keys.
- **404 model not found** → `OPENAI_MODEL` is not an available model.
- **503 / retries exhausted** → transient overload; the SDK retries
  automatically with backoff; if it persists, wait and retry.
- **`OPENAI_BASE_URL` set to a gateway/proxy** → verify the endpoint
  serves the OpenAI Responses API.

### "Ollama error: ..." in the chat stream (only when `AI_PROVIDER=ollama`)

**Cause:** `OLLAMA_BASE_URL` is unreachable or the model is missing.

**Fix:**

```bash
ollama list                      # model present?
curl http://localhost:11434/api/tags
```

If it fails, Ollama is not running — start it (`ollama serve`). Pull the
model if missing: `ollama pull gemma3:4b`. In Docker, the base URL must
point at the host (`http://host.docker.internal:11434`) — see
[docker.md](docker.md#reaching-ollama-from-the-container).

### Chat hangs / no response

- Check the configured provider vars: `OPENAI_BASE_URL`/`OPENAI_MODEL` (wrong
  values error or hang until the 300 s timeout; wrong keys hang until the SDK
  auth error).
- Confirm the first request through the UI; watch server logs for the
  `Chat with model ...` line.
- On slow models, responses are streamed incrementally — the UI shows a
  typing indicator; a long first-token delay is normal, especially with local
  Ollama models.

### Tool never runs; LLM answers instead

The prompt must match a tool pattern. See the tools' `match_prompt` logic in
[architecture.md](architecture.md#chat-request-flow) and try exact phrasing
(e.g. `read notes.txt`, `list files`).

### "Cancelled." after saying yes to a delete

The pending action has a **5-minute TTL** (`app/services/context.py`). If the
confirmation is too late, the action expired and the message was treated as
an unrelated prompt — repeat the request.

## Auth / security

### 401 Unauthorized on every `/api/*` call

`API_TOKEN` is set but the client sends no (or a wrong) token.

**Fix:** send `Authorization: Bearer <token>` or `X-Falso-Token: <token>`.
The frontend is served same-origin so it needs no token.

### 403 "Origin not allowed" from a browser

The UI origin is not in `ALLOWED_ORIGINS`.

**Fix:** add the origin (e.g. `http://192.168.1.10:8000` or your reverse
proxy origin) as a JSON array value. Note that a **dotted/qualified origin
must match exactly**, and `ALLOWED_ORIGINS` is a JSON array:

```
ALLOWED_ORIGINS=["http://localhost:8000","http://192.168.1.10:8000"]
```

### 413 "Request body too large"

The request body exceeds `MAX_REQUEST_BYTES` (default 10 MB) — enforced both
on `Content-Length` and on the streamed body (chunked uploads included).
Raise the limit in `.env` only if you also raise the file-tool write cap.

### Token ignored (works without one)

If `FALSO_API_TOKEN` is set in `.env` it is **silently ignored** — the
variable is `API_TOKEN` (see [deployment.md](deployment.md#configuration)).

## System stats

### GPU fields are `null`

- No NVIDIA GPU / driver — expected; the dashboard renders N/A.
- `nvidia-smi` is missing or slow (> 3 s timeout).
- In Docker without NVIDIA drivers mounted.

### CPU percent is 0.0

Normal right after startup: the first background sample takes one interval
(`GPU_REFRESH_INTERVAL_SECONDS`, default 5 s) to complete; before that the
cache serves zeros.

### CPU/temp/battery are `null`

Platform without the relevant psutil sensors (e.g. `sensors_temperatures`
does not exist on Windows). Degradation to `null` is by design.

### Stats never change

- `GPU_REFRESH_INTERVAL_SECONDS` is the refresh rate — verify it's > 0
  (an invalid value fails startup).
- Check logs for `System stats sampler failed` (a probe exception is logged
  and the previous snapshot is kept).
- GPU values are intentionally kept from the **last successful** probe while
  probes fail — see [architecture.md](architecture.md#system-monitor).

## Conversations

### 400 "Invalid conversation id"

IDs must match `[A-Za-z0-9][A-Za-z0-9_-]{0,63}` — no dots, slashes, or
percent-encoded separators. Generate ids with `uuid4().hex`.

### 404 on GET /api/v1/conversations/{id}

The file is not in `chats/`. Note `chats/` is gitignored and (by default in
docker-compose) **not volume-mounted** — container data is lost on container
recreation unless you add `./chats:/app/chats` (see
[docker.md](docker.md#volumes)).

### Conversation save fails with 500 "Storage error"

The `chats/` directory is not writable. Check permissions/disk space; the
directory is auto-created at import time.

## File tool

### "Access denied" on a path

The path must resolve inside `Documents`, `Desktop`, `Downloads`, or
`FILE_TOOL_WORKSPACE`. Symlinks and `..` are resolved against the real path
before the check.

### "File too large to read / Content too large"

Limits are `MAX_FILE_READ_BYTES` (1 MB) and `MAX_FILE_WRITE_BYTES` (5 MB).

### Search returns "0 matches"

`pattern` is matched against paths with `**/<pattern>` globs under each
allowed base — `report` matches `report*` only if the pattern includes the
wildcard (e.g. `*.txt`, `report*`).

## Server / infra

### Port 8000 already in use

```bash
netstat -ano | findstr :8000     # Windows
```

Change `FASTAPI_PORT` in `.env` and restart.

### "No module named 'app'"

Run uvicorn from the project root (the directory containing `app/`), or
install the package (`pip install .`) so the module is importable.

### Docker: `Ollama error` from the container

The container cannot reach host Ollama on `localhost` — set
`OLLAMA_BASE_URL` per [docker.md](docker.md#reaching-ollama-from-the-container).

### Docker: frontend changes not visible

`frontend/` is copied at **build time**; rebuild with
`docker compose up --build --force-recreate`.

## Reporting a bug

Include: OS + Python version, `LOG_LEVEL=DEBUG` output around the failure,
the exact request/prompt, and the output of `python -m pytest -q` +
`python -m ruff check app config tests`.
