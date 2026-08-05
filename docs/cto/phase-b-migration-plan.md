# Phase B — Migration Plan: What Falso Imports From ULTRON

**Date:** 2026-08-04
**Principle:** Import only ideas that objectively improve Falso. Never introduce technical debt. Never replace an existing module unless the new design is provably better (evidence in Phase A §4).

## 1. Decision record

| Decision | Ruling |
|---|---|
| Merge repositories / copy ULTRON wholesale | **NO.** Different languages, different concerns, no overlap in 27/30 modules. |
| Port the Three.js orb verbatim | **NO (as-is).** Import the *design* with Falso's constraints: offline-first, no build-weight explosion, desktop GPU tiers. |
| Adopt Next.js/React | **NO.** Rejected in Phase A §4 #6. A typed, buildable **static** frontend serves the same purpose at 1/50 the weight and keeps FastAPI as the single server. |
| Replace any backend module | **NO.** ULTRON has no backend modules; zero candidates. |
| Adopt MediaPipe tasks-vision SDK | **YES.** Legacy `@mediapipe/hands` is deprecated; the new SDK is maintained, typed, has official docs. Import with SRI + local WASM (offline-first). |

## 2. Import list (ordered, each with acceptance test)

### I-1. Hand-tracking engine replacement
- **From:** ULTRON `lib/handTracker.ts` — class design: hysteresis pinch (0.32/0.45), handedness-keyed state map, grab smoothing, mode state machine, GPU→CPU fallback, full `stop()` teardown, overlay drawing.
- **To:** Falso frontend as a `HandTracker` module (TypeScript).
- **Improves:** leak (camera never released), 12Hz console spam, dead state (`smoothHandRotation`), implicit globals.
- **Acceptance:** identical gesture UX; camera stream stops when tracking off; zero console output at idle; unit-testable pure logic (pinch/zoom math extracted, no DOM).
- **Debt guard:** the gesture *semantics* (what each gesture does) stay in Falso's orb integration, not in the tracker.

### I-2. Orb visual engine (Three.js) with Falso constraints
- **From:** ULTRON `lib/orbScene.ts` — layered wireframe shells, core pulse, debris, dust, scan rings, bloom + chromatic aberration.
- **To:** Falso frontend as an `OrbScene` module.
- **Falso-specific changes (mandatory):**
  1. **Quality tiers** (auto-detect: `highPerformance`/`lowPerformance` or explicit setting): disable post-processing below tier, reduce debris/dust counts, cap `pixelRatio` at 1.5 on low tier.
  2. **Background-tab pause** (`document.visibilitychange` stops rAF).
  3. **Energy-state coupling** stays in Falso's orchestration layer; the scene exposes only camera/scene state (ULTRON's `OrbSceneApi` pattern).
  4. **Offline-first:** vendored three.min.js (or bundled at build), no CDN.
- **Acceptance:** 60fps on the dev machine at high tier; ≤30fps budget at low tier with visuals still coherent; zero GPU work while tab hidden; dispose() releases all resources.
- **Debt guard:** never copy the 858-line single-function monolith; the module is built as: `OrbScene` (three.js objects) + `OrbController` (animation/pulse logic) + `api` surface.

### I-3. Frontend module boundaries + TypeScript build (surgical)
- **From:** ULTRON's discipline (3 files, typed contracts) — not its framework.
- **To:** Falso frontend restructured into modules with typed interfaces: `tracker`, `scene`, `chat` (stream parser), `audio`, `dashboard`, `panels`, `state`.
- **Tooling:** keep it static & local: TypeScript + esbuild (or tsc) producing a minified bundle; **no framework, no node server, no Next.** FastAPI still serves the built files.
- **Acceptance:** `tsc --noEmit` clean; build produces <200KB gzipped; `ruff`-equivalent lint for TS (eslint) clean; existing behavior byte-compatible.
- **Debt guard:** dead code (originalDraw, smoothHandRotation, camera_utils.js) is *removed*, not ported; `'use strict'` everywhere; no implicit globals.

### I-4. Accessibility + interaction patterns
- **From:** ULTRON's real `<button>`s, aria-labels, focusable controls.
- **To:** Falso dock, mic toggle, hints, conversation rows become real controls with aria states.
- **Acceptance:** full keyboard operability; `prefers-reduced-motion` honored (orb pauses, animations reduced).
- **Debt guard:** visual styling must not regress (CSS custom props keep the chrome identical).

### I-5. MediaPipe tasks-vision + SRI (dependency hygiene)
- **From:** ULTRON `package.json` — `@mediapipe/tasks-vision@^0.10.35`.
- **To:** Falso vendor: WASM files local (offline-first) OR jsdelivr with `integrity=` SRI attributes; remove legacy `hands.js`/`camera_utils.js` CDN scripts.
- **Acceptance:** hand tracking works with network disabled (local WASM); `integrity` attribute present on any remaining CDN script.
- **Debt guard:** keep the delegation fallback (GPU→CPU) and a `dispose()` on close.

## 3. Explicit non-imports (with reason)

| Rejected idea | Reason |
|---|---|
| ULTRON's exact visual theme (Iron-Man amber HUD, "U.L.T.R.O.N." identity) | Falso has its own identity; technique, not theme. |
| Next.js runtime, React 19, node_modules stack | Weight, complexity, no benefit for a static SPA (Phase A §4 #6). |
| Any backend code | ULTRON has none. |
| 2,000-dust / 1,700-sprite defaults | Unbudgeted GPU cost; Falso tiers it (I-2). |
| ULTRON's README/demo posture | Falso's doc set is superior; nothing to take. |

## 4. Backend fixes required by this review (independent of ULTRON)

These are defects found in Phase A, not imports. They gate the V2 baseline (Milestone 0):

| Fix | Location | Severity |
|---|---|---|
| Sandbox escape in `_search` — normalize pattern, reject `..`, resolve+verify each match | `app/tools/file_tool.py:648–683` | HIGH |
| Escape server data before `innerHTML` (tool_start, model) | `frontend/index.html:1843, 1858` | MEDIUM |
| Frontend sends `X-Falso-Token` when configured (setting surfaced to page via meta or `/config` endpoint) | frontend + `app/main.py` | MEDIUM |
| `_last_filename` moves to per-conversation state | `app/tools/file_tool.py:129` | MEDIUM |
| Write/append limit counts bytes, not chars | `app/tools/file_tool.py:571–578` | LOW |
| `copy` becomes real copy; `move` stays rename | `file_tool.py:259–264` | LOW |
| Operation timeout for search/list scans | `file_tool.py` + manager | LOW |
| SSE/NDJSON: standardize on real SSE (`data:` frames) with a versioned parser on both sides | backend + frontend | LOW |
| Single AudioContext ownership; mic teardown closes it | `index.html:646, 2143` | LOW |

## 5. Sequence & risk

| Order | Work | Risk | Why this order |
|---|---|---|---|
| 1 | Backend fixes (F4 table) | Low | Security first; independent of ULTRON. |
| 2 | Frontend modularization + TS build (I-3) | Medium | Prerequisite for I-1/I-2/I-4; restructure before adding new engines. |
| 3 | HandTracker import (I-1) | Medium | Replaces legacy tracking on the new module surface. |
| 4 | Orb import with tiers (I-2) | High | Visual change is user-visible; gated behind the same UI state. |
| 5 | Accessibility pass (I-4) | Low | Cheap; done last to avoid churn. |
| 6 | MediaPipe SDK + SRI (I-5) | Low | Final dependency hygiene. |

**Rollback rule:** every import lands behind the previous UI (old orb/hand tracking) until its acceptance test passes; a failed acceptance test rolls back to the tag before it (Phase D gating).
