# Stage 6 Evidence Manifest

Legacy salvage note: this document is preserved as a historical Stage6 evidence record from a
legacy PR. It is not a new experiment, not a current-main reproducibility claim, not
OOS/science/public proof, and not trading/investment advice.

Generated at: `2026-06-17 16:52:39 CST (+0800)`

This manifest records the evidence for the Stage 6 failure verdict. Run directories, SQLite ledgers,
price caches, and generated reports remain untracked.

## Commits

| Commit | Purpose |
|---|---|
| `b054b74` | `stage6: preregister dead-zone experiment` |
| `4a6d181` | `stage6: dead-zone estimator + total deadline + bounded concurrency` |
| `52965fe` | `stage6: share codex response connection limiter` |
| `b7c8d6a` | `stage6: compare paired successful replay points` |

## Replay Evidence

| Metric | Value |
|---|---:|
| final HK-inclusive agreement | `118 / 126 = 0.9365079365` |
| threshold | `0.95` |
| final A-class replay result | FAIL |
| auxiliary paired-success-only agreement | `102 / 107 = 0.9532710280` |
| auxiliary paired-success-only result | PASS |

The auxiliary paired-success-only compare is retained as a diagnostic artifact, but it is not used to
override the final HK-inclusive A-class replay failure.

## Full Run Evidence

| Metric | Value |
|---|---:|
| run id | `stage6_full_n5_deadzone_aggressive_20260616` |
| mode | `full` |
| provider | `codex_responses` |
| N | `5` |
| dead-zone epsilon | `0.3` percentage points |
| steps_written | `2012` |
| scored_steps | `1761` |
| paired_steps | `866` |
| provider_errors | `251` |
| audit.ok | `true` |
| token spent | `38359805` |
| H3 mean_loss_diff | `-1.044412` |
| H3 z_score | `-0.664089` |
| H3 p_value | `0.50663356` |
| H3 passed | `false` |

## Provider Error Distribution

| Dimension | Value | Count |
|---|---|---:|
| kind | `provider_limit_429` | `95` |
| kind | `transport_proxy_error` | `107` |
| kind | `transport_connect_error` | `29` |
| kind | `transport_remote_protocol_error` | `1` |
| kind | `transport_timeout` | `19` |
| kind | model content parse/schema failure | `0` |
| arm | `baseline` | `120` |
| arm | `alaya` | `131` |
| ticker | `0700.HK` | `17` |
| ticker | `1211.HK` | `20` |
| ticker | `1810.HK` | `14` |
| ticker | `3690.HK` | `21` |
| ticker | `6060.HK` | `33` |
| ticker | `9988.HK` | `27` |
| ticker | `AAPL` | `43` |
| ticker | `MSFT` | `49` |
| ticker | `NVDA` | `27` |

## Artifacts

| Artifact | Path | SHA-256 |
|---|---|---|
| Stage 6 preregistration | `data/backtest/STAGE6_PREREGISTERED.md` | `a01ccc440dbf7332c6842be3222a54d83803430c2517534632a6db36783a68d6` |
| Replay run 1 summary | `data/backtest/runs/stage6_repro_n5_deadzone_aggressive_run1_20260616/summary.json` | `ff63699558f3853321681edcd7cc7f4adf651cf76f87e4f0e17cfc73b40a4dc5` |
| Replay run 1 system health | `data/backtest/runs/stage6_repro_n5_deadzone_aggressive_run1_20260616/system_health.json` | `8cee089998d18aa7843ce480fe8d2de2194e3783ea5739ffbed86178a17edb31` |
| Replay run 2 summary | `data/backtest/runs/stage6_repro_n5_deadzone_aggressive_run2_20260616/summary.json` | `bef44854d1cb4d20e6fa5aaa53b16636083ed80d737b426bef023d14efc0a72a` |
| Replay run 2 system health | `data/backtest/runs/stage6_repro_n5_deadzone_aggressive_run2_20260616/system_health.json` | `402bebfdfbb514822c2b7e9faa3bc78954d88ff209b85fadb90e6c52200b11ee` |
| Auxiliary paired-success-only compare | `data/backtest/runs/stage6_repro_n5_deadzone_aggressive_compare_20260616.json` | `200bad867dd15bc3ec94334d6a4959b2877846894d28a071b9eb3545847ed2f5` |
| Full run summary | `data/backtest/runs/stage6_full_n5_deadzone_aggressive_20260616/summary.json` | `f9bf5d69b22fda174aa98a5894dd41e2dba049accbae523038e720aedd045547` |
| Full run system health | `data/backtest/runs/stage6_full_n5_deadzone_aggressive_20260616/system_health.json` | `7f580aa4b01028513eff907b11d64c55ced06b2ae74d59466780ce417b00b694` |
| Full run quality summary | `data/backtest/runs/stage6_full_n5_deadzone_aggressive_20260616/quality_summary.json` | `caaed330f6ebda018d201cbf135f8268e570a130d20aa728783b6bc02bae1163` |
| Full run provider-error manifest | `data/backtest/runs/stage6_full_n5_deadzone_aggressive_20260616/provider_error_manifest_stage6_full_n5_deadzone_aggressive_20260617.csv` | `e32095f71e9edcee2ebbe7e5ce0d67d46fb0cc89671468cf854296fe6a361760` |
| Stopped repair plan | `data/backtest/runs/stage6_full_n5_deadzone_aggressive_repair_20260617/repair_plan_stage6_full_n5_deadzone_aggressive_20260617.csv` | `e9bb348db10bbcf91e41b723c095e75d4ada21064180588f22924c77ad9d8a68` |

## Repair Run Note

The repair run `stage6_full_n5_deadzone_aggressive_repair_20260617` was stopped by operator
instruction after `6 / 120` planned baseline repair files had been written. It is not used for the
Stage 6 final verdict, and no run directory was deleted.

## Artifact Hygiene

The following paths are intentionally not tracked by git:

- `data/backtest/prices/`
- `data/backtest/runs/`
- SQLite ledgers under run directories
- generated Markdown/SVG reports under run directories
- temporary stdout/stderr or probe artifacts
