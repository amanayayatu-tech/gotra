# GOTRA v3.6AB Evidence Claim Boundary Scanner Prereg

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_claim_boundary_scan`.

This stage adds a local evidence-claim boundary scanner / preflight guard. It
scans committed docs/scripts or fixture text for evidence overclaim,
`direct_llm` mislabeling, 30D maturity-gate bypass, short-horizon-as-30D
wording, and forbidden artifact paths.

It does not call Kimi/GLM/DeepSeek providers, does not call Codex CLI, does not
run formal-lite, does not score outcomes, does not merge PRs, and does not
execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` must remain
`direct_llm_parametric_memory_control`.

## Inputs

The scanner supports:

- `--file` repeated for committed docs/scripts.
- `--manifest` for JSON fixtures containing `files` with `path` + `text`, plus
  optional changed file lists.

Forbidden artifact paths are blocked by path before content is read. The scanner
must not read raw transcripts, provider raw outputs, `data/backtest/runs/**`,
`data/paper_trading/**`, `.env*`, DB files, bundles, or Stage8/Stage9 local
artifacts.

## Blocking Rules

The scanner blocks on:

- OOS/science/public/trading/investment overclaim:
  `CLAIM_BOUNDARY_BLOCKED_OVERCLAIM`
- provider/runtime/canary/tiny/formal-lite/internal evidence written as a
  science/public/trading claim: `CLAIM_BOUNDARY_BLOCKED_OVERCLAIM`
- `direct_llm` without `direct_llm_parametric_memory_control`, or `direct_llm`
  described as a clean no-future baseline:
  `CLAIM_BOUNDARY_BLOCKED_DIRECT_LLM`
- short-horizon canary outcome described as 30D verdict / v3.7 allowed:
  `CLAIM_BOUNDARY_BLOCKED_MATURITY_GATE`
- 30D forward-live verdict/pass while true readiness is not known to be
  `READY_FOR_FORWARD_LIVE_VERDICT`:
  `CLAIM_BOUNDARY_BLOCKED_MATURITY_GATE`
- forbidden artifact paths:
  `CLAIM_BOUNDARY_BLOCKED_ARTIFACT`

The scanner should avoid false positives for explicit non-claim statements such
as `not OOS/science/public/trading claim`, `not investment advice`,
`engineering/local only`, `historical/internal only`, `v3_7_allowed=false`, and
`direct_llm_parametric_memory_control`.

Ambiguous wording may produce warnings, but only clear boundary violations
block.

## Summary Contract

The summary includes:

- `schema`
- `scan_run_id`
- `scan_timestamp_utc`
- `scanned_file_count`
- `forbidden_path_count`
- `evidence_overclaim_count`
- `direct_llm_mislabel_count`
- `maturity_gate_bypass_count`
- `short_horizon_as_30d_count`
- `warning_count`
- `blocked_items` with path, line number, rule id, and short reason
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `v3_7_allowed=false`
- `evidence_layer=engineering_claim_boundary_scan`
- `overall_status`

`CLAIM_BOUNDARY_CLEAN` means only that this local claim-boundary scan is clean.
It does not mean 30D readiness is ready and does not authorize v3.7.

## Next Boundary

v3.7 remains forbidden until true 30D actual readiness returns
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance. A clean claim scan,
clean stack, or short-horizon canary cannot substitute for the 30D maturity
gate.
