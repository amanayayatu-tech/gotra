# Stage 3 Evidence Manifest 2026-06-15

This manifest records the evidence used to freeze Stage 3 as A-class gate failure and
negative/mixed scientific result. Runtime artifacts and bundles remain ignored and are not tracked
by git.

## Tracked Verdict

- Verdict document: `docs/STAGE3_FINAL_VERDICT_20260615.md`
- Manifest document: `docs/STAGE3_EVIDENCE_MANIFEST_20260615.md`

## Runtime Evidence

| Purpose | Path | SHA-256 |
| --- | --- | --- |
| Formal Stage 3 summary | `/Users/peachy/Documents/gotra-BT-full-monthly/data/backtest/runs/bt_full_v3_20260615/summary.json` | `13292c33710de05bb222d12c175e0ecf832cf6ca697d78724b1a988cbf3ac54b` |
| Formal Stage 3 system health | `/Users/peachy/Documents/gotra-BT-full-monthly/data/backtest/runs/bt_full_v3_20260615/system_health.json` | `9eef7bc855c63323aa46347421a137f76d38d0ca6c2ce60ffbf1a7781b7dffdf` |
| Canonical baseline replay summary | `data/backtest/runs/bt_baseline_parallel_replay4_20260615/summary.json` | `ef64d96e50971909b6f6ec2719716ec031a2c534da107b6a772f73293b6a970b` |
| Canonical baseline replay system health | `data/backtest/runs/bt_baseline_parallel_replay4_20260615/system_health.json` | `e148742a882ffcf9eeaa48bfd196b789418b11687ada1eb5f67e1864af7c6a81` |
| Canonical baseline replay quality summary | `data/backtest/runs/bt_baseline_parallel_replay4_20260615/quality_summary.json` | `5a7d0a3d874056a01a5b6854a65115d37ea98d71f9afcd147a1b7e867c1b5761` |
| Baseline replay compare | `data/backtest/runs/bt_baseline_parallel_replay4_20260615/compare_bt_full_v3_20260615.json` | `7edfba19c8d2d7b525aaf79dfc8e2c2769f2e2832055c950328a7bc9f07ee75a` |
| Provider determinism gate summary | `data/backtest/runs/stage3_provider_gate_check_20260615/summary.json` | `3174b8356fc9b278e0cb63cd7300d671f65f3a792ab71487a5d63f6537835e28` |
| Provider determinism gate system health | `data/backtest/runs/stage3_provider_gate_check_20260615/system_health.json` | `70e155c949f089e80e8366af4afe3ee9fb848462b78ef4976abb0122f315336e` |
| Provider determinism gate quality summary | `data/backtest/runs/stage3_provider_gate_check_20260615/quality_summary.json` | `63afbf7a110b879bff8af6ef442b9fb928d583ffa00cd06b5f79879daaf5d5ab` |

## Key Metrics

- Formal Stage 3 run: `steps_written=2012`, `provider_errors=0`, `audit.ok=true`,
  `system_health.status=ok`.
- Canonical baseline replay: `steps_written=1006`, `provider_errors=0`, `cache_hits=0`,
  `audit.ok=true`, `system_health.status=ok`.
- Baseline replay agreement: `846/1006 = 84.10%`, threshold `95%`, `passed=false`.
- Provider determinism gate: `system_health.status=blocked_provider_determinism`,
  `steps_written=0`, `provider_errors=0`.
- H1: FAIL.
- H2: mixed, four of five windows pass and COVID shock fails.
- H3: FAIL, `p_value=0.08340848`.

## Local Bundle

The local ignored evidence bundle is:

```text
STAGE3_FINAL_EVIDENCE_20260615.tar.gz
```

It is intentionally not tracked by git. Recompute its hash locally after packaging if needed:

```bash
shasum -a 256 STAGE3_FINAL_EVIDENCE_20260615.tar.gz
```
