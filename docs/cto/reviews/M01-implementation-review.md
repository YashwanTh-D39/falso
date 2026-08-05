# M01 — Pre-Implementation Review: Implementation Roadmap

**Date:** 2026-08-04
**Reviewer:** CTO, Falso
**Subject:** `docs/cto/m1-implementation-roadmap.md` (v1)
**Verdict:** **APPROVED AFTER REDESIGN** — 8 flaws found (2 correctness-blocking, 3
flag-discipline, 2 ordering, 1 policy gap). The roadmap has been redesigned (§6) and
rewritten. Do not implement the v1 roadmap.

**Method:** every PR checked against the 8 rules; a full dependency matrix built; file-level
conflict ownership audited; feature-flag timeline reconstructed; test coverage mapped to the
design's §17 suite.

---

## 1. Dependency matrix (v1 → verified)

| PR (v1) | Declared deps | Verified deps | Verdict |
|---|---|---|---|
| PR-01 config | — | — | ✓ |
| PR-02 domain foundation | — | — | ✓ |
| PR-03 budget | 02 | — (pure math) | ✓ relaxed |
| PR-04 assembler | 03 | 02, 03 | ✓ |
| PR-05 event bus | 02 | 02 | ✓ |
| PR-06 sqlite adapter | — | 01 (settings: db path, shard_count) | **fix: add 01** |
| PR-07 migrations | 06 | 06 | ✓ |
| PR-08 repos I | — | 03, 07 | **fix: add 03, 07** |
| PR-09 repos II | 08 | 08 | ✓ |
| PR-10 UoW+lease | — | 08, 09 | **fix: add 08, 09** |
| PR-11 ledger+outbox | 10 | 10 | ✓ |
| PR-12 cache | 08 | 03 only | **fix: relax (was over-serialized)** |
| PR-13 tokenizers | — | 01, 03 | **fix: add 01** |
| PR-14 LLM provider | 06 | 01, 03 — **not 06** | **fix: relax (false dep on sqlite)** |
| PR-15 session runtime | 08/09 | 03, 09 | ✓ |
| PR-16 summarizer | 04, 09, 14 | 03, 04, 09, 14 | ✓ |
| PR-17 maintenance | 09, 11 | 09, 11 | ✓ |
| PR-18 orchestrator I | 02–15+16 | 02–17 | ✓ (add 17) |
| PR-19 orchestrator II | 18 | 18 | ✓ |
| PR-20 chat adapter | 18/19 | 18, 19 | ✓ |
| PR-21 conv service+route | 08/09 | 08, 09 | ✓ deps; **see flaw F2** |
| PR-22 migration script | 07/08 | 07, 08 | ✓ |
| PR-23 frontend chat | 20 | 20 | ✓ deps; **see flaw F1** |
| PR-24 frontend pagination | 21/23 | 21 | ✓ |
| PR-25 benchmark harness | — | 01 | ✓ deps; **see flaw F4** |
| PR-26 switchover | 20, 22, 23, 24 | + 17 (maintenance wiring), + 21 | **fix: add; see flaw F3** |
| PR-27 gate evidence | 25 | 25 | ✓ |

**Every dependency resolves to a PR inside the roadmap.** No PR references M2+ work or
unfinished components. Three false/over-strict deps (cache, LLM provider, budget) and three
missing deps (adapter→config, repos→domain, UoW→schema) were corrected.

---

## 2. Rule-by-rule verification

### Rule 2+3 — independently mergeable, compiles by itself

- Python import graph is acyclic by construction: domain → infrastructure → application →
  adapters; every PR imports only from merged predecessors (matrix above).
- All PRs in tracks A/C (pure logic, ports, providers) are additive: they change no existing
  behavior, so `main` stays green with them merged.
- Behavioral PRs (chat adapter, conversations route, frontend) ship behind
  `CONVERSATION_ENGINE` (off) — v1 violated this for the conversations route (F2) and the
  frontend persistence handoff (F1); both fixed in the redesign.

### Rule 4 — independently revertible

**Revert policy (v1 gap, now explicit):** reverts run in **reverse topological order** —
a PR is only reverted while no merged successor depends on it. Within that policy every PR
is revertible with `git revert <commit>`:

- Additive PRs: revert is a pure delete. ✓
- Flagged PRs (chat, conversations): revert restores Phase 1 path. ✓
- Migration script (PR-23): reverting restores file-based routes (pre-PR-25) or leaves the
  DB populated but unused (post-PR-25) — data is never destroyed (chats archived, not
  deleted). ✓
- **Rollback semantics transition:** until PR-26, rollback = *flag off* (Phase 1 code still
  present). PR-26 deletes the Phase 1 code and the flag; from then on rollback = `git
  revert PR-26` / previous tag (Phase D §7). v1's PR-26 claimed "flag off + revert" in the
  same PR after deleting the flag-off code — a contradiction (F3).
- No PR performs destructive data operations anywhere in the plan. ✓

### Rule 5 — no dependence on unfinished implementation

- Orchestrator (PR-19) consumes every domain/infra PR — all scheduled strictly before it.
- Frontend PR-24 needs only the wire contract (PR-21), which is defined by a merged PR. ✓
- The one hidden dependency was *"frontend stops persisting while the server flag is still
  off"* — frontend depends on a server behavior it cannot detect. Fixed by moving
  `saveConv` removal to the switchover (F1). ✓

### Rule 6 — minimize merge conflicts

File-ownership audit (prod files touched by more than one PR):

| File | Touched by | Risk |
|---|---|---|
| `config/settings.py` | PR-01 (add fields + flag), PR-25 (flip default), PR-26 (remove flag) | Low — sequential, ≤2-line diffs each |
| `frontend/index.html` | PR-24 (chat), PR-25 (saveConv removal), PR-27 (pagination) | Low — sequential, distinct regions |
| `app/routes/brain.py` | PR-21 (flagged adapter), PR-26 (off-path removal) | Low — sequential |
| `app/routes/conversations.py` | PR-22 (flagged dual-path), PR-26 (off-path removal) | Low — sequential |
| `docs/api.md`, `docs/deployment.md` | multiple | Low — sectioned edits |
| `app/conversations/orchestrator.py` | PR-19, PR-20 | Low — PR-20 strictly after PR-19, additive section |

No file is edited in parallel by independent tracks. New-file PRs cannot conflict.
**Conflicts minimized; remaining risk is sequential-only.** ✓

### Rule 7 — features behind flags until rollout

| Feature | Behind flag | Rollout |
|---|---|---|
| Engine chat path | `CONVERSATION_ENGINE=off` (PR-21) | PR-25 (default on) |
| DB-backed conversations CRUD | flag (PR-22, dual-path) | PR-25 |
| Server-side turn persistence | flag (via PR-21 path) | PR-25 |
| Summarization / context compression | engine path only (flagged) | PR-25 |
| Frontend pagination | **moved after PR-25** (F7) — never visible pre-rollout | PR-27 |
| Migration script | ops tool, no runtime surface — no flag needed | PR-23 → run at PR-25 |
| Benchmark harness | dev tool | PR-02 |

v1 violations fixed: conversations route was unconditional (F2); frontend persistence
handoff implied flag-on behavior pre-rollout (F1); pagination was user-visible before
rollout (F7). ✓ (after redesign)

### Rule 8 — complete automated tests

Every PR carries its test files (per-PR test plan in the roadmap). Gaps found and closed:

- v1 PR-20's 429 mapping test was deferred to the route PR — kept, but now explicitly
  listed in PR-21's test plan so it cannot be forgotten. ✓
- Frontend: the repo has no JS test infrastructure (vitest is M6 scope — Phase D M6). The
  honest maximum today is: static-source security tests (existing pattern) + API-level
  contract tests + a recorded manual e2e checklist. Accepted and **documented as a known
  limitation** in the roadmap (F9) — not silently waived.
- Mutation sanity on critical invariants (dedup reuse, ledger replay, owner predicate,
  floor preservation) is a per-PR acceptance criterion, matching design §17. ✓

---

## 3. Flaws found and fixes (v1 → v2 roadmap)

| # | Sev | Flaw | Fix |
|---|---|---|---|
| F1 | **H** | PR-23 removed frontend `saveConv` while `CONVERSATION_ENGINE` was still off (until v1 PR-26). The frontend cannot read server flags; on the default flag-off path **conversations would stop persisting entirely** — silent data loss. | Frontend PR keeps `saveConv` (idempotent upsert — harmless when flag on, essential when off); removal moves into the switchover PR. |
| F2 | **H** | v1 PR-21 rewrote the conversations routes unconditionally, contradicting design §16.1 ("Phase 1 endpoints remain until the switchover commit") and breaking flag-off rollback (flag off would still hit DB-backed routes). | Route becomes **flagged dual-path** (off = exact Phase 1 file behavior; on = DB-backed + pagination params), matching the brain-route pattern; off-path deleted at legacy removal. |
| F3 | **M** | v1 PR-26 self-contradiction: deleted legacy code in the same PR that claimed "rollback = flag off". Once the off-path is deleted, flag-off cannot work. | Split into PR-25 **switchover** (flag on; legacy code intact; rollback = flag off) and PR-26 **legacy removal** (delete off-path + flag; rollback = `git revert`). Rollback semantics transition documented. |
| F4 | **M** | v1 PR-25 (benchmark harness + M00 baseline) was numbered to merge after the conversations route changed — the "true baseline before the engine lands" claim was false. | Move harness + M00 baseline to **PR-02**, immediately after config, before any behavior-changing PR. |
| F5 | **M** | False dependencies over-serialized the graph: LLM provider "after 06" (sqlite — no dependency), cache "after 08" (none), budget "after 02" (none). | Relaxed; three tracks become parallel. |
| F6 | **M** | `CONVERSATION_ENGINE` flag was introduced in v1 PR-20 instead of the config foundation PR — settings.py touched twice, flag story fragmented. | Flag defined in PR-01 (default off); PR-25 flips default; PR-26 removes it. |
| F7 | **L** | Frontend pagination (user-visible) landed before rollout. | Moved to PR-27, after switchover. |
| F8 | **L** | No explicit revert policy. | Reverse-topological revert rule added to global rules. |
| F9 | **L** | Frontend test completeness unstated. | Documented limitation (static + API + manual e2e; vitest is M6). |

---

## 4. Redesigned order (v2) — rationale summary

```
01 config (incl. flag) → 02 benchmarks+M00
03 domain → 04 budget → 05 assembler | 06 bus          (track A, parallel)
07 sqlite → 08 schema → 09 repos I → 10 repos II       (track B)
             11 UoW+lease → 12 ledger+outbox           (track B')
13 cache · 14 tokenizers · 15 LLM provider             (track C, parallel)
16 session runtime · 17 summarizer (15) · 18 maintenance
19 orchestrator I → 20 orchestrator II
21 chat adapter (flag) · 22 conv routes (flag, dual-path) · 23 migration script
24 frontend session-aware (saveConv kept)
25 switchover (flag on, migration, maintenance, saveConv removal)
26 legacy removal (delete Phase 1 + flag; rollback = revert)
27 frontend pagination
28 gate evidence + tag
```

- **Critical path:** 01 → 07 → 08 → 09 → 10 → 11 → 12 → 19 → 20 → 21 → 24 → 25 → 26 → 28
  (feeding: 03→05, 03/01→15→17 before 19; 22/23 before 25).
- **Parallel tracks:** A (03–06), C (13–15), 16/18, 22/23, 27 — 5 tracks idle-time-free.
- **Why better:** every behavior change is flag-gated until PR-25; rollback semantics are
  single-valued at every point in time; the baseline benchmark is honest; no false
  serialization; frontend never assumes server behavior it cannot detect.
- Schedule unchanged in spirit: ~15 sequential hops ≈ 20 working days; with two implementers
  (storage track / domain+providers track) ≈ 3–4 calendar weeks to the tag.

## 5. Approval

The v1 roadmap fails rules 4, 5, and 7 on the frontend-handoff and conversations-route
points (F1/F2). The **v2 roadmap** (`m1-implementation-roadmap.md`, rewritten) satisfies all
8 rules:

1. ✓ Dependency matrix explicit and acyclic (per-PR "Depends on" field).
2. ✓ Every PR lands green on `main`; additive or flagged.
3. ✓ Compiles: import graph is acyclic; no cross-track file edits.
4. ✓ Revertible: reverse-topological policy; single-valued rollback semantics per point in
   time; no destructive data ops.
5. ✓ No unfinished dependencies; frontend makes no undetectable server assumptions.
6. ✓ File-ownership audit shows sequential-only, region-isolated edits.
7. ✓ Every user-visible feature is flag-gated until PR-25; pagination after rollout.
8. ✓ Per-PR test plans cover the design §17 suite; frontend limitation documented honestly.

**Approved for implementation.** PR-01 may begin.
