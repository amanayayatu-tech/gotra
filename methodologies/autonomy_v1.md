# Gotra Autonomy Methodology v1

This document freezes the Phase 0 autonomy boundary for gotra.

## Repository Roles

- gotra owns orchestration, integration contracts, autonomous operators, reporting, and backtests.
- ksana remains the pure domain engine under `engine/ksana`, pinned as a submodule.
- Alaya remains the governance system of record for gates, predictions, observations, errors, and knowledge state.

## Perplexity Boundary

ksana agents must not call Perplexity or external research APIs directly. Gotra may later introduce an orchestration-layer auto-fill operator that writes the same `_filled.yaml` artifact a human operator would have supplied. That migration is a layer boundary change, not a relaxation of ksana agent purity.

Phase P activates that auto-fill operator in gotra, not in ksana. The operator reads ksana `data/pull_requests/PR-*.yaml`, validates each record with ksana's `PerplexityPrompt` schema, calls Perplexity from the gotra orchestration layer, and writes the same `data/perplexity_results/*_filled.yaml` file that Nepha previously supplied manually through Perplexity Max/WebUI. ksana R8 remains unchanged: ksana agents still never import or call Perplexity or external research clients, and ksana guard tests remain the protection mechanism for that boundary.

Pipeline ordering is auto-fill first, `perplexity_wait` second. If gotra's operator times out or has no API key, it leaves the prompt pending so the existing human/manual `perplexity_wait` fallback remains valid.

## Human-Only Strong Promotion

Automation may prepare evidence, reject or approve lower-risk gates after Phase B0, and quarantine unsafe knowledge through audited APIs. Automation must never promote knowledge to `strong`; strong promotion remains a human-only action.

## Audit Boundary

Cross-system writes must use service or API paths that emit audit events. Direct database writes are reserved for read-only verification and are not implementation paths.
