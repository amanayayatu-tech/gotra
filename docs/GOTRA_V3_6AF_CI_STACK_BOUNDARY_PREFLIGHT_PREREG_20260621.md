# GOTRA v3.6AF CI Stack Boundary Preflight Preregistration

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_ci_stack_boundary_preflight`.

This stage wires the v3.6AE continuous stack boundary guard into a lightweight
CI/local wrapper. It is a guardrail for tracked files, optional manifest
fixtures, and optional stack snapshots. It does not score outcomes, does not
run formal-lite, does not call providers, does not call Codex CLI, does not
merge PRs, and does not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`.

## Base Stack

The branch is stacked on PR #46:
`codex/gotra-v3-6ae-continuous-stack-boundary-guard-20260621`.

Open/unmerged stacked PRs are expected and are not blockers by themselves. Real
blockers remain CI failure, active P1/P2 review threads, topology or conflict
issues, artifact-boundary violations, evidence overclaims, maturity-gate
bypass wording, provider/Codex/formal-lite boundary violations, and schema
failures.

## Wrapper Contract

The v3.6AF command must reuse the v3.6AE guard rather than reimplementing
claim/artifact scanning. The wrapper is responsible for:

- collecting git tracked files only from explicitly supplied `--pathspec`
  values; with no `--pathspec`, the wrapper scans no broad historical file tree
  and only processes optional manifest/snapshot inputs
- counting skipped untracked files without reading them
- filtering gitlinks, directories, and non-regular files before passing paths to
  the v3.6AE guard
- passing tracked files, optional manifest, and optional snapshot into v3.6AE
- applying pre-read artifact guards to manifest and snapshot paths
- mapping v3.6AE terminal statuses to v3.6AF preflight statuses
- writing a machine-readable summary under `/tmp` or an explicit output root

The script-path CLI form
`python scripts/baseline_v3_6af_ci_stack_boundary_preflight.py` must work from
the repo root without requiring callers to set `PYTHONPATH=.`.

Duplicate output run ids must fail closed without overwriting existing
`summary.json` or `manifest.json` artifacts unless `--allow-overwrite` is
explicitly supplied.

Forbidden artifact paths include `data/backtest/runs/**`,
`data/paper_trading/**`, raw outputs, transcripts, `.env*`, SQLite/DB,
bundle/tar/zip, and Stage8/Stage9 artifacts.

## Summary Contract

The summary must include:

- `schema`
- `preflight_run_id`
- `scanned_tracked_file_count`
- `skipped_untracked_count`
- `pathspecs`
- `guard_summary_path`
- `guard_summary_sha256`
- `artifact_boundary_status`
- `claim_boundary_status`
- `maturity_gate_status`
- `direct_llm_boundary_status`
- `preflight_status`
- `ready_for_human_merge_review`
- `auto_merge_executed=false`
- `v3_7_allowed=false`
- `provider_or_backend_called=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `evidence_layer=engineering_ci_stack_boundary_preflight`
- `blocker_reasons`

Allowed terminal statuses:

- `CI_STACK_BOUNDARY_PREFLIGHT_CLEAN`
- `BLOCKED_ARTIFACT`
- `BLOCKED_CLAIM_BOUNDARY`
- `BLOCKED_MATURITY_GATE`
- `BLOCKED_DIRECT_LLM_BOUNDARY`
- `SNAPSHOT_INCOMPLETE`
- `PREFLIGHT_FAIL`

Clean status exits `0`; blocked/fail terminal statuses exit non-zero.

## CI Wiring Decision

This stage adds the wrapper and tests, but does not modify the existing GitHub
Actions workflow. The existing workflow already runs full repo Ruff and pytest.
Direct workflow wiring can be added later after the team chooses explicit
changed-file or scoped pathspecs to enforce in CI without false positives from
historical research docs.

## Non-Claims

This preflight may say the local/CI boundary guard is clean for the selected
inputs. It may not say:

- v3.7 is allowed
- 30D forward-live verdict is ready
- GOTRA has an OOS/science/public proof
- any trading or investment recommendation is supported
- `direct_llm` is a clean no-future baseline

v3.7 remains forbidden until true 30D actual readiness returns
`READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
