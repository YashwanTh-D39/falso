# Architecture

Falso is a single-process application: a FastAPI server that serves a
single-page frontend and proxies LLM inference to a local Ollama process.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser                                 │
│   frontend/index.html  (single-page UI)                         │
│   - chat (streaming)  - conversations  - stats dashboard (1s)   │
│   - audio visualizer  - MediaPipe hand tracking (client-side)   │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP / SSE
┌──────────────────────────────▼──────────────────────────────────┐
│                      FastAPI (uvicorn)                          │
│                                                                │
│  SecurityMiddleware  →  CORSMiddleware                          │
│  (auth / origin / body limits / security headers)               │
│                                                                │
│  Routes:                                                        │
│   /api/v1/chat          BrainService (routing + LLM streaming)  │
│   /api/v1/conversations JSON files in chats/ (bounded executor) │
│   /api/v1/system/stats  SystemMonitor cache read (O(1))         │
│   /api/v1/tools/time    ToolManager → TimeTool                  │
│   / (SPA fallback)      frontend/index.html                     │
│                                                                │
│  Services:                                                      │
│   SystemMonitor   — background sampler (1 dedicated worker)     │
│   ToolRegistry    — class-level tool registry (import-time)     │
│   ConversationContext — per-process pending-action state        │
│                                                                │
│  Executors (bounded, dedicated):                                │
│   falso-monitor   (1 worker)  falso-file-tool (2)               │
│   falso-chats     (2 workers)                                   │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP
┌──────────────────────────────▼──────────────────────────────────┐
│                  Ollama (localhost:11434)                       │
│   POST /api/chat  — streamed chat completions                   │
└─────────────────────────────────────────────────────────────────┘
```

## Layers

| Layer | Location | Responsibility |
| --- | --- | --- |
| Middleware | `app/middleware/security.py` | Auth, origin validation, two-layer body limits, security headers. Never blocks the event loop. |
| Routes | `app/routes/` | Thin HTTP adapters — parse, validate, delegate. No business logic. |
| Services | `app/services/` | `BrainService` (chat routing), `SystemMonitor` (background metrics), `ConversationContext` (state). |
| Tools | `app/tools/` | `ToolRegistry` (class registry), `ToolManager` (execution + timing), tool implementations. |
| Config | `config/` | `Settings` (pydantic-settings, `.env`), logging setup, system prompt. |
| Frontend | `frontend/index.html` | Single-page UI, no build step, served with SPA fallback. |

## Chat request flow (`POST /api/v1/chat`)

`BrainService.chat()` is an async generator; the route wraps it in a
`StreamingResponse` (`text/event-stream`, newline-delimited JSON). One turn
is resolved in three phases:

### Phase 0 — Pending action

`ConversationContext` remembers the last tool call that requested
confirmation (5-minute TTL, `app/services/context.py`). When present, the
user's next message is checked first:

- **Affirmative** (`yes`, `y`, `sure`, `ok`, `do it`, `go ahead`, …) →
  re-execute the stored tool call with `confirmed=true`, clear pending, emit
  the formatted result.
- **Negative** (`no`, `nope`, `cancel`, `stop`, …) → clear pending, emit
  `"Cancelled."`.
- **Anything else** → pending stays alive; the message falls through to
  normal routing.

### Phase 1 — Tool routing

`ToolRegistry.list()` iterates registered tools; each `Tool.match_prompt()`
decides whether the prompt targets it. On a match:

1. Emit `tool_start` event.
2. `ToolManager.execute()` runs the tool (timing + error capture).
3. If the result requests confirmation (`confirmation_required`), the action
   is stored via `store_pending(...)` for Phase 0 of the next turn.
4. The result is formatted by `Tool.format_result()` and emitted as the final
   `done: true` line.

Intent parsing lives entirely in `FileTool.match_prompt()` (the biggest one)
and the generic `Tool.match_prompt` fallback (keyword match on name +
description minus stop words). Registration is import-time side effect:
modules are imported by `brain.py`/`routes/tools.py` and decorate themselves
with `@ToolRegistry.register`.

### Phase 2 — LLM fallback

No tool matched → stream from Ollama:

```
POST {OLLAMA_BASE_URL}/api/chat   {"model": OLLAMA_MODEL, "messages": [...], "stream": true}
```

`messages` = optional system prompt (`config/system_prompt.txt`, loaded once
at startup, missing file tolerated) + the user prompt. Every Ollama line is
re-emitted as `{"model", "response", "done"}`. Timeout: 300 s.

## Concurrency model

The event loop never does blocking work. All blocking I/O is confined to
**dedicated, bounded thread executors** — never the default pool, so one slow
operation cannot starve unrelated work:

| Executor | Workers | Used by |
| --- | --- | --- |
| `falso-monitor` | 1 | `SystemMonitor` sampling (psutil syscalls, `nvidia-smi` subprocess) |
| `falso-file-tool` | 2 | File tool operations (incl. long recursive `search` scans) |
| `falso-chats` | 2 | Conversation file reads/writes/replace/delete |

One-time exceptions: `SystemTool` runs a single ~100 ms `cpu_percent(0.1)`
warm-up via `asyncio.to_thread` on first use; afterwards CPU reads use the
non-blocking `cpu_percent(None)` delta.

## System monitor

`SystemMonitor` (singleton, started/stopped by the app lifespan) refreshes
every metric served by `/api/v1/system/stats`:

1. One task runs `loop.run_in_executor(falso-monitor, self._sample)` each
   `GPU_REFRESH_INTERVAL_SECONDS` (default 5 s).
2. `_sample()` reads CPU (warm-up then delta), RAM, disk, network counters
   (delta bytes/sec), temperatures, battery, and `nvidia-smi` (3 s timeout,
   `utilization.gpu,memory.used,memory.total,temperature.gpu`).
3. The snapshot is stored; `/stats` returns a `deepcopy` — an O(1) read with
   zero threads, safe for the frontend's 1 Hz polling.
4. Failure semantics: GPU probe failure keeps the last successful GPU values;
   unavailable sensors degrade per-field to `null`; before the first sample,
   zeros/`null`s are served.

Sampler state (`_net_last`, `_gpu_last`, `_cpu_warmed`) lives only in the
single worker thread, so no locking is needed.

## Data storage

| Data | Location | Notes |
| --- | --- | --- |
| Conversations | `chats/<id>.json` | Runtime-created, gitignored; atomic writes (temp file + `os.replace`, serialized by a write lock with retry for Windows sharing violations); listing tolerates files vanishing mid-scan; safe-id validation before any path use |
| Logs | stdout | `config/logging.py`; `docker-compose` maps `./logs` (empty — no file logging today) |
| System prompt | `config/system_prompt.txt` | Loaded once at startup; absence is tolerated |

## Non-goals / placeholders

`agents/`, `automation/`, `memory/`, `vision/`, `voice/`, `app/models/` are
empty placeholder packages for the roadmap (multi-agent, automation,
long-term memory, vision/OCR, voice). They do not run.
