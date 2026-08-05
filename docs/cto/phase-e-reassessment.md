# Phase E — Continuous Reassessment Loop

**Date:** 2026-08-04
**Trigger:** immediately after every milestone passes CTO review and is tagged (Phase D §1, gate protocol).

## 1. The ritual (runs after every tag, before starting the next milestone)

1. **Re-run the Phase A lens.** Re-scan Falso and ULTRON for any module where the balance changed (new commits, new versions, new findings). Update `phase-a-comparison.md` deltas.
2. **Revalidate the architecture against reality.** Does the code still match Phase C? If a milestone shipped a pragmatic divergence, either amend Phase C (written, dated) or file a fix-up milestone item — never leave undocumented drift.
3. **Recheck "world-class" claims** (Phase C §1 targets):
   - Re-measure the three headline numbers (offline turn ≤500 ms, cloud turn ≤900 ms, barge-in ≤120 ms) against the competitors' current public specs — if a competitor moved the bar, the target moves too.
   - Re-verify that every feature still works fully offline (the differentiator none of the four competitors has).
4. **Technology sweep.** For each domain (voice, memory, brain, vision, frontend), one question: *is there a better-maintained, objectively superior component now?* If yes → Phase B decision record; if no → proceed. No change for the sake of change.
5. **Debt audit.** Re-read the "knowingly deferred" list from the last milestone's CTO review. Anything that can now be resolved cheaply gets a slot; anything still expensive stays deferred *with a date*.
6. **Benchmark drift check.** Re-run `benchmarks/run.py` if the environment changed (model upgrade, new hardware, new adapter); record in the milestone's review doc.

## 2. Ground rules

- **Architecture first.** If a redesign would improve the system, it happens before feature work — and it goes through Phase B's decision record (import only if objectively better).
- **No gratuitous code.** A reassessment outcome of "nothing to change" is a success. The default answer to any redesign question is *no* unless evidence says otherwise.
- **Evidence over opinion.** Every decision in this loop is recorded in `docs/cto/reviews/` with the measurement or comparison that drove it.
- **Redesigns are milestones too.** Any redesign large enough to touch a domain's ports becomes its own tagged milestone entry under Phase D, with the full ten-item gate.

## 3. Review log

| Date | After milestone | Outcome | Action |
|---|---|---|---|
| 2026-08-04 | (baseline) | Falso v0.1.0 + ULTRON reviewed; imports defined; V2 designed | Phase A–E docs committed; M0 next |

(Every subsequent milestone appends a row here, in `docs/cto/reviews/MXX.md`.)

---

# Deliverables summary (all committed under `docs/cto/`)

| Phase | Document | Core conclusion |
|---|---|---|
| A | `phase-a-comparison.md` | ULTRON wins visual engineering + frontend lifecycle; Falso wins everything else. 8 import candidates, 8 Falso defects found. |
| B | `phase-b-migration-plan.md` | 5 imports (hand tracker, tiered Three.js orb, TS modularization, a11y, tasks-vision SDK), 4 explicit rejections, 9 backend fixes. No merge. |
| C | `phase-c-v2-architecture.md` | V2 = hexagonal domains + event bus + WS voice-first pipeline + SQLite/ChromaDB + PermissionGate/audit; offline-first, cloud-opt-in. |
| D | `phase-d-milestones.md` | M0–M7, each with the full 10-item gate (architecture → … → git tag) and rollback rules. |
| E | (this doc) | Post-tag reassessment ritual with evidence-based decision log. |

**Next action:** begin **Milestone 0** — the security-first hardening baseline (Phase B §4 fixes + benchmark harness). Awaiting your go.
