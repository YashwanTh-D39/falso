# Phase D — Milestone Plan (V2 Roadmap with Review Gates)

**Date:** 2026-08-04
**Rule:** No milestone may advance to the next until every gate below passes. A failed gate rolls back to the previous git tag. Perfection, not speed.

## 1. Milestone template (mandatory contents)

Every milestone ships a single directory of evidence — `docs/cto/reviews/MXX.md` plus artifacts — covering all ten items:

| # | Item | Evidence required (committed to repo) |
|---|---|---|
| 1 | **Architecture** | Updated architecture doc section; module/port/event diagram deltas; no structural regression vs Phase C |
| 2 | **Implementation** | Code landed; `ruff check` + `tsc --noEmit` clean; diff review notes |
| 3 | **Tests** | `pytest -q` full pass + new tests for every new behavior; coverage delta recorded |
| 4 | **Security Review** | Security checklist sign-off (template §3); any finding = fix before tag |
| 5 | **Performance Review** | Benchmark run against `benchmarks/` (template §4); no regression vs previous milestone |
| 6 | **Documentation** | `docs/` updated (API, architecture, security, testing, troubleshooting); README if user-facing |
| 7 | **Benchmarks** | `benchmarks/MXX.json` — machine name, timestamps, numbers, delta vs M0 baseline |
| 8 | **Self Review** | Checklist §5 completed by implementer(s) — honest, including what did NOT go well |
| 9 | **CTO Review** | Checklist §6 — gate decision: PASS / PASS-WITH-CONDITIONS / FAIL |
| 10 | **Git Tag** | `v2.0-mXX` annotated tag with the review summary as the tag message |

**Gate protocol:** implement → self-review → performance/security evidence → CTO review → tag → **Phase E reassessment** → next milestone. Nothing is "done" until the tag exists and the next milestone's architecture work references it.

## 2. Milestones

### M0 — Hardened baseline (security-first)
**Goal:** eliminate every V1 defect from Phase B §4; establish the benchmark baseline; no new features.
- Fix `_search` sandbox escape (normalize pattern, reject `..`, verify each match inside base)
- Fix frontend XSS (escape tool/model before `innerHTML`); add frontend token header support
- `_last_filename` → per-conversation; copy ≠ rename; byte-accurate write limits; tool timeouts
- SSE/NDJSON: standardize framing (versioned SSE) on both sides
- Single AudioContext ownership + teardown; remove dead code (originalDraw, smoothHandRotation, camera_utils.js)
- **Benchmarks:** `benchmarks/M00.json` — chat TTFB, tool round-trip, stats latency, memory usage, boot time
- **Tag:** `v2.0-m0`

### M1 — Storage & session backbone
**Goal:** the data foundation for everything after.
- SQLite (WAL) for conversations/sessions; `migrate_v1_to_v2` script (validated import of `chats/*.json`)
- `SessionContext` per session (replaces process-global context); conversation history actually feeds the LLM context (V1 gap)
- In-process **event bus** (typed events, sync handlers, per-topic ordering, contract tests)
- **Tests:** storage CRUD + migration + concurrency (WAL busy handling); bus contract tests
- **Security:** SQLite permissions, safe session ids, audit of migration
- **Benchmarks:** save/load p50/p95 at 100/1k/10k conversations; migration runtime
- **Tag:** `v2.0-m1`

### M2 — Orchestrator v2 (LLM-first routing)
**Goal:** real function calling; deterministic fallback; adapter selection; latency budget.
- `LLMProvider` port: `OllamaProvider` (function calling from `Tool.parameters` schemas) + optional `OpenAICompatProvider` (cloud, keyring creds)
- `IntentRouter`: `llm` path default, `deterministic` (V1 regex engine, refactored + documented) as no-model/high-latency fallback
- `FeaturePolicy` config (local/cloud per feature); model switching events
- **Tests:** schema generation, tool loop (model asks→tool runs→result fed back), fallback parity, injection-guard on tool results
- **Benchmarks:** decision latency (3B local), first-token, multi-tool turn; vs M0
- **Tag:** `v2.0-m2`

### M3 — Voice core (the phone experience)
**Goal:** voice-first with sub-second offline loop; barge-in; wake word.
- WebSocket gateway (auth via token handshake, binary+text frames, heartbeat, max frame size, rate limits)
- Voice pipeline: `STTProvider` (sherpa-onnx streaming local; cloud fallback), `TTSProvider` (piper, streaming chunks, ≤180 ms first token), `WakeWordDetector` (OpenWakeWord), VAD
- `BargeController` (interrupt TTS ≤120 ms, tail retraction)
- **Tests:** adapter fakes; frame protocol round-trip; barge-in timing; disconnect/cleanup
- **Security:** mic/audio ephemeral buffers, WS auth tests, no audio in logs
- **Benchmarks:** STT first-token, full-utterance, TTS first-token, barge-in latency, WS overhead
- **Tag:** `v2.0-m3`

### M4 — Memory
**Goal:** zero-config semantic recall of everything.
- `MemoryClient` port + `ChromaMemoryStore` (local embeddings); episodic event log + semantic summaries + entity graph (SQLite)
- `MemoryConsolidator` (idle/nightly, idempotent, crash-safe, injected clock)
- Context assembly: Orchestrator injects retrieved memory into system prompt with scope rules
- **Tests:** retrieval relevance (fixed corpus), consolidation idempotency + crash resume, scope/ACL filtering, privacy (no cloud by default)
- **Benchmarks:** embed latency, retrieval p50/p95 at 10k entries, consolidator runtime
- **Tag:** `v2.0-m4`

### M5 — Trusted autonomy (tools + permissions + automation)
**Goal:** the permission model that makes autonomy safe.
- `PermissionGate` (never/ask/always, one-time/until-revoked, per-tool), `AuditLog` (append-only SQLite, triggers), UI surface (`/api/v2/permissions`, `/api/v2/audit`)
- New read-first tools: `contacts`, `calendar`, `notifications`, `network`, `phone` (V2 scope)
- `automation`: persisted triggers (`when X and cond → action`) on cron/events, scheduler with injected clock, audit trail
- **Tests:** permission matrix (each combination), audit immutability, automation dry-run + execution, timeout enforcement
- **Security:** audit immutability test, permission revocation mid-session, least-privilege adapters
- **Benchmarks:** gate decision overhead, audit write p95, automation trigger latency
- **Tag:** `v2.0-m5`

### M6 — Frontend v2 (the visible world-class)
**Goal:** Phase B imports + a frontend worth showing.
- TS + esbuild static bundle; modules: `tracker`, `scene`, `chat`, `audio`, `dashboard`, `panels`, `state`; `'use strict'`, no implicit globals
- **Orb v2** (Phase B I-2): Three.js scene, quality tiers, visibility pause, dispose()
- **HandTracker v2** (Phase B I-1): hysteresis, handedness map, teardown, zero console noise
- Chat: O(n) streaming render (incremental, not full re-render per token); SSE v2 parser; AbortController/cancel
- A11y (I-4): real controls, aria, focus, `prefers-reduced-motion`; PWA manifest + offline shell
- **Tests:** vitest for pure modules (stream parser, pinch math, gesture state, renderer); lifecycle fakes for orb
- **Security:** CSP `script-src 'self'` (inline removed), SRI if any CDN remains, XSS audit of remaining `innerHTML` (single audited markdown renderer)
- **Benchmarks:** bundle size (≤200 KB gz), orb FPS high/low tier, DOM writes/sec, memory over 30-min session
- **Tag:** `v2.0-m6`

### M7 — Vision, agents, and the V2 release
**Goal:** the complete V2.
- `vision`: OCR (tesseract local + model fallback), screen capture events, memory integration
- `agents`: `TaskAgent` (goal→plan→steps using tools+memory; multi-step e.g. "organize Downloads by type")
- End-to-end voice session benchmarks vs Phase C targets (Table: ≤500 ms offline turn, ≤900 ms cloud, ≤120 ms barge-in)
- Final reassessment (Phase E) → `v2.0.0` release tag + changelog
- **Tag:** `v2.0.0`

## 3. Security review checklist (per milestone, sign off in `MXX.md`)

- [ ] All `// TODO security` / `noqa: BLE001` instances reviewed and justified
- [ ] New inputs validated at boundary (path, id, frame, prompt sizes)
- [ ] No secrets in code/config; secrets in keyring; `.env.example` updated
- [ ] Auth enforced on every new endpoint/WS connection (incl. no-SPA-fallback-for-/api rule)
- [ ] Audit log updated for new tool surface
- [ ] Frontend: no unescaped interpolation; CSP updated with the milestone's needs
- [ ] Dependency additions reviewed (license, maintenance, supply-chain); SRI where CDN

## 4. Performance review protocol (per milestone)

1. Run `benchmarks/run.py` (a script committed at M0) — machine, commit, date recorded in JSON output
2. Compare every metric against the previous milestone JSON; any regression > 10% blocks the tag
3. New code paths get a benchmark in the same harness (latency, memory, throughput where relevant)
4. Report in `MXX.md` §Performance with the delta table

## 5. Self-review checklist (implementer, per milestone)

- [ ] I re-read the diff; every line has a purpose; no speculative code, no dead code
- [ ] Naming/types/ports match the architecture doc; no shortcut that bypasses a port
- [ ] Tests I wrote actually fail if the behavior is removed (mutation sanity on the critical ones)
- [ ] I ran lint + full test suite + benchmarks; numbers recorded
- [ ] I documented what went badly (honest section required)
- [ ] Rollback plan identified (which tag restores the prior state)

## 6. CTO review checklist (per milestone)

- [ ] Architecture delta is consistent with Phase C; no drift without a written amendment
- [ ] No technical debt introduced; anything knowingly deferred is listed with a date to fix
- [ ] Security checklist signed; HIGH/MEDIUM findings = mandatory fix before tag
- [ ] Performance deltas within budget; latency targets (Phase C §1) still projected-achievable
- [ ] Tests meaningful and fast (unit suite < 30 s); CI-viable
- [ ] Docs current; API docs reflect the real surface
- [ ] Benchmarks committed; evidence honest (no cherry-picked runs)
- [ ] Decision: **PASS / PASS-WITH-CONDITIONS (tag allowed, conditions tracked) / FAIL (rollback to previous tag)**

## 7. Rollback rule

Any FAIL → `git checkout <previous tag>` + written post-mortem in `docs/cto/reviews/` before retry. The previous tag is always a known-good, benchmarked state. This is why every milestone ends with a tag.
