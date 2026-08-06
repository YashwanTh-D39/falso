# Phase C — Falso Version 2: Architecture for a World-Class AI Phone Assistant

**Date:** 2026-08-04
**Target:** Exceed Gemini Live, Apple Intelligence, Samsung Galaxy AI, Microsoft Copilot — as a **local-first** assistant that is *more capable than cloud-locked assistants* because it runs on your machine: lower latency, total privacy, deeper device integration, and cloud as an optional boost, not a dependency.

**Success criteria (measured):**

| Metric | V2 Target | Reference |
|---|---|---|
| Voice turn latency (offline, local model) | ≤ 500 ms (STT→LLM→TTS first-token) | Gemini Live ~1–2 s (cloud) |
| Voice turn latency (cloud-assisted) | ≤ 900 ms | — |
| Barge-in | ≤ 120 ms response to interruption | Apple Intelligence: "coming" |
| Fully offline operation | All core loops; cloud = opt-in per feature | None of the four competitors are offline-capable |
| Memory recall | Zero-config semantic recall of every conversation | Galaxy AI: 0 (no memory); Copilot: session-only |
| On-device privacy | Zero user audio/text leaves the device by default | None of the four are local-only |
| Tool autonomy | User-granted, audited, revocable tool permissions | Copilot (no device control); Gemini Live (no local tools) |

---

## 1. Design principles

1. **Offline-first, cloud-assisted.** Every subsystem has a local path that works with zero network. Cloud is a *routing decision* the Orchestrator makes per turn (cost, latency, task complexity, user policy), never a hard dependency.
2. **Modular by domain, hexagonal internally.** Each domain (`voice`, `brain`, `memory`, `vision`, `tools`, `automation`, `agents`) is a package with ports (interfaces) and adapters (implementations). The core never imports an adapter directly — it depends on interfaces, injected at composition root. This is what makes the system testable, replaceable, and honest about offline/online switching.
3. **Async end-to-end.** One event loop (asyncio) for orchestration; blocking work only inside bounded executors owned by the module that needs them (existing Falso discipline, extended).
4. **Events over direct calls for cross-domain flow.** Domains communicate through an in-process event bus (`domain events`): `UserSpoke`, `IntentResolved`, `ToolApprovalRequested`, `MemoryWrite`, `ModelSwitched`. This decouples the pipeline (voice never imports brain; brain emits events the voice layer reacts to) and makes every transition testable and observable.
5. **Security by default.** Every tool call that touches state (files, apps, messages) requires a *permission grant*, revocable, with an audit log. Models/adapters run with least privilege. All persistent stores encrypted at rest with a local keyring.
6. **LLM is a tool-user, not a parser.** V1's regex-first intent routing is inverted: the Orchestrator gives the model structured tool schemas (real function calling) and the model decides; a strict offline **deterministic fallback** (the V1 regex engine, improved) handles no-model and high-latency cases. Two paths, same Tool API.
7. **Everything testable.** Dependency injection + interfaces everywhere; domain logic is 100% unit-testable without hardware/network; adapters are integration-tested against fakes and real hardware in CI-classified tiers.
8. **Observable.** OpenTelemetry traces per turn; structured logs; per-module health; a `/diagnostics` surface. An assistant you can debug is an assistant you can trust.
9. **One identity.** Sessions are the unit of context; memory is per-owner with ACLs; multi-owner support is a config, not an afterthought.

---

## 2. System overview

```
┌──────────────────────────────  PHONE / DEVICE  ──────────────────────────────┐
│                                                                              │
│  UI (PWA / static SPA, TS modules)                                           │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────────────┐          │
│  │ Orb (3D)   │ │ Chat/Thread│ │ Voice panel│ │ Permissions panel │          │
│  └────────────┘ └────────────┘ └────────────┘ └───────────────────┘          │
│          ▲            ▲              ▲                    ▲                   │
│          │            │              │                    │                   │
│          └────────────┴─── WebSocket (binary frames, auth, rate-limit) ──────┘│
│                                                                              │
│  FALSO CORE (FastAPI + asyncio, one process, bounded executors)              │
│                                                                              │
│  ┌─ API edge ──────────────────────────────────────────────────────────────┐ │
│  │ SecurityMiddleware (auth, origin, two-layer body limits, headers)      │ │
│  │ WS gateway (token auth, frames, heartbeat, per-connection limits)      │ │
│  └─▲───────────────────────────────────────────────────────────────────────┘ │
│     │                                                                        │
│  ┌──▼────── EVENT BUS (in-process, typed domain events, sync handlers) ─────┐│
│  │                                                                           ││
│  │ ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌───────────────────┐ ││
│  │ │ voice   │ │ brain    │ │ memory  │ │ vision   │ │ automation/agents │ ││
│  │ │(STT/TTS)│ │(orchestr)│ │ (store) │ │(ocr/screen)│ (scheduler, plans)│ ││
│  │ └─────────┘ └──────────┘ └─────────┘ └──────────┘ └───────────────────┘ ││
│  │ ┌───────────────────────────────────────────────────────────────────┐    ││
│  │ │ tools: time/system/file(+new: apps, contacts, comms, network)     │    ││
│  │ │ ToolManager → PermissionGate → AuditLog → executor                │    ││
│  │ └───────────────────────────────────────────────────────────────────┘    ││
│  └──────┬───────────────────────────────────────────────────────────────────┘│
│         │                                                                    │
│  ┌──────▼─────────────── LOCAL ADAPTERS ────────────────────────────────────┐│
│  │ Ollama (local models, function-calling)   │ ChromaDB/SQLite (memory)    ││
│  │ sherpa-onnx / whisper.cpp (STT)           │ piper / kokoro (TTS)        ││
│  │ OpenWakeWord (wake word)                  │ OS integration (phone API)  ││
│  └──────┬───────────────────────────────────────────────────────────────────┘│
│         │                     (cloud path only when granted + enabled)       │
│  ┌──────▼─────────────── CLOUD ADAPTERS (opt-in per user) ──────────────────┐│
│  │ cloud LLM (e.g. OpenAI-compatible)       │ cloud STT/TTS (fallback)     ││
│  │ sync service (encrypted device-to-device)│                               ││
│  └───────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
```

**Key decisions behind this shape:**
- **WebSocket is the primary channel** for voice and streaming (binary frames for audio, JSON for text, event types multiplexed on one connection). HTTP remains for CRUD and health. This is what Gemini Live does and why it feels live.
- **Single process, many modules.** Horizontal scale is *not* the v2 problem; correctness, latency, and modularity are. The existing bounded-executor discipline is retained. Storage moves to SQLite (WAL) — multi-worker-safe via WAL + busy_timeout, no network dependency, offline-first.
- **The event bus is synchronous in-process** (no message broker yet). Domain handlers register for events; ordering per-topic is guaranteed by asyncio task semantics. If/when multi-process is needed, the bus becomes an adapter behind the same interface (this is the seam that buys future scalability without present complexity).

---

## 3. Domain specifications

### 3.1 `voice` — the phone-voice core
Ports (interfaces): `STTProvider`, `TTSProvider`, `WakeWordDetector`, `AudioChunkSource`.
- **Pipeline (offline):** OpenWakeWord → sherpa-onnx/whisper.cpp streaming STT → events (`UserSpoke` with transcript + confidence + VAD segment) → Orchestrator → TTS (piper/kokoro) → streaming audio frames to WS → UI.
- **Barge-in:** audio sink continuously compares mic energy against a speech gate; on `UserSpoke` mid-TTS, the TTS stream is paused/cancelled (≤120 ms), the tail is retracted in UI, and the new turn begins. Implemented as a `BargeController` with its own executor — never blocks the bus.
- **Streaming TTS**: chunked synthesis; first-token target ≤ 180 ms offline.
- **Fallbacks:** cloud STT/TTS adapters registered second; selection via settings + `FeaturePolicy` (a config that decides local/cloud per feature, e.g. `voice.stt = local`, `voice.tts = cloud`).

### 3.2 `brain` — orchestrator
Ports: `LLMProvider` (local Ollama, cloud OpenAI-compatible), `ToolRegistry` (moved to interface), `MemoryClient`, `IntentRouter`.
- **Per-turn flow:** contextualize (memory + session history + device state) → decide path: `tool` (function calling) | `llm` | `fallback-deterministic` → emit tool events (existing protocol) → final response.
- **Function calling:** Ollama tool-calling mode with schemas generated from `Tool.parameters` (V1 already declares these — a schema generator makes this a migration, not a rewrite). The deterministic regex router remains as `IntentRouter.deterministic` (offline no-model path).
- **Session model:** persisted per-conversation; `ConversationContext` becomes `SessionContext` bound to a session id, stored (not process-global) — fixes the V1 cross-conversation leak properly.
- **Latency budget (offline):** bus dispatch ≤ 1 ms · context load ≤ 10 ms · tool decision ≤ 120 ms (local 3B) · first LLM token ≤ 300 ms.

### 3.3 `memory` — persistent, semantic, private
Ports: `VectorStore` (ChromaDB local), `KeyValueStore` (SQLite), `Embedder` (sentence-transformers local; cloud embedder optional).
- **Three stores:**
  1. *Episodic* — every conversation turn as an event-log entry, embedded, retrievable ("what did I ask last Tuesday?").
  2. *Semantic* — consolidated summaries + entity graph (people, files, projects, preferences) with confidence + source refs.
  3. *Procedural* — user-created automations/recipes.
- **Consolidation:** a background `MemoryConsolidator` (own executor) runs nightly/on-idle: clusters episodes, writes semantic summaries, prunes stale entries. It must be idempotent and resumable (crash-safe via SQLite transaction log).
- **Privacy:** embeddings are local by default; memory is encrypted at rest; memory API has `scope` (session/owner) and never returns entries the current session isn't authorized for.

### 3.4 `vision` — seeing the phone world
Ports: `ImageSource`, `OCREngine` (tesseract local, offload to model when better), `ScreenReader` (device API).
- V2 scope: screenshot/OCR ("what's on my screen?"), document OCR, optional local VLM for scene description. Vision results feed the memory event log and tool calls (e.g., "read this code").
- Async: capture → background OCR → result event; never blocks the conversation loop.

### 3.5 `tools` — the action surface (extends V1)
- Keep `Tool`, `ToolResult`, `ToolRegistry`, `ToolManager` contracts. Add:
  - **`PermissionGate`** — per-tool, per-scope grants: `never | ask | always` with one-time/until-revoked durations. Default: ask. Every decision is appended to `AuditLog`.
  - **`AuditLog`** — append-only SQLite table: `timestamp, session, tool, kwargs_hash, outcome, permission_decision, model_used`. UI-consumable (`/api/v2/audit`).
  - **New tools:** `contacts`, `messaging` (SMS), `calendar`, `apps` (launch/switch), `notifications`, `network` (status/connect), `phone` (call/voicemail) — each behind PermissionGate. First versions are read-only where possible.
  - **Timeout contract:** every tool declares `max_runtime_seconds`; the manager enforces it (fixes V1's unbounded search).
- **`automation`** — cron/event-triggered tool runs: `when <event> and <condition> → do <action>`, persisted, testable, audited.

### 3.6 `agents` — planned autonomy
- V2 baseline: single-agent orchestration is the `brain`. `agents` domain defines `Agent` interface (goal → plan → steps) for future multi-agent; shipping a working `TaskAgent` that can decompose multi-step requests ("organize my Downloads folder: archive by type, report result") using tools + memory. Multi-agent orchestration stays out of scope until TaskAgent is proven — no speculative machinery.

---

## 4. Data & storage

| Store | Tech | Why |
|---|---|---|
| Conversations / sessions | SQLite (WAL) | Migrates from JSON files; transactions; WAL = multi-worker safe; zero ops. Migration: import existing `chats/*.json` once. |
| Memory (episodic/semantic) | ChromaDB + SQLite | Vectors local; SQLite for graph/relations. |
| Audit log | SQLite (append-only table) | Same DB, separate table, triggers to prevent UPDATE. |
| Permissions | SQLite (keyring-encrypted) | `PermissionGate` reads; UI writes. |
| Config | pydantic-settings + `.env` (extended) | As today. |
| Frontend assets | built static bundle | As today, now compiled. |
| Secrets (tokens, cloud keys) | OS keyring (`keyring` lib) | Never in `.env` for secrets; `.env` holds non-secrets only. |

**Migration path (V1→V2):** a one-shot `migrate_v1_to_v2` script reads `chats/*.json` → SQLite, validates, reports. Old dir is archived, never deleted without user confirmation.

---

## 5. Security model (V2)

| Layer | Control |
|---|---|
| Transport | WS + HTTP only on localhost/HTTPS; token auth (existing middleware, extended to WS handshake); rate limits per connection; max frame size |
| Frontend | CSP upgraded (`script-src 'self'` post-bundling — inline removed), SRI on any CDN asset, `innerHTML` eliminated except a single audited markdown renderer |
| Tools | `PermissionGate` (never/ask/always) + audit + timeouts + sandbox (existing resolve-based rules, with the search fix) |
| At rest | SQLite via `sqlcipher` (key from OS keyring); no plaintext logs of prompts/audio; audio buffers ephemeral |
| LLM boundaries | Local Ollama by default; cloud providers only via explicit `FeaturePolicy` + keyring credentials; prompt-injection guard on tool results (tools never feed raw prompt text to the model without boundary markers) |
| Identity | Single local owner v2; multi-owner ACLs designed, not built |

---

## 6. Testability strategy

1. **Hexagonal purity:** domain modules depend on ports only. Unit tests inject fakes (`FakeSTT`, `FakeLLM`, `InMemoryStore`). No hardware/network in unit tests.
2. **Layered test tiers (CI):** `unit` (pure, fast, must pass always) → `integration` (real SQLite, fakes for model/hardware) → `e2e` (real Ollama if present, marked `slow`, runnable on demand).
3. **Event-bus tests:** every domain event has a spec: producer, consumer, payload schema, failure semantics. A `bus_contract_test` asserts handler registration matches specs.
4. **Determinism:** `MemoryConsolidator` and automation scheduler use injected clocks (monotonic, controllable).
5. **Frontend:** pure logic (stream parser, pinch math, gesture state machine) extracted to modules with unit tests (vitest); DOM kept thin. Orb visuals tested for lifecycle (no GPU in CI; dispose invariants via fakes).
6. **Perf tests:** latency budgets (§3.2) codified as benchmarks that fail the milestone on regression (Phase D gate).

---

## 7. Tech stack decision record

| Layer | Choice | Rejected alternatives |
|---|---|---|
| API | FastAPI (as is) | — |
| WS | `fastapi.WebSocket` + uvicorn | — |
| ORM/storage | `sqlite3` stdlib + WAL; `sqlcipher` optional build | SQLAlchemy (weight, no need) |
| Vector | `chromadb` local (already optional dep) | — |
| STT | `sherpa-onnx` (streaming, offline) | whisper.cpp (no streaming); cloud-only (privacy fail) |
| TTS | `piper` (offline, <180ms first token) | kokoro (better quality, heavier — swap-in adapter later) |
| Wake word | `OpenWakeWord` | Porcupine (license) |
| Embeddings | `sentence-transformers` local | — |
| Frontend | TS + esbuild static bundle, WebSocket client, Three.js (tiered), MediaPipe tasks-vision (local WASM) | Next/React (weight), Vite (ok but heavier than esbuild) |
| Test | pytest + pytest-asyncio + vitest | — |
| Observability | stdlib logging + OpenTelemetry (optional export) | — |
| Models | Ollama function-calling models (`gemma3:4b` default, configurable) | — |

---

## 8. What V2 deliberately does NOT build

- Multi-process/microservices (the bus interface is the seam; single-process wins latency and simplicity)
- Multi-owner ACLs (designed, deferred)
- Cloud sync across devices (adapter seam exists; no service to build in v2)
- Autonomous multi-agent swarms (TaskAgent first, evidence before scale)
- An app store / plugin marketplace

These are the *honest* exclusions that keep V2 shippable, testable, and debt-free — the same principle applied to the ULTRON imports.
