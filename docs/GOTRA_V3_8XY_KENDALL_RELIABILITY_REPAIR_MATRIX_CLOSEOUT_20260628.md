# GOTRA v3.8X/Y Kendall Reliability Repair Matrix Closeout

Date: `2026-06-28`

Status: `METHOD_DECISION_NOT_FORMALLY_ACCEPTED_UNDER_CURRENT_PROTOCOL`

Formal Phase 4 gate state preserved:

- `formal_phase4_gate_status=PHASE_4_BLOCKED_SCORER_RELIABILITY`
- `formal_phase4_pass=false`
- `formal_phase5_entered=false`
- No science, public, trading, or investment claim.

## Summary

GOTRA v3.8X/Y Kendall/scorer-reliability repair did not reach formal
acceptance. The repair loop produced useful diagnostic and runtime
improvements, including better low-dimension bucket spread in probes, role
symmetry improvements, stricter partial-output handling, and budget metadata
support for explicit unbounded user authorization. None of those improvements
created a formal Phase 4 pass.

The latest accepted Phase 3 source did not produce a passing Phase 4
reliability result. Later source-chain regeneration was blocked before a new
Reviewer-passed Phase 2/Phase 3 source chain could be re-established. This
document closes out the current open-ended repair loop for documentation and
GitHub synchronization only.

Public/science/trading claims remain disallowed. This document is engineering
and reliability closeout metadata, not evidence of GOTRA scientific success,
cognitive-lift superiority, production readiness, or investment value.

## Evidence Ladder

### local checks

Local checks include `codex-preflight --check --expect-project gotra`, targeted
`py_compile`, `ruff`, `pytest`, hash checks, safe JSON/JQ checks, repo raw
artifact scans, and `git diff --check` reported during Worker/Reviewer turns.
They establish local consistency of scripts, docs, tests, and safe artifact
metadata only.

### smoke/probe evidence

Probe evidence includes non-formal calibration and measurability probes, such
as `gotra_v3_8x_contrastive_pair_selection_by_low_dim_cues_probe_20260627T170000Z`.
Probe evidence can guide repair selection but cannot be promoted to Phase 3 or
Phase 4 formal acceptance.

### bounded batch/scale runtime evidence

Bounded batch/scale runtime evidence includes completed Phase 2 arm generation
attempts and Phase 3 scoring runtime scale attempts. A runtime artifact can be
used downstream only after its exact source artifact is Reviewer-passed and, if
required, recorded by State-Writer. Runtime `status=PASS` without Reviewer gate
is not formal acceptance.

### scorer reliability evidence

Scorer reliability evidence is Phase 4 evidence only. Phase 4 requires both
`icc_2_k >= icc_2_k_minimum=0.70` and
`kendall_tau >= kendall_tau_minimum=0.60`, then a Reviewer gate before formal
Phase 4 can be recorded.

### waived diagnostic downstream evidence

No waived diagnostic downstream evidence is used as formal evidence in this
closeout. Diagnostic downstream observations remain non-formal.

### long-run/formal acceptance

Formal acceptance was not reached. No Reviewer-passed fresh Phase 4 run met
both scorer reliability thresholds. No Phase 5/effective-N/verdict fan-in was
entered.

### science/public/trading claim

No science, public, trading, or investment claim is made. This closeout does
not establish `cognitive_lift_superiority`, a clean direct-LLM baseline, market
edge, production readiness, or a trading recommendation.

## Protocol And Thresholds

The relevant protocol layers were:

- Phase 2 source generation must produce complete arm outputs with stable
  source identity, safe summary/manifest metadata, raw outputs under
  `/tmp/gotra_rubric_reasoning_quality/**`, and no claim/raw boundary breach.
- Phase 3 scoring runtime must use a Reviewer-passed source, produce complete
  scored records and safe manifests, and preserve source identity and budget
  metadata.
- Reviewer gates are required before a fresh Phase 2 or Phase 3 source is used
  for the next formal stage.
- State-Writer gates record only the reviewed gate layer and must not promote
  downstream phases.
- Phase 4 reliability requires both `icc_2_k_minimum=0.70` and
  `kendall_tau_minimum=0.60`.
- Thresholds were not relaxed.
- Phase 5 is forbidden unless a fresh Phase 4 reliability run meets both
  thresholds and receives `REVIEW_PASS` or `REVIEW_PASS_WITH_LIMITATION`.

## Chronology Of Main Runs

### Phase 4 blocked, 2026-06-26

- Run id:
  `gotra_v3_8y_rubric_reasoning_scorer_reliability_20260626T115500Z_scale`
- Evidence layer: scorer reliability evidence.
- `icc_2_k=0.785802 >= icc_2_k_minimum=0.70`
- `kendall_tau=0.483723 < kendall_tau_minimum=0.60`
- Blocker: `scorer_reliability_kendall_tau_below_threshold`
- Outcome: not formal Phase 4 pass because `kendall_tau` failed.

### Phase 3 pass with limitation, 2026-06-26

- Run id:
  `gotra_v3_8x_rubric_reasoning_scoring_runtime_20260626T140000Z_scale`
- Summary:
  `/tmp/gotra_rubric_reasoning_quality/phase3_scoring_outputs/gotra_v3_8x_rubric_reasoning_scoring_runtime_20260626T140000Z_scale/validation_summary.json`
- Reviewer verdict: `REVIEW_PASS_WITH_LIMITATION`
- Accepted layer only:
  `phase3_scoring_runtime_scale_failure_recovery_measurability_repair_pass_with_limitation`
- Outcome: eligible as Phase 3 source for a later Phase 4 reliability run, not
  a Phase 4 pass.

### Phase 4 blocked, 2026-06-27 01:00Z

- Run id:
  `gotra_v3_8y_rubric_reasoning_scorer_reliability_20260627T010000Z_scale`
- Summary:
  `/tmp/gotra_rubric_reasoning_quality/phase4_reliability_outputs/gotra_v3_8y_rubric_reasoning_scorer_reliability_20260627T010000Z_scale/reliability_summary.json`
- `reliability_summary_sha256=424ac247b93ba6a7e67674ead1728feb4553ead94d5331f89c018779eedbfc87`
- `icc_2_k=0.569156 < icc_2_k_minimum=0.70`
- `kendall_tau=0.297243 < kendall_tau_minimum=0.60`
- Blockers:
  `scorer_reliability_icc_2_k_below_threshold`,
  `scorer_reliability_kendall_tau_below_threshold`
- Outcome: `PHASE_4_BLOCKED_SCORER_RELIABILITY`.

### Budget-blocked Phase 3, 2026-06-27 08:00Z

- Run id:
  `gotra_v3_8x_rubric_reasoning_scoring_runtime_20260627T080000Z_scale`
- Summary:
  `/tmp/gotra_rubric_reasoning_quality/phase3_scoring_outputs/gotra_v3_8x_rubric_reasoning_scoring_runtime_20260627T080000Z_scale/validation_summary.json`
- Reviewer verdict: `REVIEW_BLOCKED`
- Rule id: `BUDGET_CAP_EXCEEDED`
- Field/status:
  `cost_estimated_usd=1473.65368 > cost_cap_usd=1000.0`
- `cost_cap_enforcement=hard_stop`
- `regate_authorization=null`
- Outcome: cannot be promoted or used as Phase 3 source.

### Unbounded-budget Phase 3 pass with limitation, 2026-06-27 12:00Z

- Run id:
  `gotra_v3_8x_rubric_reasoning_scoring_runtime_20260627T120000Z_scale`
- Summary:
  `/tmp/gotra_rubric_reasoning_quality/phase3_scoring_outputs/gotra_v3_8x_rubric_reasoning_scoring_runtime_20260627T120000Z_scale/validation_summary.json`
- Reviewer verdict: `REVIEW_PASS_WITH_LIMITATION`
- `validation_summary_sha256=dfbbbf96196afa7af35459b69621f0ff3dc84666c0afca45a74b2d6ab8df46fb`
- `scoring_manifest_sha256=ae57265082e37977fee73a4b0dc23095bee2507dffc61833f0b86e561148d5c3`
- `scored_records_sha256=10ac7b3efd7e0c73ebf4a5b13b95149602a4d080edf6cf7cdf00997a997b82f2`
- `budget_mode=unbounded`
- `budget_cap_unbounded=true`
- `cost_cap_usd=null`
- `cost_cap_enforcement=unbounded_user_authorized`
- `regate_authorization=user_explicit_unbounded_budget_authorization`
- Outcome: eligible as Phase 3 source for a later fresh Phase 4 reliability
  run, with cost/token/model-family limitations preserved.

### Latest fresh Phase 4 blocked, 2026-06-27 10:30Z

- Run id:
  `gotra_v3_8y_rubric_reasoning_scorer_reliability_20260627T103000Z_scale`
- Summary:
  `/tmp/gotra_rubric_reasoning_quality/phase4_reliability_outputs/gotra_v3_8y_rubric_reasoning_scorer_reliability_20260627T103000Z_scale/reliability_summary.json`
- `reliability_summary_sha256=d2849a1570361689708aa2c164cca50b4cfc4fc6e8c567e50a2c7dd516a97f6f`
- `icc_2_k=0.547762 < icc_2_k_minimum=0.70`
- `kendall_tau=0.278711 < kendall_tau_minimum=0.60`
- Blockers:
  `scorer_reliability_icc_2_k_below_threshold`,
  `scorer_reliability_kendall_tau_below_threshold`
- Outcome: `PHASE_4_BLOCKED_SCORER_RELIABILITY`.

### Contrastive low-dimension probe, 2026-06-27 17:00Z

- Run id:
  `gotra_v3_8x_contrastive_pair_selection_by_low_dim_cues_probe_20260627T170000Z`
- Summary:
  `/tmp/gotra_rubric_reasoning_quality/phase3_scoring_outputs/gotra_v3_8x_contrastive_pair_selection_by_low_dim_cues_probe_20260627T170000Z/validation_summary.json`
- Evidence layer: smoke/probe evidence, diagnostic only.
- `calibration_probe_gate.status=PASS`
- `provenance_completeness distinct_score_count=5`
- `determinism_stability distinct_score_count=6`
- Outcome: useful diagnostic signal only, not formal pass.

### Blocked Phase 3 scale after contrastive repair, 2026-06-27 18:00Z

- Run id:
  `gotra_v3_8x_rubric_reasoning_scoring_runtime_20260627T180000Z_scale`
- Summary:
  `/tmp/gotra_rubric_reasoning_quality/phase3_scoring_outputs/gotra_v3_8x_rubric_reasoning_scoring_runtime_20260627T180000Z_scale/validation_summary.json`
- `status=BLOCKED_RUNTIME_BOUNDARY`
- `scoring_status=BLOCKED_RUNTIME_BOUNDARY`
- Blockers:
  `codex_exec_runtime_error`,
  `scored_record_count_mismatch`,
  `paired_required_candidate_arm_missing`
- Exact blocker path:
  `/private/tmp/gotra_rubric_reasoning_quality/phase3_scoring_outputs/gotra_v3_8x_rubric_reasoning_scoring_runtime_20260627T180000Z_scale/scoring/scorer_alpha_codex_cli_anchor_first/v3_8x_pair_0023/arm_beta`
- Outcome: cannot be Reviewer-ready Phase 3 source.

### Missing reviewed Phase 2 source artifact

- Missing path:
  `/tmp/gotra_rubric_reasoning_quality/phase2_arm_outputs/gotra_v3_8x_rubric_reasoning_arm_generation_20260623T085023Z_regate_scale/arm_outputs.jsonl`
- Expected sha256:
  `ed8953c3784a6cbb83a45efe1cd77e106e6f3373bc38ba97a6bad86cae3dce5d`
- Constraint: do not fake, reconstruct, relabel, reuse, or overwrite that old
  run id.
- Outcome: source-chain reproducibility risk due to `/tmp` artifact volatility.

### Fresh Phase 2 regeneration attempt, 2026-06-28 08:00Z

- Run id:
  `gotra_v3_8x_rubric_reasoning_arm_generation_20260628T080000Z_regate_scale`
- Status: `NEEDS_REPAIR`
- `generation_status=NEEDS_REPAIR`
- Blockers:
  `reasoning_too_short`,
  `arm_output_count_mismatch`
- Outcome: partial/failed artifact, not promoted.

### Fresh Phase 2 regeneration review blocked, 2026-06-28 08:30Z

- Run id:
  `gotra_v3_8x_rubric_reasoning_arm_generation_20260628T083000Z_regate_scale`
- Summary:
  `/tmp/gotra_rubric_reasoning_quality/phase2_arm_outputs/gotra_v3_8x_rubric_reasoning_arm_generation_20260628T083000Z_regate_scale/validation_summary.json`
- Manifest:
  `/tmp/gotra_rubric_reasoning_quality/phase2_arm_outputs/gotra_v3_8x_rubric_reasoning_arm_generation_20260628T083000Z_regate_scale/arm_output_manifest.json`
- Arm outputs:
  `/tmp/gotra_rubric_reasoning_quality/phase2_arm_outputs/gotra_v3_8x_rubric_reasoning_arm_generation_20260628T083000Z_regate_scale/arm_outputs.jsonl`
- `validation_summary_sha256=55c53c04aca2da48fc8686c2147fa38080ac103623ccc64f9d6f3639db8bb148`
- `arm_output_manifest_sha256=b40b1430b8ee71ea58d14bd3eb22e499bca163358ac5da9465102e3ca69abcad`
- `arm_outputs_sha256=9a5946fc44a0b3edad8bd5031efc8ff68bb193c2da517ab6c2b8860d800e944d`
- Worker summary fields:
  `status=PASS`, `generation_status=PASS`,
  `selected_paired_sample_count=80`, `candidate_arm_count=160`,
  `real_calls_count=160`, `budget_mode=unbounded`,
  `cost_cap_usd=null`,
  `cost_cap_enforcement=unbounded_user_authorized`,
  `regate_authorization=user_explicit_unbounded_budget_authorization`
- Reviewer verdict: `REVIEW_BLOCKED`
- Hard stop: `CLAIM_BOUNDARY_BREACH`
- Rule id: `claim_boundary_forbidden_wording`
- Forbidden token observed by Reviewer: `clean baseline`
- Blocked artifact path:
  `/tmp/gotra_rubric_reasoning_quality/phase2_arm_outputs/gotra_v3_8x_rubric_reasoning_arm_generation_20260628T083000Z_regate_scale/arm_outputs.jsonl`
- Outcome: not eligible as fresh Phase 2 source for Phase 3. Fresh rerun
  required if work resumes.

## Repair Directions Attempted

### `FAILURE_RECOVERY_MEASURABILITY_REPAIR`

Improved failure-recovery measurability enough to produce a Reviewer-passed
Phase 3 source with limitation, but subsequent Phase 4 still failed
`kendall_tau`.

### `DETERMINISM_STABILITY_MEASURABILITY_REPAIR`

Targeted low spread and ambiguity in deterministic/reproducibility cues.
Remaining reliability still failed formal Phase 4 thresholds.

### `PROBLEM_DECOMPOSITION_MEASURABILITY_REPAIR`

Probe remained blocked with compressed score distribution:
`problem_decomposition distinct_score_count=2`,
`histogram={"3":4,"3.5":12}`.

### `PROVENANCE_COMPLETENESS_MEASURABILITY_REPAIR`

Probe remained blocked with compressed score distribution and role asymmetry:
`provenance_completeness distinct_score_count=2`,
`histogram={"3.5":3,"4":13}`.

### `ANTI_DEFAULT_HIGH_SCORER_INSTRUCTION`

Improved several weak dimensions but left
`provenance_completeness distinct_score_count=2` with
`histogram={"3.5":4,"4":12}`.

### `PER_DIMENSION_RANK_ORDER_CALIBRATION_FIXTURES`

Improved `provenance_completeness` bucket spread:
`distinct_score_count=6`, `variance=2.058594`,
`top_value_fraction=0.25`, `score_range=4.0`, but remaining blocker was
`measurability_probe_scorer_role_distribution_asymmetric`.

### `ROLE_SYMMETRY_AND_PROMPT_VARIANT_AUDIT`

Improved role symmetry enough to produce a fresh Phase 3 scale under unbounded
budget authorization, later accepted by Reviewer with limitation.

### `BUDGET_UNBOUNDED_AUTHORIZATION_AND_STATUS_MAPPING_REPAIR`

Mapped explicit user budget authorization into safe metadata:
`budget_mode=unbounded`, `budget_cap_unbounded=true`,
`cost_cap_usd=null`, `cost_cap_enforcement=unbounded_user_authorized`,
`regate_authorization=user_explicit_unbounded_budget_authorization`.
This fixed the stale `cost_cap_usd=1000.0` hard-stop problem for future
authorized reruns.

### `PAIRWISE_RANK_INVERSION_REPAIR`

Improved some weak dimensions but left `provenance_completeness` and
`determinism_stability` compressed:
`provenance_completeness distinct_score_count=2`,
`determinism_stability distinct_score_count=2`.

### `CONTRASTIVE_PAIR_SELECTION_BY_LOW_DIM_CUES`

Probe reached diagnostic `calibration_probe_gate.status=PASS` with
`provenance_completeness distinct_score_count=5` and
`determinism_stability distinct_score_count=6`. The downstream Phase 3 scale
failed with `BLOCKED_RUNTIME_BOUNDARY`.

### `RUNTIME_COMPLETION_REPAIR_FOR_CONTRASTIVE_LOW_DIM_SCALE`

Identified and contained runtime completion issues so partial failed runs were
not promoted as complete scored records. The relevant blocked Phase 3 scale
remained `gotra_v3_8x_rubric_reasoning_scoring_runtime_20260627T180000Z_scale`.

### `FRESH_PHASE2_SOURCE_REGENERATION_AFTER_TMP_ARTIFACT_LOSS`

Regenerated a fresh Phase 2 artifact after old `/tmp` source loss, added
bounded retry handling for retryable arm-output invalidity, and produced
`gotra_v3_8x_rubric_reasoning_arm_generation_20260628T083000Z_regate_scale`.
Reviewer blocked that artifact due to `CLAIM_BOUNDARY_BREACH`.

## What Improved

- Some probes improved low-dimension bucket spread, especially for
  `failure_recovery`, `provenance_completeness`, and
  `determinism_stability`.
- Role symmetry improved in some dimensions after role/prompt-variant repair.
- `CONTRASTIVE_PAIR_SELECTION_BY_LOW_DIM_CUES` reached diagnostic
  `calibration_probe_gate.status=PASS`.
- Runtime partial-output handling improved so partial failed runs are not
  promoted as complete scored records.
- Budget metadata was made compatible with explicit unbounded user
  authorization.

## What Still Failed

- Phase 4 Kendall reliability remains below threshold.
- The latest accepted Phase 3 source did not produce a passing Phase 4.
- Runtime completion and source artifact continuity blocked further formal
  reruns.
- `/tmp` artifact volatility created source-chain reproducibility risk.
- Fresh Phase 2 regeneration first hit `reasoning_too_short` and
  `arm_output_count_mismatch`.
- A later fresh Phase 2 regeneration run was Reviewer-blocked due to
  `CLAIM_BOUNDARY_BREACH` / `claim_boundary_forbidden_wording`.
- No Reviewer-passed fresh Phase 4 threshold evidence exists.

## Current Status

Current documentation closeout status:
`METHOD_DECISION_NOT_FORMALLY_ACCEPTED_UNDER_CURRENT_PROTOCOL`

Formal Phase 4 status remains:
`PHASE_4_BLOCKED_SCORER_RELIABILITY`

Latest fresh Phase 4 evidence preserved in the controller record:

- `gotra_v3_8y_rubric_reasoning_scorer_reliability_20260627T103000Z_scale`
- `icc_2_k=0.547762 < icc_2_k_minimum=0.70`
- `kendall_tau=0.278711 < kendall_tau_minimum=0.60`
- Blockers:
  `scorer_reliability_icc_2_k_below_threshold`,
  `scorer_reliability_kendall_tau_below_threshold`

Latest source-chain blocker:

- Artifact:
  `/tmp/gotra_rubric_reasoning_quality/phase2_arm_outputs/gotra_v3_8x_rubric_reasoning_arm_generation_20260628T083000Z_regate_scale/arm_outputs.jsonl`
- Reviewer verdict: `REVIEW_BLOCKED`
- Hard stop: `CLAIM_BOUNDARY_BREACH`
- Rule id: `claim_boundary_forbidden_wording`
- Fresh rerun required if work resumes.

## Next Requirements If Work Resumes

If work resumes, the minimum requirements are:

- Durable source artifact storage instead of relying only on `/tmp`.
- Fresh Phase 2 source generation with complete arm outputs.
- Phase 2 validation that explicitly catches claim-boundary forbidden wording
  and maps it to a hard blocker before a source is marked usable.
- Reviewer gate for the fresh Phase 2 source if protocol requires it.
- State-Writer gate for fresh Phase 2 only after Reviewer pass.
- Fresh Phase 3 scale from Reviewer-passed Phase 2.
- Reviewer and State-Writer gate for fresh Phase 3.
- Fresh Phase 4 reliability from Reviewer-passed Phase 3.
- Reviewer and State-Writer gate for formal Phase 4 only if both
  `icc_2_k >= 0.70` and `kendall_tau >= 0.60`.
- No Phase 5/effective-N/verdict fan-in before Reviewer-passed Phase 4.

## Claim Boundary

This is an engineering/reliability closeout document. It is not evidence of
GOTRA scientific success. It is not a trading or investment recommendation. It
does not establish cognitive-lift superiority, clean direct-LLM baseline,
market edge, production readiness, or public-science proof.

## Validation For This Documentation Sync

Documentation-only scope intended:

- Created:
  `docs/GOTRA_V3_8XY_KENDALL_RELIABILITY_REPAIR_MATRIX_CLOSEOUT_20260628.md`
- Required local validation:
  `codex-preflight --check --expect-project gotra`
- Required documentation sanity check:
  `git diff --check`
- No code tests required for this documentation-only closeout.
