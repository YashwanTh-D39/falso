# M1 — Conversation Engine: Implementation Roadmap (PR-by-PR) — v2

**Date:** 2026-08-04
**Status:** APPROVED — pre-implementation review passed (`reviews/M01-implementation-review.md`,
v2 redesign). Architecture: `m1-conversation-engine-design.md` + gate `reviews/M01.md`.
**Scope:** The only implementation authority for ordering, size, and acceptance.

---

## 1. Global rules (apply to EVERY PR)

1. **Compiles:** `python -m ruff check app config tests` clean; imports resolve; the import
   graph stays acyclic (domain → infrastructure → application → adapters).
2. **Tests:** full `python -m pytest -q` green — including the existing Phase 1 suite
   (76 tests) except where a PR explicitly and intentionally adapts them (noted per PR).
3. **Independently mergeable:** every PR lands on `main` in a working state. Behavioral
   changes ship behind `CONVERSATION_ENGINE` (defined in PR-01, default **off**, flipped in
   PR-25, removed in PR-26). Additive modules (pure logic, ports, providers) land
   unconsumed — the roadmap is their committed consumer.
4. **Rollback capability — revert policy:** reverts run in **reverse topological order**
   (a PR is only reverted while no merged successor depends on it). Until PR-26 the
   second-layer rollback is the flag (Phase 1 code still present); from PR-26 onward
   rollback is `git revert PR-26` / previous tag (Phase D §7). No PR performs destructive
   data operations (migrations forward-only; the import script never deletes the `chats/`
   archive).
5. **Unit tests:** new behavior covered in the same PR (test list per PR).
6. **Documentation:** every PR updates its slice of `docs/engine/*.md` (grows
   incrementally) or the user-facing docs; consolidation lands in PR-28.
7. **Self-review:** Phase D §5 checklist executed in the PR description (diff re-read,
   naming/ports match the design, mutation sanity on critical invariants, lint+tests+bench
   numbers, honest "what went badly", rollback tag identified).
8. **Size:** ≤ ~500 lines of modified production code per PR; exceptions flagged with
   justification (none expected).
9. **Ordering:** a PR starts the moment its "Depends on" set is merged; parallel where the
   DAG allows. **Known limitation (accepted):** the frontend has no JS unit-test
   infrastructure (vitest is M6 scope) — frontend PRs are verified by static-source
   security tests + API-level contract tests + a recorded manual e2e checklist.

**Approved structural refinement (no design change):** port implementations get homes not
listed in design-doc §5: `app/infrastructure/repositories/` (repo adapters),
`app/infrastructure/transactional/` (uow, lease, ledger, outbox). Domain code stays in
`app/conversations/` exactly as designed.

---

## 2. PR dependency graph (v2)

```
01 config (incl. CONVERSATION_ENGINE=off)
02 benchmarks + M00 baseline            (after 01)
03 domain foundation ─┬─► 04 budget ─► 05 assembler
                      └─► 06 event bus
07 sqlite adapter ─► 08 schema+migrations ─► 09 repos I ─► 10 repos II
11 UoW+lease (09) ─► 12 ledger+outbox (11)
13 cache (03) · 14 tokenizers (01,03) · 15 LLM provider (01,03)
16 session runtime (03,10) · 17 summarizer (03,05,10,15) · 18 maintenance (10,12)
19 orchestrator I (03,04,05,06,09,10,11,12,13,14,15,16,17)
20 orchestrator II (19)
21 chat adapter, flagged (19,20)
22 conv service + route, flagged dual-path (09,10)
23 migration script (08,09)
24 frontend session-aware — saveConv KEPT (21)
25 switchover: flag on + migration + maintenance + saveConv removal (17,21,22,23,24)
26 legacy removal: Phase 1 brain/context + off-paths + flag (25)
27 frontend pagination (22,25)
28 gate evidence + tag (02,26,27)
```

Parallel tracks: A domain (03–06) · B storage (07–12) · C providers (13–15) · D ops
(16–18, 23) · E client (24, 27).

---

## 3. The PRs

### PR-01 — Configuration foundation
1. **Goal:** every M1 setting (design §7 + M01 §2.6) with validation — including
   **`CONVERSATION_ENGINE` (default off)**, the single rollout flag for the milestone.
2. **Files modified:** `config/settings.py`, `.env.example`, `docs/deployment.md`
   (config table), `tests/test_settings.py` (new).
3. **Architecture impact:** none behavioral; all engine modules consume settings from here.
   Flag story established once (off here, on in PR-25, removed in PR-26).
4. **Risk level:** LOW.
5. **Test plan:** defaults; env parsing; validation failures; `.env.example` parity; flag
   default asserted off.
6. **Rollback plan:** revert; fields/flag unused.
7. **Acceptance criteria:** suite green; deployment.md matches settings exactly.
8. **Estimated time:** 0.5 day.

### PR-02 — Benchmark harness + M00 baseline
1. **Goal:** `benchmarks/run.py` with machine/commit/date metadata; capture the **M00
   baseline on the true Phase 1 state** (before any behavior-changing PR merges).
2. **Files modified:** `benchmarks/run.py`, `benchmarks/M00.json`, `docs/engine/ops.md`
   (§3), small harness smoke test.
3. **Architecture impact:** the Phase D §4 measurement gate; baseline integrity requires
   this position (review F4).
4. **Risk level:** LOW.
5. **Test plan:** harness smoke (deterministic on tiny corpus); JSON schema validation;
   M00 recorded with metadata.
6. **Rollback plan:** revert; dev tool only.
7. **Acceptance criteria:** M00.json committed; harness runnable.
8. **Estimated time:** 1 day.

### PR-03 — Domain foundation: entities, errors, events, ports
1. **Goal:** the domain layer skeleton per design §6 + M01 additions: entities
   (`Message`, `Session`, `ConversationSummary`, `ToolExecution`, `OutboxRow`,
   `MemoryWritePayload`, views); typed error hierarchy; all domain events; all Protocol
   ports (repository, session state, UoW, lease, ledger, outbox, tokenizer, summarizer,
   LLM provider with `priority`, bus, memory gateway, clock, id generator).
2. **Files modified:** `app/conversations/{__init__,entities,errors,events,ports}.py`
   (new); `tests/test_engine/{test_entities,test_errors,test_events,test_ports}.py`
   (new); `docs/engine/domain.md` (new).
3. **Architecture impact:** the hexagonal boundary; nothing consumes it yet.
4. **Risk level:** LOW.
5. **Test plan:** entity invariants; event payload specs (seed of the bus contract suite);
   error hierarchy; ports Protocol-checked against design §6 field-for-field.
6. **Rollback plan:** revert; no consumers.
7. **Acceptance criteria:** suite green; ports match design §6 (checklist item).
8. **Estimated time:** 1 day.

### PR-04 — TokenBudget + BudgetSplit (pure)
1. **Goal:** budget math: split window into system/summary/history/response-reserve;
   reserve = max(response, ratio·window); per-model override hook.
2. **Files modified:** `app/conversations/budget.py` (new); `tests/test_engine/
   test_budget.py` (new); `docs/engine/context.md` (§1).
3. **Architecture impact:** pure domain; feeds the assembler.
4. **Risk level:** LOW.
5. **Test plan:** split correctness; edge cases (window ≤ reserve, zero system, tiny
   window); per-model overrides; property: parts sum ≤ window.
6. **Rollback plan:** revert; unconsumed.
7. **Acceptance criteria:** suite green; property test in place.
8. **Estimated time:** 0.5 day.

### PR-05 — ContextAssembler (pure)
1. **Goal:** assembly algorithm per design §9.1 + M01 amendments: ordered selection
   (newest-first selection, oldest-first emission), summary injection inside markers,
   **atomic tool-pair units**, digest caps with `[truncated]`, `interrupted`/`superseded`
   exclusion, `min_verbatim_tail` floor, compression triggers, extended-summarization
   trigger path, `AssemblyReport`. Pure: no I/O.
2. **Files modified:** `app/conversations/assembler.py` (new); `tests/test_engine/
   test_assembler.py` (new, design §17 suite); `docs/engine/context.md` (§2–3).
3. **Architecture impact:** the correctness-critical pure core (M01 A21/A22).
4. **Risk level:** MEDIUM.
5. **Test plan:** design §17 assembler suite: token math; truncation order; summary
   injection; pair both-or-neither; `[truncated]` preservation; floor preservation;
   extended-summarization trigger; property: output ≤ budget; chronological order.
6. **Rollback plan:** revert; unconsumed.
7. **Acceptance criteria:** suite green; mutation sanity on pair logic + floor (removing a
   guard fails a test).
8. **Estimated time:** 1.5 days.

### PR-06 — InProcessEventBus + event contracts
1. **Goal:** typed in-process sync bus: subscribe/publish, handler failure isolation,
   wall-time guard (< 1 ms contract hook); contract test module for every domain event.
2. **Files modified:** `app/infrastructure/providers/event_bus.py` (new); `tests/
   test_engine/test_event_bus.py` (new); `docs/engine/domain.md` (bus section).
3. **Architecture impact:** the Phase C bus seam; outbox (PR-12) uses it.
4. **Risk level:** LOW.
5. **Test plan:** per-topic order; handler exception isolation; unsubscribe; wall-time
   benchmark; event contract tests.
6. **Rollback plan:** revert; unconsumed.
7. **Acceptance criteria:** suite green; contract tests fail if an event lacks a spec.
8. **Estimated time:** 0.5 day.

### PR-07 — SQLiteDatabase adapter
1. **Goal:** per-shard DB files (`data/db/<shard_id>/falso.db`, `shard_id = hash(owner) %
   shard_count`), thread-local connections in the `falso-db` executor (1 writer + N readers
   per shard), connection factory pragmas (WAL, foreign_keys, busy_timeout, synchronous),
   `SQLITE_BUSY` retry (3× backoff + jitter), `quick_check` helper, executor-based async
   API.
2. **Files modified:** `app/infrastructure/db/sqlite.py` (new); `tests/test_infrastructure/
   test_sqlite.py` (new); `docs/engine/storage.md` (new, §1).
3. **Architecture impact:** the storage foundation; sharding contained here (M01 A14).
4. **Risk level:** MEDIUM.
5. **Test plan:** pragma conformance per pooled connection; shard path derivation
   (stability, distribution); thread-local safety under concurrency; busy → retry →
   success and exhausted → error; WAL on; quick_check; writer/reader concurrency smoke.
6. **Rollback plan:** revert; unconsumed.
7. **Acceptance criteria:** suite green; no sleeps/races in concurrency tests (injected
   clock).
8. **Estimated time:** 2 days.

### PR-08 — Engine schema + embedded migration runner
1. **Goal:** versioned migration runner (transactional, idempotent, startup-applied) +
   schema v1: schema_versions, owners, sessions, messages, session_state,
   conversation_summaries, turn_dedup, session_turn_lease, tool_executions, event_outbox,
   messages_archive + indexes (design §7 + M01 §2.2).
2. **Files modified:** `app/infrastructure/db/migrations.py`,
   `app/infrastructure/db/migrations/0001_engine_schema.sql` (new); `tests/
   test_infrastructure/test_migrations.py` (new); `docs/engine/storage.md` (§2).
3. **Architecture impact:** the schema contract; all repositories depend on it.
4. **Risk level:** MEDIUM.
5. **Test plan:** fresh → v1; re-run no-op; version bookkeeping; FK/pragma presence;
   CHECK constraints; archive-table parity with messages.
6. **Rollback plan:** forward-only; revert leaves unused tables.
7. **Acceptance criteria:** suite green; `0001` matches design §7 (checklist vs M01 §2.2).
8. **Estimated time:** 1.5 days.

### PR-09 — Repository adapters I: ConversationRepository
1. **Goal:** SQLite implementation of `ConversationRepository`: session CRUD, message
   append/status, last_messages, messages_after, paginated_messages, archive_messages,
   summary read/append; owner predicate on every query; parameterized SQL only. In-memory
   fakes in `app/conversations/fakes.py` for the contract suite.
2. **Files modified:** `app/infrastructure/repositories/conversations.py` (new);
   `app/conversations/fakes.py` (new); `tests/test_infrastructure/test_repositories.py`
   (new, contract suite); `docs/engine/storage.md` (§3).
3. **Architecture impact:** first port implementation; contract-suite pattern established.
4. **Risk level:** MEDIUM.
5. **Test plan:** contract suite on **both** adapters: CRUD round trip; owner scoping
   (cross-owner → empty); seq uniqueness under concurrency; pagination; archive round-trip;
   summary watermark reads.
6. **Rollback plan:** revert; unconsumed by routes.
7. **Acceptance criteria:** suite green both adapters; mutation sanity on the owner
   predicate.
8. **Estimated time:** 1 day.

### PR-10 — Repository adapters II: SessionStateRepository
1. **Goal:** SQLite + fake `SessionStateRepository` with the engine key whitelist
   (`pending_action`, `last_filename`); unknown keys rejected; JSON round-trip.
2. **Files modified:** `app/infrastructure/repositories/session_state.py` (new); tests;
   `docs/engine/storage.md` (§3).
3. **Architecture impact:** completes the repository layer.
4. **Risk level:** LOW.
5. **Test plan:** whitelist enforcement; JSON round-trip; delete; scoping.
6. **Rollback plan:** revert.
7. **Acceptance criteria:** suite green.
8. **Estimated time:** 0.5 day.

### PR-11 — UnitOfWork + TurnLeaseManager
1. **Goal:** transactional UoW (BEGIN IMMEDIATE, commit/rollback, repos + transactional
   services bound per shard) and the DB turn lease: acquire (PK conflict → None unless
   expired → fenced takeover), renew, release; worker_id token.
2. **Files modified:** `app/infrastructure/transactional/{uow,lease}.py` (new); `tests/
   test_infrastructure/{test_uow,test_lease}.py` (new); `docs/engine/recovery.md` (new, §1).
3. **Architecture impact:** crash-atomicity + cross-worker exclusion (M01 A1/A2).
4. **Risk level:** MEDIUM.
5. **Test plan:** UoW atomicity/rollback/re-entrancy guard; lease acquire, conflict → None,
   expiry takeover fenced, renew, release idempotent, multi-worker simulation.
6. **Rollback plan:** revert; unconsumed.
7. **Acceptance criteria:** suite green on real SQLite.
8. **Estimated time:** 1 day.

### PR-12 — ToolLedger + Outbox + MemoryGatewayNoop
1. **Goal:** tool execution ledger (record/by_turn, unique (turn_id, seq)); outbox
   (enqueue-in-UoW, claim_batch, ack, unacked re-claim); no-op memory gateway.
2. **Files modified:** `app/infrastructure/transactional/{ledger,outbox}.py`,
   `app/infrastructure/providers/memory.py` (new); tests; `docs/engine/recovery.md` (§2).
3. **Architecture impact:** exactly-once tool effects (A11) + durable fan-out (A4).
4. **Risk level:** LOW-MEDIUM.
5. **Test plan:** ledger uniqueness/replay ordering; outbox enqueue atomic with UoW
   (rollback → no row); claim/ack; crash-resume re-claim; owner tagging.
6. **Rollback plan:** revert.
7. **Acceptance criteria:** suite green.
8. **Estimated time:** 1 day.

### PR-13 — HistoryCache
1. **Goal:** generation-keyed per-session cache: entry cap, TTL (M01 A36), miss-on-stale,
   memory budget, never-trusted.
2. **Files modified:** `app/infrastructure/cache/history_cache.py` (new); tests;
   `docs/engine/context.md` (§4).
3. **Architecture impact:** context load within the 10 ms budget.
4. **Risk level:** LOW.
5. **Test plan:** generation mismatch → miss; TTL → miss; entry cap; budget guard;
   concurrent get/set.
6. **Rollback plan:** revert.
7. **Acceptance criteria:** suite green.
8. **Estimated time:** 0.5 day.

### PR-14 — Tokenizer implementations
1. **Goal:** `HeuristicTokenizer` (chars/4 with bounds) and `OllamaTokenizer`
   (`/api/tokenize`, timeout, fallback on failure); per-message cache keyed by
   (text-hash, model); `tokenizer_mode` selection.
2. **Files modified:** `app/infrastructure/providers/tokenizer.py` (new); tests;
   `docs/engine/context.md` (§5).
3. **Architecture impact:** token accuracy + availability (D10).
4. **Risk level:** LOW.
5. **Test plan:** heuristic bounds; ollama path with FakeClient; down → fallback; cache
   hits/misses; model-keyed invalidation.
6. **Rollback plan:** revert.
7. **Acceptance criteria:** suite green; no network in tests.
8. **Estimated time:** 0.5 day.

### PR-15 — LLMProvider: Ollama implementation (bounded + priority)
1. **Goal:** `OllamaLLMProvider.stream_chat/complete` with per-model concurrency bound,
   queue depth → `LLMQueueFullError`, priority (turns 0 > summarization 1), timeouts,
   stream chunk passthrough, malformed-line tolerance (Phase 1 parity).
2. **Files modified:** `app/infrastructure/providers/llm.py` (new); tests; `docs/engine/
   wire-contract.md` (new, §1 error codes).
3. **Architecture impact:** the M2 seam; backpressure contract (M01 A18/D22).
4. **Risk level:** MEDIUM.
5. **Test plan:** fake-Ollama streaming (chunks, done, 500, malformed lines, connect
   error, timeout); concurrency bound observed; queue full → typed error; priority
   ordering; cancellation closes upstream.
6. **Rollback plan:** revert.
7. **Acceptance criteria:** suite green; 429 route mapping tested in PR-21.
8. **Estimated time:** 1.5 days.

### PR-16 — SessionRuntimeRegistry (+ pending-action semantics)
1. **Goal:** per-session runtime: pending action with `execution_ref` (A11) and TTL,
   `last_filename`; rehydration from `session_state`; in-use refcounting (never evict an
   active turn, A3); LRU among idle; memory budget.
2. **Files modified:** `app/conversations/session_runtime.py` (new); tests; `docs/engine/
   context.md` (§6).
3. **Architecture impact:** kills the Phase 1 cross-conversation leak by construction.
4. **Risk level:** MEDIUM.
5. **Test plan:** per-session isolation; TTL; execution_ref restore; eviction never touches
   in-use; rehydration.
6. **Rollback plan:** revert; unconsumed by routes until PR-21.
7. **Acceptance criteria:** suite green; mutation sanity: removing isolation fails a test.
8. **Estimated time:** 1 day.

### PR-17 — Summarizer (queue + workers + triggers)
1. **Goal:** background summarization: trigger evaluation (message count, dropped-message
   count, extended-summarization), watermark idempotency, tool-result exclusion,
   keep-window, saturation skip (A18), failure backoff, summary chain (A22); configurable
   workers with per-session ordering.
2. **Files modified:** `app/conversations/summarizer.py` (new); tests; `docs/engine/
   context.md` (§7).
3. **Architecture impact:** the compression engine; consumes the LLM provider at priority 1.
4. **Risk level:** MEDIUM.
5. **Test plan:** design §17 summarizer suite: trigger math; watermark re-run no-op; chain
   fuzz (no gaps/duplicates); tool exclusion; failure → backoff → verbatim; saturation →
   skip; injected clock.
6. **Rollback plan:** revert; inactive until the orchestrator triggers it.
7. **Acceptance criteria:** suite green; chain property test included.
8. **Estimated time:** 1.5 days.

### PR-18 — MaintenanceService
1. **Goal:** scheduled job (injected clock): dedup/lease purge, WAL checkpoint + `PRAGMA
   optimize` per shard, archival compaction (`archive_after_summaries`), outbox
   dispatch/ack; never on the request path; idempotent, crash-safe.
2. **Files modified:** `app/conversations/maintenance.py` (new); tests; `docs/engine/
   ops.md` (new).
3. **Architecture impact:** long-run health (M01 A6/A16/A35).
4. **Risk level:** LOW-MEDIUM.
5. **Test plan:** purge correctness; compaction moves exactly folded-and-old rows; outbox
   dispatch/ack/crash-resume; checkpoint call; idempotency; no request-path interference.
6. **Rollback plan:** revert; not scheduled until PR-25.
7. **Acceptance criteria:** suite green.
8. **Estimated time:** 1 day.

### PR-19 — TurnOrchestrator I: happy path
1. **Goal:** turn protocol happy path (design §3 + M01 §2.1 minus recovery): session
   create/upsert, dedup INSERT-first (winner/loser), lease acquire, user message persist
   (`processing`) + atomic generation bump, assembly, deterministic routing (Phase 1 logic
   adapted to session runtime), tool execution + ledger + capped digest rows, LLM stream
   at priority 0, terminal persistence (`complete`), outbox TurnCompleted, 409 mapping,
   terminal-line invariant. **No retry/cancel/crash semantics (PR-20).**
2. **Files modified:** `app/conversations/orchestrator.py` (new, ~350–450 lines);
   `tests/test_engine/test_orchestrator.py` (new); `docs/engine/wire-contract.md` (§2).
3. **Architecture impact:** the engine core; first consumer of every port.
4. **Risk level:** HIGH (behavioral core).
5. **Test plan:** happy multi-turn (assembled messages reach the model — spy assert); tool
   turn with ledger + digest; 409 on busy session; concurrent identical requests → one
   winner; stream passthrough; terminal-line invariant; generation bump.
6. **Rollback plan:** revert; flag off by default → zero production exposure.
7. **Acceptance criteria:** suite green; recovery semantics explicitly out of scope here.
8. **Estimated time:** 2 days.

### PR-20 — TurnOrchestrator II: recovery & conflict semantics
1. **Goal:** complete the turn protocol per M01 A10/A11/A19/A29: retry = **reuse** of the
   user-message row (prompt mismatch → 409), ledger replay for executed steps, cancel
   order (persist → commit → aclose → release), interrupted/superseded marking, lease
   heartbeat, `LLMQueueFullError` → 429, provider-unavailable → typed error.
2. **Files modified:** `app/conversations/orchestrator.py` (same file, additive +~150
   lines); tests; `docs/engine/recovery.md` (§3).
3. **Architecture impact:** crash- and retry-safety; exactly-once tool effects.
4. **Risk level:** HIGH.
5. **Test plan:** retry reuses row (no second INSERT); ledger replay (spy: no second tool
   execution); prompt-mismatch 409; disconnect cancel order (lease released after commit);
   crash-mid-turn → interrupted → retry; heartbeat.
6. **Rollback plan:** revert; flag off.
7. **Acceptance criteria:** suite green; M01 gate conditions A10/A11 demonstrated.
8. **Estimated time:** 2 days.

### PR-21 — ChatAdapter (session-aware chat, flagged)
1. **Goal:** `POST /api/v1/chat` serves the engine when `CONVERSATION_ENGINE=on` (default
   off): `conversation_id`/`client_turn_id`/`turn_id` fields, error-code lines, keepalive,
   404/409/429/503 mapping (incl. the PR-15 429 test), streaming connection budget; Phase
   1 path byte-identical when off.
2. **Files modified:** `app/routes/brain.py` (+ adapter module), `tests/test_backend/
   test_brain.py` (flag-off parity retained; flag-on suite added), `docs/api.md` (+),
   `docs/engine/wire-contract.md` (§3).
3. **Architecture impact:** first (opt-in) production exposure of the engine.
4. **Risk level:** MEDIUM-HIGH (live surface, opt-in).
5. **Test plan:** flag-off: existing suite unchanged; flag-on: stream shape, error-code
   mapping table, keepalive, connection budget 503, 429 path.
6. **Rollback plan:** flag off (default); revert as second layer.
7. **Acceptance criteria:** both flag paths fully tested; wire contract v1+ documented.
8. **Estimated time:** 1 day.

### PR-22 — ConversationService + conversations route (flagged dual-path)
1. **Goal:** CRUD/list/get/delete over repositories with **unchanged wire shape** when the
   flag is on; **exact Phase 1 file-based behavior when off** (design §16.1 side-by-side);
   pagination params (`before_seq`/`limit`, archive reads) on the flag-on path only.
2. **Files modified:** `app/conversations/service.py` (new), `app/routes/conversations.py`
   (dual-path), `tests/test_conversations.py` (both paths; existing tests stay valid as
   the flag-off suite), `docs/api.md`.
3. **Architecture impact:** persistence authority moves to the engine DB — but only behind
   the flag; flag-off rollback stays complete (review F2).
4. **Risk level:** MEDIUM.
5. **Test plan:** flag-off: existing file-based CRUD suite (regression); flag-on:
   repository-backed round trip, pagination, owner scoping, archive reads; no file I/O in
   the flag-on path.
6. **Rollback plan:** flag off; revert.
7. **Acceptance criteria:** suite green; flag-off path proven identical by tests.
8. **Estimated time:** 1 day.

### PR-23 — Migration script (v1 JSON → engine DB)
1. **Goal:** `python -m app.infrastructure.db.migrate_v1_to_v2 [--dry-run|--apply]`:
   validate every `chats/*.json`, map to sessions/messages (role map, seq order,
   timestamps preserved), idempotent, shard-aware, archive `chats/` (never delete),
   human-readable report.
2. **Files modified:** `app/infrastructure/db/migrate_v1_to_v2.py` (new); `tests/
   test_migration/` (fixtures + tests); `docs/deployment.md` (migration section),
   `docs/engine/ops.md` (§2).
3. **Architecture impact:** data continuity; ops tool, no runtime surface.
4. **Risk level:** MEDIUM (data movement; reversible by design).
5. **Test plan:** fixtures (valid/empty/corrupt/oversized/duplicate ids); dry-run writes
   nothing (asserted); apply idempotency; role/order/timestamp preservation; archive
   behavior; `shard_count=2` routing.
6. **Rollback plan:** never deletes; `chats_archived_*` restores state; revert commit.
7. **Acceptance criteria:** suite green.
8. **Estimated time:** 1.5 days.

### PR-24 — Frontend: session-aware chat (**saveConv kept**)
1. **Goal:** chat sends `conversation_id` + `client_turn_id`; renders new done-line fields
   and error codes; **`saveConv` self-persistence KEPT** — harmless idempotent upsert on
   the flag-on path, essential on the flag-off path (review F1). Removed only in PR-25.
2. **Files modified:** `frontend/index.html`, `tests/test_security.py` (static frontend
   tests updated if sink patterns change), README (feature note).
3. **Architecture impact:** none server-side; client compatible with both flag states by
   design.
4. **Risk level:** MEDIUM (user-facing).
5. **Test plan:** static-source security tests; API-level contract tests; recorded manual
   e2e checklist (create/continue/retry) on both flag states; existing suite green.
6. **Rollback plan:** revert; server stays backward-compatible.
7. **Acceptance criteria:** suite green; e2e checklist executed and recorded; no persistence
   path regression on flag-off (double-write test at API level).
8. **Estimated time:** 1 day.

### PR-25 — Switchover (flag on + migration + saveConv removal)
1. **Goal:** `CONVERSATION_ENGINE` defaults **on**; migration run as part of rollout
   (ops step, recorded); maintenance job scheduled in the lifespan (needs PR-18); frontend
   `saveConv` removed (server now the only persistence authority). **Phase 1 code stays
   present** — flag-off remains a working rollback (review F3).
2. **Files modified:** `config/settings.py` (default flip), `app/main.py` (lifespan wiring),
   `frontend/index.html` (saveConv removal), `docs/deployment.md` (rollback docs), tests
   (full suite on the flag-on path).
3. **Architecture impact:** the milestone's behavior change; reversible by flag.
4. **Risk level:** HIGH (mitigated: flag + revert).
5. **Test plan:** full suite green with flag on; flag-off smoke test (the rollback path is
   proven working); migration executed against real `chats/` and verified before deploy
   (ops, recorded in PR description).
6. **Rollback plan:** **flag off** (Phase 1 code intact) — primary; git revert secondary.
7. **Acceptance criteria:** suite green; flag-off smoke recorded; deployment doc documents
   both rollback layers.
8. **Estimated time:** 1 day.

### PR-26 — Legacy removal (Phase 1 brain/context + off-paths + flag)
1. **Goal:** delete `app/services/brain.py`, `app/services/context.py`, the flag-off paths
   in both routes, and the `CONVERSATION_ENGINE` setting. Rollback semantics transition
   from flag-based to revert/tag-based (Phase D §7).
2. **Files modified:** deletions above, `config/settings.py`, `app/main.py`, tests
   (off-path tests removed), `docs/architecture.md` (+ engine chapter).
3. **Architecture impact:** Phase 1 chat machinery retired; the engine is the only path.
4. **Risk level:** MEDIUM (deletion; everything is in git).
5. **Test plan:** full suite green post-deletion; dead-code grep (no references remain).
6. **Rollback plan:** `git revert PR-26` restores the entire Phase 1 path (flag re-added);
   previous tag as the outer layer.
7. **Acceptance criteria:** suite green; no dead code; flag gone everywhere.
8. **Estimated time:** 1 day.

### PR-27 — Frontend: pagination ("load older")
1. **Goal:** message list loads oldest-first with `before_seq`/`limit`; "load older"
   control; archive reads seamless. Merges **after** the switchover so it is never visible
   pre-rollout (review F7).
2. **Files modified:** `frontend/index.html`, tests, `docs/api.md` (query params).
3. **Architecture impact:** none.
4. **Risk level:** LOW-MEDIUM.
5. **Test plan:** static tests; manual e2e on a migrated 500-message conversation.
6. **Rollback plan:** revert.
7. **Acceptance criteria:** suite green.
8. **Estimated time:** 0.5 day.

### PR-28 — Gate evidence: benchmarks, docs, tag
1. **Goal:** full benchmark run → `benchmarks/M01.json` (deltas vs M00 within Phase D §4
   thresholds); consolidate `docs/architecture.md`, `docs/api.md`, `docs/testing.md`,
   `docs/troubleshooting.md`, README; sign off `reviews/M01.md` conditions 1–5; annotated
   tag `v2.0-m1` per Phase D §1.10.
2. **Files modified:** benchmarks, docs suite, `reviews/M01.md`, git tag.
3. **Architecture impact:** none; milestone gate only.
4. **Risk level:** LOW.
5. **Test plan:** benchmark deltas; docs links resolve; tag message contains the review
   summary.
6. **Rollback plan:** delete tag; docs revert.
7. **Acceptance criteria:** all 10 gate items evidenced; M01.json within budget; tag exists.
8. **Estimated time:** 0.5 day.

---

## 4. Critical path & schedule

```
Critical path: 01 → 07 → 08 → 09 → 10 → 11 → 12 → 19 → 20 → 21 → 24 → 25 → 26 → 28
(feeders: 03→05 and 01/03→15→17 join before 19; 22/23 join before 25; 02/27 join before 28)
≈ 20 working days sequential. Parallel tracks A (03–06), C (13–15), 16/18, 22/23, 27
add ≈ 8 days of parallel work → ≈ 5–6 calendar weeks (one implementer),
≈ 3–4 calendar weeks (two: storage track | domain+providers track).
```

**Bundling (only if the gate allows):** PR-03+04, or PR-09+10, or PR-11+12 — each saves
review overhead, not work; kept separate by default to hold every PR ≤ 500 lines.

## 5. Gate exit criteria (before `v2.0-m1`)

- All 28 PRs merged; PR-25 switchover live; M01.json within design §18 targets and ≤ 10%
  regression vs M00.
- `reviews/M01.md` conditions 1–5 demonstrated by tests/benchmarks (A1/A10/A11
  conformance, CA1/CA2 adversarial, 2-worker stress, M01 benchmarks, shard-aware
  migration).
- Phase E reassessment (`phase-e-reassessment.md`) run and logged before the next
  milestone's first PR.
