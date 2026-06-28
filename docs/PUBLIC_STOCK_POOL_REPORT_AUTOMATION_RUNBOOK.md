# GOTRA Public Stock-Pool Report Automation Runbook

This runbook documents the local single-server automation that generates and
publishes public-safe stock-pool reports for the GOTRA public ledger frontend.
It preserves the same boundary as the public API adapter: research information
only, not investment advice, not a trading signal, and not performance proof.

## Scope

- Backend repository: `/opt/gotra`
- Frontend repository: `/opt/gotra-public-ledger`
- Static report source: `/opt/gotra/data/reports/`
- Static web target: `/var/www/gotra-public-ledger/reports/`
- Public frontend route: `/reports`
- Public API adapter: `gotra-public-api.service`
- Private ResearchOS UI: not exposed

The report script writes Markdown and JSON artifacts only. It does not call LLM
providers, read `.env` files, expose private workflow state, create orders, or
generate buy/sell/hold/position instructions.

## Production Runtime Boundary

These files are Git-tracked templates for the current production runtime. They
are not `/etc` snapshots and do not include certificates, private key material,
credential values, environment files, or local machine logs.

- `ops/systemd/gotra-public-api.service`
- `ops/systemd/gotra-stock-pool-morning-report.service`
- `ops/systemd/gotra-stock-pool-morning-report.timer`
- `ops/systemd/gotra-stock-pool-evening-report.service`
- `ops/systemd/gotra-stock-pool-evening-report.timer`

Runtime invariants:

- `gotra-public-api.service` must bind only `127.0.0.1:3000`.
- Public traffic reaches the API only through Nginx `/api/`.
- Port `7777` is not used by this public deployment and must not be opened to
  the public Internet.
- Public reports are static artifacts under `/var/www/gotra-public-ledger/reports/`.
- Public evidence from this runtime is `local checks` plus `server runtime
  evidence`; it is not science/public proof, performance proof, or a trading
  signal.

## Commands

Generate the full-market morning report:

```bash
cd /opt/gotra
/root/.local/bin/uv run python scripts/public_stock_pool_report.py \
  --mode morning-global \
  --publish-static
```

Generate the HK evening report:

```bash
cd /opt/gotra
/root/.local/bin/uv run python scripts/public_stock_pool_report.py \
  --mode evening-hk \
  --publish-static
```

Useful dry-run flags:

```bash
--as-of-date 2026-06-28
--trading-date 2026-06-26
--us-trading-date 2026-06-26
--report-dir /tmp/gotra-report-smoke
--static-dir /tmp/gotra-report-static
```

## Output Files

The script creates:

- `data/reports/public_stock_pool_eod_<trading_date>.md`
- `data/reports/latest.md`
- `data/reports/status.json`

When `--publish-static` is set, it also copies the same public-safe files to:

- `/var/www/gotra-public-ledger/reports/latest.md`
- `/var/www/gotra-public-ledger/reports/status.json`
- `/var/www/gotra-public-ledger/reports/public_stock_pool_eod_<trading_date>.md`

`status.json` includes `schema`, `mode`, `as_of_date`, `trading_date`,
per-exchange trading dates, `universe_count`, `success_count`, `failed_count`,
`missing_symbols`, `failed_symbols`, `run_status`, `artifact_write_status`,
`artifact_write_failure_reason`, `source`, public-safety boundary text, and
generated time. `missing_symbols` is retained for compatibility; use
`failed_symbols` for new checks.

## Observability And Failure Checks

systemd captures script logs in the service journal. Use these commands first
when a timer looks stale or a report is missing:

```bash
sudo journalctl -u gotra-stock-pool-morning-report.service -n 120 --no-pager
sudo journalctl -u gotra-stock-pool-evening-report.service -n 120 --no-pager
sudo journalctl -u gotra-stock-pool-morning-report.service --since "24 hours ago" --no-pager
sudo journalctl -u gotra-stock-pool-evening-report.service --since "24 hours ago" --no-pager
```

The journal should include start parameters, resolved trading dates, coverage,
failed-symbol summaries, artifact paths, and any `status.json write failed`
reason. If `status.json` itself cannot be written, the journal is the source of
truth for that write failure.

Check the current source status:

```bash
jq '{ok, run_status, mode, as_of_date, trading_date, success_count, failed_count, artifact_write_status, artifact_write_failure_reason}' \
  /opt/gotra/data/reports/status.json
```

List failed symbols:

```bash
jq -r '.failed_symbols[]? | [.exchange, .symbol, .provider_ticker, .reason] | @tsv' \
  /opt/gotra/data/reports/status.json
```

Check the public static status:

```bash
curl -fsS http://47.251.249.147/reports/status.json \
  | jq '{ok, run_status, mode, trading_date, success_count, failed_count, artifact_write_status, artifact_write_failure_reason}'

curl -fsS http://47.251.249.147/reports/status.json \
  | jq -r '.failed_symbols[]? | [.exchange, .symbol, .provider_ticker, .reason] | @tsv'
```

Current notification boundary: no email, Telegram, or Notion notification is
configured. The first operational alert surface is journal + `status.json`.

## Timers

Install the templates from `ops/systemd/` on the server:

```bash
cd /opt/gotra
sudo cp ops/systemd/gotra-stock-pool-*.service /etc/systemd/system/
sudo cp ops/systemd/gotra-stock-pool-*.timer /etc/systemd/system/
sudo cp ops/systemd/gotra-public-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gotra-public-api.service
sudo systemctl enable --now gotra-stock-pool-morning-report.timer
sudo systemctl enable --now gotra-stock-pool-evening-report.timer
```

Current schedules:

- `gotra-stock-pool-morning-report.timer`: `Tue..Sat *-*-* 10:30:00 Asia/Shanghai`
- `gotra-stock-pool-evening-report.timer`: `Mon..Fri *-*-* 18:30:00 Asia/Shanghai`

Validate calendar syntax and next runs:

```bash
systemd-analyze calendar 'Tue..Sat *-*-* 10:30:00 Asia/Shanghai'
systemd-analyze calendar 'Mon..Fri *-*-* 18:30:00 Asia/Shanghai'
systemctl list-timers --all "gotra-stock-pool-*" --no-pager
systemctl status gotra-stock-pool-morning-report.timer gotra-stock-pool-evening-report.timer --no-pager
```

## Runtime Status Commands

Check the public API service and listener:

```bash
systemctl status gotra-public-api.service --no-pager
ss -ltnp | grep -E ':(3000|7777)\b' || true
curl -fsS http://127.0.0.1:3000/api/health
```

Check report timers and journals:

```bash
systemctl list-timers --all "gotra-stock-pool-*" --no-pager
journalctl -u gotra-stock-pool-morning-report.service -n 120 --no-pager
journalctl -u gotra-stock-pool-evening-report.service -n 120 --no-pager
```

Check local and public status JSON:

```bash
jq '{ok, run_status, mode, as_of_date, trading_date, success_count, failed_count, artifact_write_status, artifact_write_failure_reason, failed_symbols}' \
  /opt/gotra/data/reports/status.json

curl -fsS http://47.251.249.147/reports/status.json \
  | jq '{ok, run_status, mode, as_of_date, trading_date, success_count, failed_count, artifact_write_status, artifact_write_failure_reason, failed_symbols}'
```

## Smoke Checks

Run the service manually:

```bash
sudo systemctl start gotra-stock-pool-morning-report.service
sudo systemctl status gotra-stock-pool-morning-report.service --no-pager
```

Check local artifacts:

```bash
test -s /opt/gotra/data/reports/latest.md
python3 -m json.tool /opt/gotra/data/reports/status.json >/dev/null
jq '.failed_symbols' /opt/gotra/data/reports/status.json
```

Check static frontend artifacts:

```bash
curl -I http://47.251.249.147/reports
curl -I http://47.251.249.147/reports/latest.md
curl -i http://47.251.249.147/reports/status.json
```

Check service and private-boundary health:

```bash
curl -i http://47.251.249.147/api/health
curl -i https://gotra.me/api/health
curl -I --connect-timeout 5 --max-time 8 http://47.251.249.147:3000/api/health
curl -I --connect-timeout 5 --max-time 8 http://47.251.249.147:7777/
```

Expected:

- `/reports`, `/reports/latest.md`, and `/reports/status.json` are public HTTP 200.
- `/api/health` remains public HTTP 200.
- Public ports `3000` and `7777` remain unreachable.
- No private ResearchOS UI or private API routes are exposed.

## Safety Scan

Scan generated reports before public exposure:

```bash
rg -n \
  'OPENAI''_API_KEY|ADMIN''_SMOKE_TOKEN|s''k-[A-Za-z0-9]|Bear''er |Authori''zation|BEGIN PRIVATE'' KEY|PRIVATE'' KEY|pass''word\s*=|sec''ret\s*=|to''ken\s*=' \
  /opt/gotra/data/reports /var/www/gotra-public-ledger/reports \
  || true
```

The reports should not contain raw Yahoo URLs, raw provider metadata, prompts,
completions, messages, or hidden model/provider I/O.

## Known Limitations

- Holiday calendars are approximated by weekdays unless dates are overridden.
- Yahoo Finance availability can be delayed or partial; coverage must be read
  from `status.json`.
- HTTPS, security headers, Nginx `/api/` rate limiting, `/data/` static 404
  behavior, and nftables edge blocking are owned by the public-ledger runtime
  templates in `/opt/gotra-public-ledger`.
- This is runtime/status evidence only. It does not satisfy any preregistered
  GOTRA gate and must remain below claims about model quality or future outcomes.
