# GOTRA v3.8I End-to-End Connectivity Replay Prereg

Date: 2026-06-22

## Scope

v3.8I is a deterministic/local bounded connectivity replay for the already merged v3.8B-v3.8H engineering evidence chain.

It does not make new provider/backend calls, does not execute a provider canary, does not run a real 30D verdict path, does not score outcomes, and does not emit a comparative result.

Evidence layer: `engineering_internal_end_to_end_connectivity_replay`.

## Canonical Replay Chain

The replay binds these source stages in order:

| Stage | PR | Required status | Head | Merge commit | Calls | Tokens |
| --- | ---: | --- | --- | --- | ---: | ---: |
| v3.8B | #66 | `REAL_CONNECTION_AUTH_READY` | `c09060b95666d7760c4529eb66271298638d75bf` | `e974420eb2090f541f20d694444d184019f82dca` | 1 | 86 |
| v3.8C | #67 | `KSANA_PACKET_V2_REAL_TOKEN_CANARY_PASS` | `96406a6dda3daa4e682aea1329eb1c63ebfeb78f` | `9d554e48294e74f9af22a72c93bab6f3c6c8c37a` | 3 | 6518 |
| v3.8D | #68 | `GOTRA_ORCHESTRATOR_REAL_TOKEN_DRY_RUN_PASS` | `bdf5997a4ca881125878879f7d1f06db349ff257` | `b92be9870db661dd27015f4e8dcccd5d7235541e` | 3 | 6765 |
| v3.8E | #69 | `REAL_TOKEN_FAILURE_MODE_SUITE_PASS` | `500649a51816fef338e941b0790cc3a5a01ac0a7` | `cce6cec18ba856d986e8144d8e7915c37d6c9822` | 0 | 0 |
| v3.8F | #70 | `REAL_CONNECTION_EVIDENCE_DASHBOARD_READY` | `16cb7283f7dd280685aacafd137b663222d3e2fa` | `069aba13405928249f70f2f9bc5bafb01af641f5` | 0 | 0 |
| v3.8G | #71 | `PROVIDER_CANARY_PREREG_READY` | `c86719c1e70746568950fb7d1e097b16bae307e3` | `050a070f3f6bc10c3f1c18b9a31ba4ff46280e9c` | 0 | 0 |
| v3.8H | #72 | `PROVIDER_CANARY_AUTHORIZATION_GATE_READY` | `b825341cf90dcb2859920ec46bb9a1257eabec22` | `3321e870d99df935201a91294ee767be0edf541c` | 0 | 0 |

The derived chain is v3.8B -> v3.8C -> v3.8D -> v3.8E -> v3.8F -> v3.8G -> v3.8H.

## Required Boundary Fields

The replay summary must include:

- `replay_status`
- `engineering_connectivity_status`
- `cognitive_lift_candidate_status`
- `cognitive_lift_superiority_verdict_status=NOT_YET_VERDICT_READY`
- `actual_30d_readiness_status=DATA_NOT_MATURED`
- `next_check_after=2026-07-21T00:00:00Z`
- `v3_7_actual_verdict_executable=false`
- `v3_7_actual_verdict_executed=false`
- `provider_or_backend_called=false` for v3.8I itself
- `provider_canary_executed=false`
- `codex_cli_new_call=false`
- `formal_lite_entered=false`
- `raw_tmp_only=true`
- `no_raw_repo=true`
- `direct_llm_interpretation=direct_llm_parametric_memory_control`

## Blockers

The replay must block missing stages, swapped PR/head/merge identity, inconsistent call/token totals, malformed hashes or timestamps, non-`/tmp` raw references, forbidden committed artifacts, unsafe runtime flags, provider canary execution, actual verdict execution, 30D readiness bypass wording, or overclaim wording.

## Allowed Statuses

- `END_TO_END_CONNECTIVITY_READY`
- `BLOCKED_SCHEMA`
- `BLOCKED_PROVENANCE`
- `BLOCKED_CLAIM_BOUNDARY`
- `BLOCKED_RUNTIME_BOUNDARY`
- `BLOCKED_ARTIFACT_BOUNDARY`
- `BLOCKED_METADATA`

`END_TO_END_CONNECTIVITY_READY` is an engineering connectivity conclusion only. It is not an actual 30D verdict, not provider canary execution, not a comparative result, not an OOS/science/public/trading claim, and not investment advice.
