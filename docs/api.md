# Falso API Reference

Interactive docs are available at `/docs` (Swagger UI) and `/openapi.json`
when the server is running. All API routes live under `/api/v1` and are
protected by the security middleware — see [security.md](security.md).

Base URL: `http://localhost:8000`

---

## Headers

| Header | Where | Value |
| --- | --- | --- |
| `Authorization: Bearer <token>` | All `/api/*` requests when `API_TOKEN` is set | Optional auth |
| `X-Falso-Token: <token>` | Alternative to the Authorization header | Optional auth |
| `Content-Type: application/json` | All POSTs with a body | Required |

If `API_TOKEN` is empty (local default), no auth is required.

Every response carries the security headers listed in
[security.md](security.md#response-headers).

## Error format

All non-streaming errors are JSON:

```json
{ "detail": "message" }
```

| Status | Meaning |
| --- | --- |
| `400` | Invalid request (e.g. empty prompt, malformed conversation id) |
| `401` | Missing or invalid API token |
| `403` | Cross-origin request from an origin not in `ALLOWED_ORIGINS` |
| `404` | Conversation not found — or any unknown `/api/*` path (never the SPA) |
| `413` | Request body exceeds `MAX_REQUEST_BYTES` (either layer) |
| `422` | Pydantic validation failure |
| `500` | Storage or internal error |

Unknown `/api/*` routes return a JSON `404` (not the single-page frontend),
so API clients never receive HTML by accident.

---

## GET /health

Liveness probe — does not require auth and is not under `/api`.

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "debug": true
}
```

---

## POST /api/v1/chat

Stream a chat turn. The response is `text/event-stream` containing
newline-delimited JSON objects (one per line, not SSE `data:` framed).

Request body:

```json
{
  "prompt": "what time is it?"
}
```

`prompt` must be 1–50,000 characters.

```bash
curl -N http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt":"what time is it?"}'
```

### Response stream

Each line is a JSON object. Event types:

**Token/response chunks** (LLM streaming):

```json
{ "model": "gpt-5", "response": "The current time is ", "done": false }
```

**Tool start notification** (before a tool executes):

```json
{ "type": "tool_start", "tool": "file", "action": "write", "detail": "notes.txt" }
```

**Final response** — a `done: true` line always ends the stream:

```json
{ "model": "gpt-5", "response": "The current time is 12:34:56.", "done": true }
```

For tool results the final `done` line contains the formatted tool result.

**Error** (e.g. provider unreachable, invalid key, or a connection failure
mid-stream):

```json
{ "error": "OpenAI connection failed: ..." }
```

The stream is resilient: malformed or non-object lines from the provider (or
a proxy) are skipped, and connect/read timeouts are surfaced as an `error`
line instead of a silently truncated stream. The model name in the stream
events reflects the configured `OPENAI_MODEL` / `OLLAMA_MODEL` (the
`done` event of a tool turn carries the default model).

### Chat routing

One chat request is resolved in three phases (see
[architecture.md](architecture.md#chat-request-flow)):

1. **Pending action** — if a previous tool call requested confirmation, an
   affirmative reply (`yes`, `sure`, `go ahead`, …) executes it; a negative
   reply (`no`, `cancel`, …) cancels it. Any other message falls through.
2. **Tool routing** — the prompt is matched against registered tools by
   keyword/pattern; a match streams a `tool_start` event, executes the tool,
   and ends with the formatted result. Deletions return
   `confirmation_required: true` instead of executing.
3. **LLM fallback** — no tool match: the prompt is streamed through the AI
   provider selected by `AI_PROVIDER` — OpenAI Responses API by default
   (`OPENAI_MODEL`), or Ollama (`OLLAMA_MODEL` at `OLLAMA_BASE_URL/api/chat`).
   System prompt → provider `instructions`; turns → `input`.

---

## Conversations

Conversations are stored as JSON files in `chats/` at the project root

> **Trailing slash required.** Collection routes (`GET`/`POST
> `/api/v1/conversations/`) expect the trailing slash. The no-slash form
> (`/api/v1/conversations`) is swallowed by the frontend catch-all and returns
> `404` (GET) or `405` (other methods) instead of the usual redirect.
(created at runtime, gitignored). Files are written atomically
(temp file + `os.replace`).

IDs must match `[A-Za-z0-9][A-Za-z0-9_-]{0,63}` (no dots or slashes — any
other value is rejected with `400`).

### GET /api/v1/conversations/

List saved conversations, newest first.

```json
[
  {
    "id": "abc123",
    "title": "New Chat",
    "createdAt": "2026-01-01T00:00:00Z",
    "updatedAt": "2026-01-01T00:00:00Z"
  }
]
```

### GET /api/v1/conversations/{conv_id}

Full conversation record, or `404` if missing.

```json
{
  "id": "abc123",
  "title": "New Chat",
  "messages": [
    { "role": "user", "text": "hello", "time": "12:00:00" },
    { "role": "assistant", "text": "hi!", "time": "12:00:01" }
  ],
  "createdAt": "2026-01-01T00:00:00Z",
  "updatedAt": "2026-01-01T00:00:00Z"
}
```

### POST /api/v1/conversations/

Create or overwrite a conversation. `id` is required (≤ 64 chars, safe
charset); `messages[].text` is capped at 200,000 chars.

```bash
curl -X POST http://localhost:8000/api/v1/conversations/ \
  -H "Content-Type: application/json" \
  -d '{"id":"abc123","title":"My chat","messages":[]}'
```

```json
{ "ok": true }
```

### DELETE /api/v1/conversations/{conv_id}

Delete a conversation file (idempotent — deleting a missing id is a `200`).

```json
{ "ok": true }
```

---

## Tools

### GET /api/v1/tools/time

Execute the time tool directly:

```json
{
  "time": "12:34:56",
  "date": "2026-08-04",
  "timezone": "India Standard Time"
}
```

This is a convenience endpoint — tools are normally invoked through `/chat`.

---

## System stats

### GET /api/v1/system/stats

Live system metrics. **All values come from a background cache** — the
request itself performs zero hardware probing (see
[architecture.md](architecture.md#system-monitor)). The frontend polls this
endpoint once per second; the cache refreshes every
`GPU_REFRESH_INTERVAL_SECONDS` (default 5 s).

```json
{
  "cpu":    { "percent": 8.0, "temp": 58.0 },
  "ram":    { "used": 8589934592, "total": 17179869184, "percent": 50.0 },
  "disk":   { "used": 214748364800, "total": 512110190592, "percent": 41.9 },
  "gpu":    { "util": 50.0, "vram_used": 1048576, "vram_total": 8589934592, "temp": 60.0 },
  "battery":{ "percent": 80.0, "charging": true },
  "network":{ "upload_bps": 1024.5, "download_bps": 2048.25 }
}
```

Field semantics:

| Field | Type | Notes |
| --- | --- | --- |
| `cpu.percent` | float | 1 decimal; 0.0 until the first background sample completes |
| `cpu.temp` / `gpu.temp` | float \| null | From OS temperature sensors; GPU temp prefers sensors over nvidia-smi; `null` = unavailable (no sensors / no GPU) |
| `ram.used` / `ram.total` / `ram.percent` | int / int / float | psutil `virtual_memory()` |
| `disk.used` / `disk.total` / `disk.percent` | int / int / float | `disk_usage("/")` |
| `gpu.util` / `vram_used` / `vram_total` | float \| null | From `nvidia-smi` (3 s timeout); `null` when no NVIDIA GPU or driver failure. A failed probe keeps the last successful GPU values (stale-on-failure, not cleared) |
| `battery.percent` / `battery.charging` | float \| null | `null` on desktop / unsupported platforms |
| `network.upload_bps` / `download_bps` | float | Bytes/sec since the previous sample; `0.0` on the first sample |
