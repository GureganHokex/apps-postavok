<!-- orchestrate handoff
task: review-architecture
branch: `orch/excel-parser-resilient-design/design-architecture` (commit `00acd51` — review only adds `docs/design/excel-parser/_review/architecture-review.md`, не трогает артефакты worker'а)
agentId: bc-3641eb7b-296f-4869-8cc9-e90b50c02464
runId: run-bbdf0468-1bd6-46d8-ac0c-e565b1f7640b
resultStatus: finished
finishedAt: 2026-05-08T18:26:35.101Z
-->

Review committed and pushed.

## Verification
unit-test-verified

## Target
`design-architecture` on branch `orch/excel-parser-resilient-design/design-architecture`

## Branch
`orch/excel-parser-resilient-design/design-architecture` (commit `00acd51` — review only adds `docs/design/excel-parser/_review/architecture-review.md`, не трогает артефакты worker'а)

## Execution
- `python3 -c 'import ast; ast.parse(open("docs/design/excel-parser/contracts/pipeline.py").read())'` → `ast.parse OK`
- `pip install jsonschema` → installed 4.26.0
- `python3 -c "import json,jsonschema; jsonschema.Draft7Validator.check_schema(...)"` → `Draft7 schema OK`
- 5 sanity-семплов через `Draft7Validator.iter_errors`: minimal valid → pass; extra field → reject (`additionalProperties: false`); unknown `field_confidences` key → reject; warning shape → pass; **negative numeric `price` → pass (gap)**; `"-10"` string → reject; `"12,50"` string → reject (gap для русской локали)
- `wc -l docs/design/excel-parser/architecture.md` → 860 строк, разделы §1..§15 присутствуют (verified Read offset)
- `grep "mermaid" docs/design/excel-parser/architecture.md` → 5 диаграмм (§4.1, §12.1, §14.1, §14.2, §14.3); требование ≥ 2 выполнено
- 14 осей изменчивости перепроверены в матрице §2.2 + сверены с описаниями стадий §4: 13 covered, 1 partial (ось 3 — brewery-as-prefix внутри `beer_name`)
- Cross-check `ParseWarning` между arch.md §5.1 / pipeline.py / schema → подтверждена расхождение `field` vs `field_name`
- Cross-check `ParseError` наследования между §5.1 (наследник) vs pipeline.py (отдельный класс) vs §13 (явно «error ≠ warning») → внутреннее противоречие
- `git push` → success

## Findings

Per acceptance criterion (verifier-specific):
- [x] `docs/design/excel-parser/_review/architecture-review.md` создан и закоммичен (`00acd51`) — met
- [x] В первой строке `# Verdict: pass-with-comments` — met
- [x] Все 14 осей классифицированы: 13 covered / 1 partial (ось 3) / 0 missing — met
- [x] Каждое замечание ссылается на раздел/строку (§4, §5.1 строка 372, schema строка 146, и т.д.) — met

Per acceptance criterion (target worker):
- [x] `architecture.md` существует, 860 строк, 15 разделов — met
- [x] ≥ 2 mermaid-диаграммы — met (5 диаграмм)
- [x] `parsed_item.schema.json` валидный draft-07 — met (но без `minimum: 0` для price/volume/stock)
- [x] `pipeline.py` парсится `ast.parse` — met
- [x] 14 осей адресованы — частично (ось 3 partial, см. high finding)

Other findings (severity-ordered):
- (high) **Ось 3 partial**: brewery-as-prefix внутри `beer_name` (например, `"Paradox - Stout 5%"`) не покрыт ни одной стадией. `MetaExtractor` решает только filename-case, group-headers — отдельный case в `RegionDetector`. Нужен `BrewerySplitter` под-шаг в `Normalizer` или отдельная стадия.
- (high) **Контрактный drift**: `ParseWarning.field` (arch.md §5.1, schema:146) vs `field_name` (pipeline.py:187). Сериализация через `dataclasses.asdict` не пройдёт schema из-за `additionalProperties: false`.
- (high) **Внутреннее противоречие**: §5.1 объявляет `ParseError(ParseWarning): pass`, pipeline.py:190 — отдельный класс без наследования; §13 (стр. 723) утверждает «`ParseError` ≠ `ParseWarning`» — что противоречит §5.1.
- (med) **JSON Schema gap**: `price`/`volume`/`stock` пропускают отрицательные числа (regex pattern не применяется к type=number в draft-07; нет `minimum: 0`); пропускают также строки с запятой (`"12,50"`), хотя §3 пишет «Decimal как строка».
- (med) **§6.3 SupplierTypeDetector**: формула не нормализована — сумма весов может превысить 1.0, в отличие от §6.1/§6.2.
- (med) **§10.1 SLO без плана валидации**: метрики есть в §11, но как именно gating'овать (load-test / harness / production) — не сказано.
- (med) **§5.2 vs pipeline.py**: упомянутые `LoaderError`, `RowExtractorWarning` не определены в pipeline.py (там `FileLoadError`).
- (low) **§9 опечатка** «Petr-loop» → «Feedback-loop» (стр. 580).
- (low) **§14.2 sequence**: Validator вызывается в loop'е, но в диаграмме `invalid_items` теряется визуально между loop и Deduplicator.
- (low) **§7/§9 коллизия**: не описано формально, что БД-маппинг (вес `user`=1.0) побеждает YAML-лексикон (`header_exact`=0.9).
- Остальные low — собраны в таблице §13 ревью.

## Notes & suggestions
- Worker для skeleton-implementation должен начать **с** правки трёх high-замечаний: иначе DTO зафиксируется в коде с двумя именами поля одновременно. Контракт `ParseWarning` должен быть первым же commit'ом нового worker'а.
- Worker для regression harness может одновременно закрыть калибровку весов confidence (open question worker'а): тот же корпус прайсов даст и пороги, и проверку SLO P95.
- Schema-фикс (`minimum: 0` для price/volume/stock) — тривиальный hotfix, можно вынести как сидячий next-step worker'а или сделать в первом же коммите skeleton-implementation.
- Полностью legacy-удаление (V5 в §12.1) безопасно только после того, как все 14 осей будут зелёными в harness'е на ≥ 30 файлах. Этот gate стоит явно прописать в plan.json.