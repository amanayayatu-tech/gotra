# GOTRA Full-Analyst Candidate Rollback

This runbook only affects the independent full-analyst production candidate.
It does not delete historical public reports and must not change the five daily
stock-pool timers.

## Stop The Candidate

```bash
sudo systemctl disable --now gotra-full-analyst-evening-hk-candidate.timer
sudo systemctl stop gotra-full-analyst-evening-hk-candidate.service
```

## Downgrade Concurrency

Edit `/etc/systemd/system/gotra-full-analyst-evening-hk-candidate.service` and
change:

```text
--max-concurrency 3
```

to:

```text
--max-concurrency 1
```

Then reload and restart only the candidate timer:

```bash
sudo systemctl daemon-reload
sudo systemctl restart gotra-full-analyst-evening-hk-candidate.timer
```

## Verify Daily Timers Are Still Active

```bash
systemctl list-timers "gotra*" --all --no-pager
```

Expected: the five daily stock-pool timers remain active/enabled:

- `gotra-stock-pool-hk-morning-report.timer`
- `gotra-stock-pool-hk-evening-report.timer`
- `gotra-stock-pool-us-morning-report.timer`
- `gotra-stock-pool-us-evening-report.timer`
- `gotra-stock-pool-global-summary-report.timer`

## Verify Public Artifacts

```bash
curl -fsS https://gotra.me/api/health
curl -fsS https://gotra.me/reports
curl -fsS https://gotra.me/reports/status_full_analyst_monitor.json
```

Rollback does not remove old full-analyst reports. It only disables or slows
future candidate runs.

## Evidence Boundary

This rollback surface is operational control for a production canary. It only
documents how an operator stops or slows the candidate timer; it does not
evaluate model quality or recommend any market action.
