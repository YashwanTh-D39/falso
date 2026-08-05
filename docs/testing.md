# Testing Guide

## Tooling

- **pytest** — test runner with `asyncio_mode = "auto"` (async tests need no
  decorators) and `testpaths = ["tests"]` (`pyproject.toml`).
- **pytest-asyncio** — async test support.
- **ruff** — linter; line length 100, target `py311`.

```bash
python -m pytest -q            # full suite (121 tests)
python -m pytest tests/test_security.py -q        # single file
python -m pytest tests/test_system_monitor.py::TestSystemMonitor -q  # class
python -m ruff check app config tests             # lint
```

## Suite overview

| File | Covers |
| --- | --- |
| `tests/test_security.py` | Token auth (constant-time `hmac.compare_digest`, both header forms), body-size limits, origin checks, security headers, middleware unit tests |
| `tests/test_system_monitor.py` | Background sampling, keep-last-good GPU on probe failure, snapshot isolation, interval validation, lifecycle (idempotent start, double stop, restart), missing `nvidia-smi`, battery/temperature degradation, CPU warm-up-then-delta, `/stats` route (cache-only, full JSON shape, never probes in request path) |
| `tests/test_conversations.py` | Conversations CRUD roundtrip over HTTP (save/list/get/delete), invalid-id rejection |
| `tests/test_file_tool.py` | File tool `execute` (write/read cycle, delete confirmation flow, non-empty dir, sandbox escape rejection, read/write size limits, search result cap, unknown command) and `match_prompt` intent parsing (list/read/write-with-quotes/delete/unrelated) |
| `tests/test_backend/test_brain.py` | `BrainService`: prompt validation, tool routing without LLM (time/system), pending-action confirmation flow, LLM streaming with a mocked httpx client, provider error surfacing, `ChatRequest` model limits (empty + 50 001-char prompts) |
| `tests/test_backend/test_providers.py` | Provider layer: OpenAI message mapping (system → instructions, turns → input), delta parsing (unified/legacy events), OpenAI streaming wire contract (single-flight lock release, missing-key rejection, error/failed response events), OpenAI error mapping (404/429/503 hints), Ollama NDJSON streaming, `build_provider()` factory (default `openai`, case-insensitive, unknown provider error) |

Suite status on the reference machine (Windows, Python 3.14.6): **121
passed, 1 skipped**, 1 expected `StarletteDeprecationWarning` (httpx vs httpx2
in starlette's TestClient — harmless), ruff clean.

## Conventions

- **No live services in tests.** No OpenAI, no Ollama, no real `nvidia-smi`,
  no real hardware: providers are exercised with scripted fakes
  (`FakeHttpStream`, `_FakeErrorEvent`/`_FakeFailedEvent`), `psutil` entry
  hardware: `psutil` entry points are stubbed with `monkeypatch`, and
  `subprocess.run` is either stubbed or booby-trapped
  (`tests/test_system_monitor.py` proves `/stats` never spawns a process).
- **Platform-aware stubs.** `psutil.sensors_*` do not exist on every
  platform (e.g. `sensors_temperatures` is absent on Windows). Stub them
  conditionally (`if hasattr(psutil, name)`).
- **Route tests use `fastapi.testclient.TestClient`** as a context manager so
  the lifespan (monitor start/stop) runs:
  ```python
  with TestClient(main_module.app) as client:
      r = client.get("/api/v1/system/stats")
  ```
- **Patching route dependencies:** patch the *name in the route module*
  (e.g. `system_module.system_monitor`) rather than the singleton's class.
- **Streaming is tested at the unit level.** Starlette's TestClient coalesces
  chunked streamed bodies, so mid-stream behavior (e.g. the 413 cut-off
  proof) is tested with scripted ASGI `receive` callables in
  `tests/test_security.py`.
- **State cleanup:** conversation tests use unique ids
  (`uuid.uuid4().hex[:8]`) and delete what they create.

## Adding a test

1. Match an existing file by area, or create `tests/test_<module>.py`.
2. Prefer monkeypatched stubs over real I/O.
3. Verify: `python -m pytest -q` and `python -m ruff check app config tests`.
