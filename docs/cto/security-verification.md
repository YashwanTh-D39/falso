# Security Verification Report — Two Confirmed Vulnerabilities

**Date:** 2026-08-04
**Status:** PROVEN (both exploited against the real codebase, no mocks)
**PoC artifacts:** `C:\Users\Admin\AppData\Local\Temp\opencode\poc\` (search_escape_poc.py, xss_flow_poc.py, xss_dom_poc.cjs)
**Scope:** Falso v0.1.0 @ `cc35eb7` (Phase 1 hardened implementation)

---

## Vulnerability 1 — Sandbox escape via glob traversal in `FileTool._search`

### 1.1 Proof (executed)

Real code path, real sandbox directories, on this machine:

```
prompt: 'search for ../../../../Windows/*.ini'
  match_prompt -> command='search' pattern='../../../../Windows/*.ini'
  matches: 64
    ESCAPED -> C:\Users\Admin\Desktop\..\..\..\..\Windows\KPCMS.INI  (size=156)
    ESCAPED -> C:\Users\Admin\Desktop\..\..\..\..\Windows\UV_LastPW.ini  (size=0)
    ESCAPED -> C:\Users\Admin\Desktop\..\..\..\..\Windows\system.ini  (size=219)
    ESCAPED -> C:\Users\Admin\Desktop\..\..\..\..\Windows\win.ini  (size=92)
    ... (64 total, incl. 3 nested-depth variants per file)
```

File names **and sizes** from `C:\Windows` are returned by a prompt that never
names a sandboxed file. The `..` segments are preserved in the returned paths
(`...\Desktop\..\..\..\..\Windows\...`) proving glob did not normalize them.

### 1.2 Exact location

| Item | Location |
|---|---|
| File | `app/tools/file_tool.py` |
| Sink (unescaped glob) | **lines 655–657** — `glob_module.iglob(f"{base_str}/**/{pattern}", recursive=True)` |
| Pattern extraction (raw capture) | **line 426** — `kwargs['pattern'] = m.group(1).strip()` |
| Match loop that discloses `..`-escaped paths | **lines 658–666** (incl. `m.stat().st_size` at 664) |
| Every *other* command's containment guard (never called here) | `_check_allowed` lines 46–57; `_resolve_path` lines 60–77 |

### 1.3 Root cause

`_search` is the **only** command handler that does not route its target
through `_resolve_path`/`_check_allowed`. The user-supplied pattern is
concatenated verbatim into a recursive glob. Python's `glob` module performs
**no normalization of `..`** — segments are walked via `os.scandir`, which
honors `..` as "parent directory" — so `{base}/**/../../../../Windows/*.ini`
walks `Documents/Desktop/Downloads` → up 4 levels → matches any pattern
anywhere the process user can read. Defense relies on a single missing call.

### 1.4 Exploit steps

1. `POST /api/v1/chat` with `{"prompt": "search for ../../../../Windows/*.ini"}`
   (reachable at `0.0.0.0:8000`; no auth when `API_TOKEN` unset).
2. `FileTool.match_prompt` (L420–428) matches the search regex; pattern is
   taken raw.
3. `_search` (L655) builds `C:\Users\Admin\Desktop\**\..\..\..\..\Windows\*.ini`
   and iterates matches, `stat()`-ing each (L664).
4. Response `matches[]` contains path + type + size of every hit outside the
   sandbox (verified: 64).
5. Variants: `../../../../Users/*/AppData/**/*.log`, `../../../../Program
   Files/**/*.cfg`, etc. — anything the process account can read.

### 1.5 Impact

- **Disclosure:** existence, exact path, type, and byte-size of arbitrary
  files/directories on the machine — including sensitive-named files
  (verified: `UV_LastPW.ini`, `KPCMS.INI`), user profiles, AppData structure.
- **No content read/write through this vector** (echoing a leaked path back
  into `read` re-runs `_resolve_path` and is rejected) — the sandbox's
  *envelope* is broken, its *data* is not exfiltratable via this bug alone.
- **Amplification:** combines with V1's class-level `_last_filename`
  (file_tool.py:129) and the "delete it" pronoun fallback — a leaked path can
  influence later destructive prompts in other conversations.

### 1.6 CVSS 3.1 estimate

```
AV:N / AC:L / PR:L / UI:N / S:C / C:L / I:N / A:N  =  6.0  (Medium)
```
- Scope changed (crosses the sandbox boundary).
- Confidentiality Low (names/sizes only, no contents).
- If `API_TOKEN` is unset (the default), any LAN/network peer can reach the
  endpoint: PR:N raises the score toward **7.1 (High)**.

### 1.7 Why the 70 tests missed it

- `tests/test_file_tool.py:47` (`test_escape_outside_sandbox_rejected`)
  exercises **only `read`** — the one command that already has the guard.
- `tests/test_file_tool.py:72` (`test_search_result_cap`) is the only search
  test; it uses a benign `*.txt` pattern and asserts only the cap.
- No test ever passes a traversal pattern to `search`, and nothing asserts
  that `_search`'s matches stay inside `_allowed_bases()`. The vulnerability
  is a *missing-call* bug — only a direct test of the search path catches it.

### 1.8 Smallest possible fix (not yet implemented)

Reuse the existing, tested containment primitive — filter each match through
`_check_allowed` and use the *resolved* path:

```python
for match in glob_module.iglob(f"{base_str}/**/{pattern}", recursive=True):
    try:
        m = _check_allowed(Path(match))   # raises PermissionError outside sandbox
    except PermissionError:
        continue
    if m.is_file() or m.is_dir():
        matches.append({"path": str(m), "type": ..., "size": m.stat().st_size if m.is_file() else None})
        ...
```

One guard, consistent with every other command. Optional hardening (not
required once matches are filtered): reject patterns containing `..` or path
separators up front at L426.

### 1.9 Regression tests to add

1. `test_search_traversal_patterns_contained`: for patterns
   `../../../../Windows/*.ini` and `..\..\..\*.txt` (workspace-relative):
   `r.success is True` and **`count == 0`** / no match path escapes the
   workspace.
2. `test_search_cannot_disclose_outside_file`: create `secret.txt` in
   `tmp_path.parent`; search `../secret.txt` and `..`-traversal variants →
   not present in `matches`.
3. `test_search_benign_patterns_still_work` (guard against over-fixing):
   existing `test_search_result_cap` and a normal `*.txt` search keep passing.
4. Optional (Windows): junction-inside-base pointing outside → `_check_allowed`
   resolves the junction and rejects (validates the fix on real `resolve()`
   semantics).

---

## Vulnerability 2 — DOM XSS via unescaped `tool_start` detail

### 2.1 Proof (executed)

**Data flow (real backend code):**

```
prompt   : 'read <img src=x onerror=alert(1)>'
command  : 'read'
detail   : '<img src=x onerror=alert(1)>'     <- payload intact, no escaping/encoding
prompt   : 'read <svg onload=alert(2)>'
detail   : '<svg onload=alert(2)>'            <- intact
```

**Sink execution (jsdom, replicating index.html:1843 verbatim):**

```
innerHTML after sink: <span class="spinner">◌</span> FILE — READ // <img src="x" onerror="...">
XSS EXECUTED: onerror handler fired; document.title = XSS-PROVEN
```

In a real browser the `onerror` fires automatically the moment `<img src=x>`
fails to load (immediate, no user interaction). jsdom does not emulate image
fetch failure, so the error event was dispatched manually — same handler, same
execution. Payload choice matters: double-quoted payloads are partially eaten
by `_extract_quoted` (file_tool.py:144–150); **quote-free** payloads survive
verbatim (verified above).

### 2.2 Exact location

| Item | Location |
|---|---|
| File | `frontend/index.html` |
| Sink 1 (primary) | **line 1843** — `ti.innerHTML = \`<span class="spinner">◌</span> ${toolName} — ${act} ${detail ? '// '+detail : ''}\`;` |
| Sink 2 (secondary) | **line 1858** — `document.querySelector('.sysid').innerHTML = 'FALSO // ' + modelName...` |
| Event producer | `app/routes/brain.py` (route) → `app/services/brain.py` **lines 125–130** (`"detail": kwargs.get("path") or kwargs.get("new_name") or ""`) |
| Payload origin | `app/tools/file_tool.py` **line 458** (`store_path(m.group(1).strip())`) — raw rest-of-prompt becomes `path` |
| Escaping helper that exists but is unused here | `escHtml` at index.html:1351–1355 |

### 2.3 Root cause

Server-derived string (`detail` = parsed prompt fragment, i.e. attacker
influence) is interpolated into `innerHTML` with no escaping. The frontend
already contains `escHtml()` (used correctly for conversation titles at
L1351/L1365) — it was simply not applied at the `tool_start` sink. Secondary
sink L1858 interpolates the model name from the Ollama response into
`innerHTML` unescaped (an attacker with control of a local model/proxy could
inject there too).

### 2.4 Exploit steps

1. Attacker crafts a prompt containing a quote-free payload, e.g.
   `read <img src=x onerror=alert(1)>` (or a chat script/snippet the user is
   socially engineered into pasting; payload can be disguised inside a file
   name).
2. User sends it. Backend parses `path = <img src=x onerror=alert(1)>`
   (file_tool.py:458), emits `tool_start` with that `detail` (brain.py:129).
3. Frontend inserts `detail` into `#toolIndicator` via `innerHTML` (L1843).
4. `<img src=x>` fails to load → `onerror` runs **JavaScript with the full
   origin privileges of the Falso page**.

**What the injected JS can do:** read and delete every conversation
(`GET/DELETE /api/v1/conversations/*`), exfiltrate chat contents (which may
contain pasted secrets, file paths), issue further chat prompts, drive the
file tool (read/write within sandbox; the "confirm delete" gate is trivially
bypassed by scripting a `yes` turn), and — if the user granted mic/camera —
drain those streams. This is not cosmetic.

### 2.5 Impact

- **Full origin-level XSS:** arbitrary script in the user's Falso session.
- Data confidentiality (conversations, tool results) and integrity (file
  operations executed via the assistant) are compromised; availability
  marginally (UI takeover).
- One caveat lowers the practical rating: a *human* must issue the crafted
  prompt (or be tricked into it); there is no stored-reflect vector from the
  model itself (tool events are prompt-derived, not model-derived).

### 2.6 CVSS 3.1 estimate

```
AV:N / AC:L / PR:N / UI:R / S:U / C:H / I:H / A:L  =  8.3  (High)
```
- Requires user interaction (UI:R) — the crafted prompt must be sent.
- Confidentiality/Integrity High: full origin privileges over the user's
  conversations and tool execution.

### 2.7 Why the 70 tests missed it

- **There are no frontend tests at all.** All 70 tests are backend pytest;
  the sink lives in the untested 1,600-line IIFE.
- Backend tests that touch the event (`tests/test_backend/test_brain.py:36,45`)
  assert only the event **type** (`events[0]["type"] == "tool_start"`), never
  the safety of interpolating its fields into HTML — a frontend concern the
  backend suite structurally cannot see.

### 2.8 Smallest possible fix (not yet implemented)

Escape the three interpolated values with the existing helper, and do the
same at the secondary sink:

```js
// index.html:1840-1843
const toolName = escHtml((data.tool || '').replace(/_/g,' ').toUpperCase());
const act     = escHtml((data.action || '').toUpperCase());
const detail  = escHtml(data.detail || '');
ti.innerHTML = `<span class="spinner">◌</span> ${toolName} — ${act} ${detail ? '// '+detail : ''}`;

// index.html:1858
if(modelName) document.querySelector('.sysid').innerHTML =
    'FALSO // ' + escHtml(modelName.toUpperCase().replace(':','')) + '<br>NO CLOUD REQUIRED';
```

`escHtml` (textContent→innerHTML) encodes `& < > " '` — sufficient for this
sink. Long-term (Phase C/Phase B I-3): eliminate `innerHTML` for data values
and render via DOM nodes.

### 2.9 Regression tests to add

1. **New frontend test harness (vitest)** — first frontend tests in the repo:
   - `escHtml('<img src=x onerror=alert(1)>')` contains `&lt;img`, no element created.
   - `renderToolStart({tool, action, detail: '<img onerror=...>'})` → output
     innerHTML contains `&lt;img`, and the DOM contains **no** `img` element.
   - Payloads: `<svg onload>`, `"><script>`, `onerror`, model-name sink variant.
2. **Backend defense-in-depth test:** prompt
   `read <svg onload=alert(2)>` → the `tool_start` line's `detail` is asserted
   to contain no `<` when... (no — escaping stays the frontend's job; instead
   assert the *emitted shape* stays stable so the frontend contract test can
   rely on it).
3. **E2E (optional, `slow`):** drive the real server with a payload prompt,
   open the page in a headless browser, assert `#toolIndicator` contains no
   injected element and `window.__xssFired` is undefined.

---

## Combined verdict & next step

| Vuln | File:Lines | Proven | CVSS |
|---|---|---|---|
| Sandbox escape (search) | `file_tool.py:655–657` | Yes — 64 matches from `C:\Windows` | 6.0 (Medium, →7.1 unauthenticated) |
| DOM XSS (tool_start) | `index.html:1843` (+1858) | Yes — handler executed | 8.3 (High) |

Both are the first items in Milestone 0 (Phase D). Per your instruction,
**nothing has been modified** — the codebase is untouched; PoCs live only in
the temp dir. Awaiting go to implement the §1.8/§2.8 fixes and §1.9/§2.9
regression tests.
