# GOTRA Direct LLM Interpretation Boundary (2026-06-20)

## Scope

This note applies to historical GOTRA Baseline v2/v3 result documents that report
metrics for a `direct_llm` arm.

## Boundary

Historical `direct_llm` results must be read as
`direct_llm_parametric_memory_control`.

The arm is not a clean no-future historical baseline. Even when prompts, input
packets, and artifact filters are time-bounded to `decision_date`, a modern LLM
may contain later market narratives in its parameters. Prompt and artifact gates
reduce explicit future-data leakage, but they do not erase parametric memory.

Therefore:

- `direct_llm` metrics are diagnostic only.
- `direct_llm` should not be used to prove or refute GOTRA, ksana, or alaya
  success.
- Comparisons such as C1/C3/C5 are useful for engineering and methodological
  diagnosis, not for OOS, science/public, or trading claims.
- Cleaner historical baselines should use deterministic price-only or simple
  statistical references.
- The strongest future-oriented evidence remains forward-live/future-only
  capture with outcomes scored only after maturation.

## Reading Older Documents

Older Baseline v2 documents may keep the literal arm name `direct_llm` because it
was the recorded run artifact label. When interpreting those documents, read
that label as `direct_llm_parametric_memory_control` unless a later document
explicitly defines a stricter baseline.
