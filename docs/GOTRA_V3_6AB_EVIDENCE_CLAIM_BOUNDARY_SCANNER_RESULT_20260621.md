# GOTRA v3.6AB Evidence Claim Boundary Scanner Result

Date: 2026-06-21 Asia/Shanghai

## Scope

Evidence layer: `engineering_claim_boundary_scan`.

This result records local fixture validation of the v3.6AB evidence-claim
boundary scanner. It does not call any provider, does not call Codex CLI, does
not run formal-lite, does not score outcomes, and does not execute v3.7.

This is not OOS evidence, not science/public proof, and not trading or
investment advice. Historical `direct_llm` remains
`direct_llm_parametric_memory_control`.

## Branch And Base

- Repo: `/Users/peachy/Documents/gotra`
- Base/head source: PR #42
  `codex/gotra-v3-6aa-stack-evidence-boundary-audit-20260621 @ 1e3a0fc77f36949e2ac28e3b68c9a7a8c7f95c78`
- Branch:
  `codex/gotra-v3-6ab-evidence-claim-boundary-scanner-20260621`
- Target PR base:
  `codex/gotra-v3-6aa-stack-evidence-boundary-audit-20260621`

## Local Fixture Scan

Command:

```bash
uv run python scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py \
  --scan-run-id baseline_v3_6ab_evidence_claim_boundary_scan_reviewfix_20260621T072258Z \
  --manifest /tmp/gotra_v3_6ab_claim_boundary_scan_reviewfix_20260621T072258Z/claim_boundary_manifest.json \
  --output-dir /tmp/gotra_v3_6ab_claim_boundary_scan_reviewfix_20260621T072258Z/runs
```

Output, not committed:

`/tmp/gotra_v3_6ab_claim_boundary_scan_reviewfix_20260621T072258Z/runs/baseline_v3_6ab_evidence_claim_boundary_scan_reviewfix_20260621T072258Z/summary.json`

Summary sha256:

`fa39a03abd9b9945eabaf1b4e3cf8c924ac7fca4ac9fec27cdab2ad72a165dc1`

Result:

- Overall status: `CLAIM_BOUNDARY_CLEAN`
- Scanned file count: `2`
- Forbidden path count: `0`
- Evidence overclaim count: `0`
- Direct LLM mislabel count: `0`
- Maturity gate bypass count: `0`
- Short-horizon-as-30D count: `0`
- Warning count: `0`
- Provider/backend called: `false`
- New Codex CLI call: `false`
- Formal-lite entered: `false`
- v3.7 allowed: `false`

Interpretation: the fixture demonstrates that the scanner accepts explicit
engineering/local non-claim wording and blocks only clear boundary violations.
It does not imply 30D readiness and does not authorize v3.7.

## Local Validation

Commands run:

```bash
uv run python -m py_compile scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py
uv run ruff check --no-cache scripts/baseline_v3_6ab_evidence_claim_boundary_scanner.py tests/test_evidence_claim_boundary_scanner.py
uv run pytest -q tests/test_evidence_claim_boundary_scanner.py
uv run pytest -q tests/test_evidence_claim_boundary_scanner.py tests/test_stack_evidence_boundary_audit.py tests/test_evidence_package_dashboard.py
uv run pytest -q
git diff --check
```

Result:

- py_compile: pass
- Ruff: pass
- Focused tests: `20 passed`
- v3.6AA/v3.6AB/v3.6X regression tests: `42 passed`
- Full test suite: `454 passed`
- `git diff --check`: pass

Covered behavior:

- clean engineering/local docs fixture -> `CLAIM_BOUNDARY_CLEAN`
- negative non-claim statements do not block
- OOS/science/public/trading/investment overclaim blocks
- OOS/public `evidence` claims block unless specifically negated
- `direct_llm` without `direct_llm_parametric_memory_control` blocks
- `direct_llm_parametric_memory_control` is accepted
- `direct_llm_parametric_memory_control is not a clean no-future baseline` is accepted
- short-horizon canary as 30D verdict / v3.7 allowed blocks
- 30D verdict/pass while readiness is not true READY blocks
- same-line caveats do not mask maturity-gate/v3.7 claims
- quoted `v3_7_allowed: true`, underscore/dot/plain v3.7 wording blocks
- explicit false forms such as `v3.7 verdict allowed: false` are accepted
- forbidden path manifest entries block
- forbidden `--file` and `--manifest` paths are blocked before read
- provider/canary evidence as public proof blocks
- no provider, no new Codex CLI call, no formal-lite

## Artifact Boundary

The local scan output is stored under `/tmp` and is not committed. No
`data/backtest/runs/**`, `data/paper_trading/**`, raw outputs, transcripts,
`.env*`, SQLite/DB, bundle/tar/zip, Stage8/Stage9 local artifacts, or README
changes are intended for commit.

## Next Action

Do not execute v3.7. Continue stack monitoring or maturity rechecks only under
separate authorization. The 30D path remains blocked until true actual readiness
returns `READY_FOR_FORWARD_LIVE_VERDICT` with matching provenance.
