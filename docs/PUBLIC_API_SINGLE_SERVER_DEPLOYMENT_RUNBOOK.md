# GOTRA Public API Single-Server Deployment Runbook

This runbook documents the current single-server public deployment for the
GOTRA Public Ledger. It intentionally excludes domain setup, HTTPS certificate
issuance, and any private ResearchOS Web UI exposure.

## Architecture

- Nginx serves the frontend at `/`.
- Nginx proxies `/api/` to the local public API adapter.
- `gotra-public-api` listens on `127.0.0.1:3000`.
- The private ResearchOS Web UI is not exposed.
- The public API adapter is read-only and public-safe.

Request flow:

```text
public HTTP :80
  -> Nginx
    -> /      -> /var/www/gotra-public-ledger
    -> /api/ -> http://127.0.0.1:3000
```

## Current Server Paths

- Backend repository: `/opt/gotra`
- Frontend repository: `/opt/gotra-public-ledger`
- Frontend web root: `/var/www/gotra-public-ledger`
- Nginx site config: `/etc/nginx/sites-available/gotra-public-ledger`
- Systemd service: `/etc/systemd/system/gotra-public-api.service`

## Public API Adapter

Service name: `gotra-public-api`

Expected listener:

```bash
ss -lntp | grep -E '3000|7777' || true
```

Expected result:

- `127.0.0.1:3000` is listening.
- `0.0.0.0:3000` is not listening.
- `7777` is not publicly exposed and should not be listening for this public
  deployment.

Public endpoints:

- `GET /api/health`
- `GET /api/research-universe`
- `GET /api/public-ledger/status`

Private ResearchOS endpoints must remain unavailable from the public Nginx API
surface, including:

- `/api/env`
- `/api/llm/health`
- `/api/stock-pool`
- `/api/run-stream`
- `/api/agent-stream`
- `/api/research-scan-stream`
- `/api/codex/login-stream`
- `/api/deep-research/rerun-stream`
- `/api/cleanup`

## Restart Commands

Restart and inspect the public API adapter:

```bash
sudo systemctl restart gotra-public-api
sudo systemctl status gotra-public-api --no-pager
```

Validate and reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Smoke Commands

Local backend health:

```bash
curl -i http://127.0.0.1:3000/api/health
```

Local backend research universe:

```bash
curl -i http://127.0.0.1:3000/api/research-universe | head -80
```

Local backend public-ledger status:

```bash
curl -i http://127.0.0.1:3000/api/public-ledger/status
```

Public API health through Nginx:

```bash
curl -i http://47.251.249.147/api/health
```

Public research universe through Nginx:

```bash
curl -i http://47.251.249.147/api/research-universe | head -80
```

Frontend root and SPA routes:

```bash
curl -I http://47.251.249.147/
curl -I http://47.251.249.147/ledger
curl -I http://47.251.249.147/system
curl -I http://47.251.249.147/notes
```

## Security Checks

Confirm the API adapter is localhost-only:

```bash
ss -lntp | grep -E '3000|7777' || true
```

Confirm no environment or database files are in the web root:

```bash
find /var/www/gotra-public-ledger \
  \( -name '.env*' -o -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) \
  -print
```

Confirm private API routes are not exposed through Nginx:

```bash
for path in \
  /api/env \
  /api/llm/health \
  /api/stock-pool \
  /api/run-stream \
  /api/agent-stream \
  /api/research-scan-stream \
  /api/codex/login-stream \
  /api/deep-research/rerun-stream \
  /api/cleanup
do
  printf '%s ' "$path"
  curl -sS -o /dev/null -w '%{http_code}\n' "http://47.251.249.147$path"
done
```

Expected result: each `/api/...` private route returns `404`.

Check the staged code before committing:

```bash
git diff --cached | rg -n \
  'OPENAI''_API_KEY|ADMIN''_SMOKE_TOKEN|sk-[A-Za-z0-9]|BEGIN PRIVATE'' KEY|PRIVATE'' KEY|password\s*=|secret\s*=|token\s*=' \
  || true
```

## Current Limitations

- HTTPS is pending.
- Domain and DNS setup are pending.
- Public API rate limiting is not implemented yet.
- Frontend dependency audit currently reports 17 moderate findings.
- This public adapter exposes a static read-only research universe, not a
  private workflow UI and not a live provider/model integration.

## Public Boundary

All public responses from this adapter are bounded as:

- Research information only.
- Not investment advice.
- Not a trading signal.
- Not performance proof.
- Not live trading.
- No guarantee of future performance.
