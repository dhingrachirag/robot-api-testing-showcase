# Robot Framework API Testing Showcase

A small, self-contained REST API test framework built with **Robot Framework** and **Python**.
It shows patterns I use for reliable, fast, easy-to-debug API automation, and it runs
against a bundled mock API, so anyone can clone it and see every test pass in seconds.

## What it demonstrates

| Pattern | Where | Why it matters |
|---|---|---|
| **Session reuse** | `libraries/ApiLibrary.py` | One pooled `requests.Session` per suite, so keep-alive connections skip repeated TCP/TLS handshakes. |
| **Async polling with exponential backoff** | `libraries/polling.py` | Checks quickly at first, backs off on long jobs, and fails fast on terminal states like `failed`. |
| **Error classification** | `libraries/error_classifier.py` | Every result is tagged `OK`, `TIMEOUT`, `SERVER_ERROR`, `AUTH_ERROR` ... so reports are triaged by category instead of by stack trace. |
| **Smart retries** | `ApiLibrary.Send Request` | Retries only transient categories (5xx, 429, timeouts). A 404 or 422 fails immediately. |
| **Path-based JSON extraction** | `libraries/json_path.py` | `result.items[0].id` style lookups with clear errors. |
| **Keyword composition** | `resources/api_keywords.resource` | Tests read like specifications; HTTP details live in reusable keywords. |
| **Data-driven tests** | `tests/api/error_handling.robot` | One template, many cases. |
| **Mutual TLS / token auth via env vars** | `ApiLibrary._get_session` | Certificates and secrets are never stored in the repo. |
| **Unit-tested helpers** | `tests/unit/` | Polling is tested with a fake clock, so there's no real waiting. |

## Project layout

```
.
├── libraries/              # Python keyword library + pure helper modules
│   ├── ApiLibrary.py
│   ├── error_classifier.py
│   ├── json_path.py
│   └── polling.py
├── mock_server/app.py      # Dependency-free mock REST API (stdlib only)
├── resources/              # Reusable Robot keywords
├── tests/
│   ├── api/                # Robot Framework suites
│   └── unit/               # pytest unit tests
└── .github/workflows/ci.yml
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Robot suites (starts the mock API automatically)
robot --pythonpath . --outputdir results tests/api

# Unit tests
pytest tests/unit
```

Open `results/report.html` for the report and `results/log.html` for the per-request log
(method, URL, status, category, latency and attempt count).

### Run in parallel

```bash
pip install robotframework-pabot
pabot --pythonpath . --outputdir results tests/api
```

Each suite starts its own mock server on a free port, so suites run in parallel without clashing.

### Run against a real API

The suites target the mock server unless you set `API_BASE_URL`:

| Variable | Purpose |
|---|---|
| `API_BASE_URL` | Base URL of the API under test (skips the mock server) |
| `API_TIMEOUT` | Default request timeout in seconds (default `10`) |
| `API_TOKEN` | Sent as `Authorization: Bearer <token>` |
| `CLIENT_CERT` / `CLIENT_KEY` | PEM paths for mutual-TLS client authentication |
| `CA_BUNDLE` | Custom CA bundle for server verification |

Keep secrets in your CI's secret store or a local `.env`. Never commit them. `.gitignore`
already excludes common certificate and key formats.

## Example: polling an async job

```robotframework
Async Job Completes And Returns A Result
    ${final}=    Start Job And Wait Until Done    timeout=10
    Should Be Equal    ${final}[status]    done
```

The log shows every state seen while polling, e.g.
`Reached status=done after 4 polls (0.62s): ['queued', 'running', 'running', 'done']`.

## License

MIT, see [LICENSE](LICENSE).
