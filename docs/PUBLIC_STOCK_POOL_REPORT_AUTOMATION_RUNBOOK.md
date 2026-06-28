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
- Public API: unchanged
- Private ResearchOS UI: not exposed

The report script writes Markdown and JSON artifacts only. It does not call LLM
providers, read `.env` files, expose private workflow state, create orders, or
generate buy/sell/hold/position instructions.

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
`missing_symbols`, `source`, public-safety boundary text, and generated time.

## Timers

Install the templates from `ops/systemd/` on the server:

```bash
sudo cp ops/systemd/gotra-stock-pool-*.service /etc/systemd/system/
sudo cp ops/systemd/gotra-stock-pool-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
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
systemctl list-timers --all | grep gotra-stock-pool
```

## Nginx Route

The frontend route `/reports` is a React route. Add the exact-location snippet
from `ops/nginx/gotra-public-ledger-reports.locations.conf` before the general
SPA fallback in `/etc/nginx/sites-available/gotra-public-ledger`:

```nginx
location = /reports {
    try_files /index.html =404;
}

location = /reports/ {
    try_files /index.html =404;
}
```

Then validate and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
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
  'OPENAI_API_KEY|ADMIN_SMOKE_TOKEN|sk-[A-Za-z0-9]|Bearer |Authorization|BEGIN PRIVATE KEY|PRIVATE KEY|password\s*=|secret\s*=|token\s*=' \
  /opt/gotra/data/reports /var/www/gotra-public-ledger/reports \
  || true
```

The reports should not contain raw Yahoo URLs, raw provider metadata, prompts,
completions, messages, or hidden model/provider I/O.

## Known Limitations

- Holiday calendars are approximated by weekdays unless dates are overridden.
- Yahoo Finance availability can be delayed or partial; coverage must be read
  from `status.json`.
- HTTPS, domain/DNS, and public API rate limiting are pending.
- This is runtime/status evidence only. It does not satisfy any preregistered
  GOTRA gate and must remain below claims about model quality or future outcomes.
