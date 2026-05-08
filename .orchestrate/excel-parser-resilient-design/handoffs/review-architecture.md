<!-- orchestrate handoff
task: review-architecture
branch: orch/excel-parser-resilient-design/design-architecture
agentId: bc-7d3757d7-7638-4bc7-8f10-a5db2395659e
runId: run-ffd46bfb-84f1-4542-a5ce-7fede63ea33a
resultStatus: finished
finishedAt: 2026-05-08T18:30:27.738Z
-->

Pushed cleanly. Final handoff:

## Verification
unit-test-verified

## Target
`design-architecture` on branch `orch/excel-parser-resilient-design/design-architecture`

## Branch
`orch/excel-parser-resilient-design/design-architecture`

## Execution
- `python3 -c 'import ast; ast.parse(open("docs/design/excel-parser/contracts/pipeline.py").read())'` → OK (syntactically valid).
- `pip install jsonschema` → installed, then `python3 -c "import json,jsonschema; jsonschema.Draft7Validator.check_schema(json.load(open('docs/design/excel-parser/contracts/parsed_item.schema.json')))"` → OK (draft-07 schema valid).
- Sanity-validation against schema with one positive sample (full ParsedItem) → accepted; four negative samples (missing `beer_name`, `confidence > 1`, invalid `format_type` `"Bottle"`, unknown `field_confidences` key) → all correctly rejected.
- `importlib.util.spec_from_file_location(...).loader.exec_module(...)` after `sys.modules['pipeline']=mod` → module loads; `Field.BREWERY`, `PipelineConfig()`, `Candidate(value=1, …)` all instantiate.
- Manual review of `architecture.md`: counted 15 numbered sections, 5 mermaid blocks (§4.1 flowchart, §12.1 migration, §14.1 pipeline, §14.2 sequence, §14.3 class), 14-axis coverage table at §2.2 verified line-by-line against bodies of §4/§6/§7.
- Cross-checks: `MetaExtractor` referenced in §2.2 / §4.1 / §4.2 / §11 / §14.1 / §14.2 / §14.3 but missing from TL;DR (§1 line 15). `ParseError` defined as inheriting `ParseWarning` in markdown (line 379) but as standalone dataclass in `pipeline.py` (line 191); `field` vs `field_name` mismatch among markdown/pipeline.py/JSON Schema. Loader sanitize "снять защиту на чтение" (§4 line 174) contradicts §15 risk row (line 854).
- `git rebase` against `origin/orch/excel-parser-resilient-design/design-architecture` (which already contained a prior verifier's review at the same path) → conflict; resolved by appending my second-pass review beneath the existing one in the canonical file rather than overwriting; fast-forward push succeeded (`00acd51..6090ca9`).

## Findings
Per acceptance criterion (verifier-specific):
- [x] `docs/design/excel-parser/_review/architecture-review.md` создан и закоммичен → met (commit `6090ca9` on the worker branch, pushed to origin).
- [x] В первой строке файла стоит Verdict — met (`# Verdict: pass-with-comments`, line 1; both passes agree on the same verdict).
- [x] Все 14 осей изменчивости явно классифицированы (covered/partial/missing) — met (table in §2 of the second-pass review classifies all 14 as `covered` except axis 6 marked `partially covered`; the prior first-pass review additionally treats axis 3 as `partially covered`).
- [x] Каждое замечание имеет ссылку на конкретный раздел/строку — met (each M-/m- finding cites a section number + line range in `architecture.md`).

Per acceptance criterion (target task — quick spot-check):
- [x] 15 sections present (TL;DR/Reqs/Contract/Pipeline/Module-contracts/Confidence/Registries/Extensibility/Feedback/Performance/Observability/BC/Failure/Diagrams/Risks).
- [x] ≥ 2 mermaid diagrams (5 found).
- [x] JSON Schema draft-07 valid.
- [x] `pipeline.py` parses with `ast.parse`.
- [x] All 14 axes addressed (one partial — price-vs-stock content scoring).

Other findings (severity-ordered):
- (high) **M-1** §6.2 lines 470–472: `numeric_ratio ∧ mean(values) ≤ 10000 ∧ diff_from_price_col` mixes booleans and numerics into a "score" — no numeric formula; harness-worker has nothing to calibrate against. Critical for axis 6.
- (high) **M-3** §12 line 677 vs §13 line 712: at the legacy facade boundary `parse(...) -> list[dict]` only logs warnings/errors, returning silent empty list on `status="failed"`. This contradicts §13's explicit "no silent empty result" rule. Need a strict alternate API or explicitly call out the trade-off.
- (high) **M-4** Contract drift: `ParseError`/`ParseWarning` inheritance and `field` vs `field_name` mismatched across `architecture.md` §5.1, `pipeline.py`, and JSON Schema. Will break `dataclasses.asdict` → schema validation pipeline.
- (high) Prior verifier's findings (preserved in same file): brewery-as-prefix splitter missing for axis 3 (`"Paradox - Stout 5%"` → split is undescribed in any stage), no `minimum: 0` in JSON Schema for `price`/`volume`/`stock` numeric branch, CSV decimal `12,50` rejected by current schema pattern.
- (med) **M-2** TL;DR (§1, line 15) omits `MetaExtractor` though present in all diagrams.
- (med) **M-7** §4 Loader (line 174) "снять защиту на чтение" contradicts §15 risk row (line 854) "без попыток обхода".
- (med) **M-8** No concrete plan/tooling to validate SLO (no `pytest-benchmark`/perf-CI mentioned).
- (med) **M-9** Voting is `argmax(score)` — no aggregation of converging sources; flagged as open question for harness-worker.
- (med) **M-5** ColumnMapper behavior on `SupplierColumnMapping` referencing a non-existent column is undefined.
- (low) `Petr-loop` typo (§9 line 580); `file_hash_prefix` (§7 line 508) introduced without definition; streaming-mode (§10.2) vs Loader "numpy array" (§4.2) consistency note; hot-reload only in DEBUG (§7) leaves prod admin without a no-redeploy path; ABV `<1 → fraction` heuristic risks false-positive on ≤0.5% non-alc.

Open questions for the planner (escalation, not blocker):
- OQ-1: how does the legacy facade return when `ParseResult.status="failed"`?
- OQ-2: scope conflict resolution when both file-pattern and supplier-pattern user-mappings match.
- OQ-3: voting strategy choice (`argmax` vs `sum`/`mean`) before harness-worker calibrates.

## Notes & suggestions
- Two independent verifier passes converged on `pass-with-comments`. The current `_review/architecture-review.md` is a layered file: first half = first-pass verifier (commit `00acd51`, 482 lines), second half = my second pass (commit `6090ca9`, +176 lines after a "Second-pass verifier review" separator). I deliberately preserved the first review rather than force-pushing over it; final push was a fast-forward (`00acd51..6090ca9`), no force, no amend.
- Both passes flag the same `ParseError`/`ParseWarning` `field`/`field_name` drift — strongest signal for the architect-fix-worker.
- Recommended next worker: a **fix-architecture** pass that addresses `M-1` (numeric formula for stock content score), `M-3` + OQ-1 (facade strictness or new API), `M-4` (contract drift), `M-7` (Loader sanitize vs LoaderError), and the prior pass's brewery-as-prefix splitter and JSON Schema `minimum: 0`. After that, harness-worker and skeleton-worker can start in parallel.
- Open questions worker'а сводятся к follow-up worker'ам (harness, skeleton, YAML registries, DB feedback, UI ambiguous) — пишутся параллельно после fix-architecture.

## Branch
`orch/excel-parser-resilient-design/design-architecture`
## Verdict
pass-with-comments
## Summary
Both independent verifier passes (prior: commit `00acd51`, mine: commit `6090ca9`) converge on `pass-with-comments`: 15 sections present, 5 mermaid diagrams, JSON Schema valid, `pipeline.py` parses; all 14 axes addressed (axis 6 partial in second pass; axis 3 partial in first pass). Must-fix before skeleton-worker: contract drift `ParseError`/`ParseWarning` `field` vs `field_name` (M-4 + first-pass parallel finding), facade silent-empty contradicts §13 (M-3/OQ-1), Loader sanitize vs LoaderError contradiction (M-7), under-specified content-score formula for stock (M-1), brewery-as-prefix splitter missing (first-pass finding), JSON Schema `minimum:0` for numeric fields (first-pass finding). Open questions OQ-1..OQ-3 belong to the planner / next architect-fix worker.
## Files
- docs/design/excel-parser/_review/architecture-review.md
## Coverage
14/14 axes (this pass): 13 covered, 1 partial (axis 6 — price vs stock, score formula uses logical AND not numeric). Combined with first-pass review in same file: 12 covered, 2 partial (axes 3 and 6).