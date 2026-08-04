# Security Guide

Falso is a **local-first** application. By default it binds `0.0.0.0` with
no token and debug on — fine on a trusted machine, **not** fine exposed to a
network. This document describes the implemented controls and the rules for
safe exposure.

## Threat model summary

Threats addressed: unauthorized API access, cross-origin browser attacks,
oversized/DoS request bodies, content sniffing, clickjacking/embedding,
unrestricted file-tool access, path traversal in conversation ids.

## Controls

### 1. API authentication (`API_TOKEN`)

Implemented in `app/middleware/security.py`:

- When `API_TOKEN` is non-empty, **every** `/api/*` request (except
  `OPTIONS` preflight) must present the token.
- Accepted headers: `Authorization: Bearer <token>` or
  `X-Falso-Token: <token>`.
- Comparison uses `hmac.compare_digest` (constant-time, resistant to timing
  attacks).
- Missing/invalid → `401 {"detail":"Unauthorized"}`.
- Non-`/api/*` routes (frontend, `/health`) are exempt so the UI can load.

### 2. Cross-origin validation

Two layers:

- **CORS middleware** — reflects `ALLOWED_ORIGINS` and restricts
  methods/headers (`GET, POST, DELETE, OPTIONS`;
  `Content-Type, Authorization, X-Falso-Token`). `allow_credentials=false`.
- **SecurityMiddleware** — for mutating methods (`POST/PUT/PATCH/DELETE`)
  on `/api/*`, a non-empty `Origin` header that is neither same-origin nor
  in `ALLOWED_ORIGINS` → `403 {"detail":"Origin not allowed"}`. This blocks
  cross-site form posts even when CORS headers are not required by the
  browser.

### 3. Request body limits (two layers, never buffered)

`MAX_REQUEST_BYTES` (default 10 MB) is enforced twice:

1. **Declared `Content-Length`** — rejected up front with `413` before any
   body is read.
2. **Streaming counter** — the actual `receive()` stream is counted in
   flight; chunked/streamed bodies that exceed the limit are cut off with
   `413` at the moment of overflow (remaining bytes never consumed). This
   closes the chunked-encoding bypass.

### 4. Response headers

Every HTTP response (including middleware-rejected ones) carries:

| Header | Value |
| --- | --- |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `Cross-Origin-Opener-Policy` | `same-origin` |
| `Permissions-Policy` | `camera=(self), microphone=(self), geolocation=()` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' https://cdn.jsdelivr.net; object-src 'none'; frame-ancestors 'none'; base-uri 'self'` |

CSP notes: `'unsafe-inline'` scripts/styles and `https://cdn.jsdelivr.net`
(MediaPipe) are required by the current single-file frontend;
`'wasm-unsafe-eval'` is required by MediaPipe's WASM runtime; `blob:` media
is required by the microphone visualizer. Tightening the CSP requires
refactoring the frontend to remove inline scripts/CDN.

### 5. File tool sandbox

`FileTool` (`app/tools/file_tool.py`) is restricted to:

- `Documents`, `Desktop`, `Downloads` (home directory) — always allowed;
- `FILE_TOOL_WORKSPACE`, when configured — extra allowed base.

Path resolution (`_check_allowed`) resolves every candidate
(`~` expansion, relative, absolute) and requires it to be inside an allowed
base via `Path.relative_to`; anything else raises `PermissionError`, surfaced
to the user as an error message. Limits: reads ≤ `MAX_FILE_READ_BYTES`,
writes ≤ `MAX_FILE_WRITE_BYTES`, search ≤ `MAX_SEARCH_RESULTS` results,
listings ≤ `MAX_LIST_ITEMS`.

Deletions additionally require an explicit confirmation step (see
architecture.md, Phase 0).

### 6. Conversation id validation

IDs must match `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$` — no dots, slashes, or
percent-encoded path separators. Validation happens before the id is used in
any file operation (reject `400`), and conversation JSON files live in a
fixed `chats/` directory.

### 7. Prompt validation

`POST /api/v1/chat` requires a non-empty prompt (1–50,000 chars, enforced by
Pydantic `min_length=1, max_length=50_000` plus an explicit empty-check in
`BrainService.validate_prompt`). The system prompt file is optional and
loaded once at startup.

### 8. Input never reaches a shell

The only subprocess is `nvidia-smi` with a fixed argument list (no user
input) — see `SystemMonitor._probe_gpu`.

## Hardening checklist for non-local deployment

- [ ] Set a strong `API_TOKEN` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
- [ ] Set `ALLOWED_ORIGINS` to your real UI origin(s); don't use `*`.
- [ ] `FASTAPI_DEBUG=false`.
- [ ] Put the API behind TLS (reverse proxy), keep `/api/v1/chat` uncached.
- [ ] Bind to a private interface (`FASTAPI_HOST`) or firewall port 8000.
- [ ] Keep `MAX_REQUEST_BYTES` at or below 10 MB unless you raise
      `MAX_FILE_WRITE_BYTES` intentionally.
- [ ] Run one uvicorn worker (pending-action state is in-memory, per-process).

## Known limitations

- **No `Host` header allowlist** — the API does not verify the `Host`
  header; a DNS rebinding-style proxy that can reach the port will pass.
  Mitigate by binding `FASTAPI_HOST` to localhost/private IPs or placing a
  proxy in front that validates `Host`.
- The CSP requires `'unsafe-inline'` scripts/styles because the frontend is a
  single inline-script HTML file (see above).
- `API_TOKEN` protects API routes only; `/health` and the frontend remain
  public by design.
- File-tool sandbox is a per-path containment, not a container/OS sandbox —
  a compromised tool cannot escape the allowed bases, but bases themselves
  are real user directories.
