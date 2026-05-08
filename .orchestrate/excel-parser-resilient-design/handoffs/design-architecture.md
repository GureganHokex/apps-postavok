<!-- orchestrate handoff
task: design-architecture
branch: orch/excel-parser-resilient-design/design-architecture
agentId: bc-c9f4d84c-43ac-464c-b891-3ac4d54088c9
runId: run-d190e559-10ac-4058-9d56-b5dc06d01cdd
resultStatus: finished
finishedAt: 2026-05-08T18:18:46.972Z
-->

All checks pass. Here is my handoff:

## Status
success

## Branch
`orch/excel-parser-resilient-design/design-architecture`

## What I did
- Created design-only document set under `docs/design/excel-parser/**`. No backend or frontend code touched.
- `docs/design/excel-parser/architecture.md` (860 строк): 15 разделов согласно ТЗ — TL;DR, требования с матрицей "ось → раздел" для всех 14 осей изменчивости, контракт `ParsedItem`, граф pipeline `Loader → SheetClassifier → MetaExtractor → RegionDetector → HeaderDetector → ColumnMapper → RowExtractor → Normalizer → Validator → Deduplicator → TelemetrySink`, модульные DTO-контракты с таблицей "что значит провал на стадии", формальный confidence-скоринг и voting (с весами источников и tie-break правилами), YAML+БД реестры, plug-in points расширяемости, схема таблиц `SupplierColumnMapping`/`ParsingFeedback`/`ParseRun` для feedback-loop, SLO производительности с сравнительной таблицей старого парсера и нового, список структурированных событий и Prometheus-метрик, план миграции через feature flag `EXCEL_PARSER_PIPELINE_V2`, явный `ParseResult.status` против тихого пустого результата, 5 mermaid-диаграмм (pipeline, sequence, class, migration roadmap), таблица рисков.
- `docs/design/excel-parser/contracts/parsed_item.schema.json` (152 строки): валидный JSON Schema draft-07 для `ParsedItem` (проверено `jsonschema.Draft7Validator.check_schema` + sanity-сэмплом).
- `docs/design/excel-parser/contracts/pipeline.py` (562 строки): Protocol/dataclass псевдокод всех DTO (`RawFile`, `Workbook`, `Sheet`, `SheetVerdict`, `FileMeta`, `DataRegion`, `HeaderCandidate`, `Candidate[T]`, `ColumnPlan`, `RawRow`, `ParsedItem`, `ParseResult`, ...) и стадий (`Loader`, `SheetClassifier`, `MetaExtractor`, `RegionDetector`, `HeaderDetector`, `ColumnMapper`, `RowExtractor`, `Normalizer`, `Validator`, `Deduplicator`, `TelemetrySink`, `Pipeline`). Синтаксически валиден (`ast.parse` проходит).
- Закоммитил, запушил ветку, открыл draft PR #4 на `main`.

## Measurements
- `sections_in_architecture_md: 0 → 15`
- `mermaid_diagrams_in_architecture_md: 0 → 5` (требование `>= 2`)
- `axes_of_variability_addressed: 0 → 14` (требование `== 14`)
- `wc -l docs/design/excel-parser/architecture.md: 0 → 860`
- `python3 -c 'import ast; ast.parse(open("docs/design/excel-parser/contracts/pipeline.py").read())': fail → ok`
- `Draft7Validator.check_schema(parsed_item.schema.json): n/a → ok`

## Verification
type-check-only

JSON Schema валидируется `jsonschema.Draft7Validator.check_schema` плюс положительный sanity-сэмпл. `pipeline.py` проходит `ast.parse`. Архитектурный документ — design-only, нет кода для unit-тестов; финальная верификация смысловой устойчивости pipeline — задача harness-стадии следующих worker-ов.

## Notes, concerns, deviations, findings, thoughts, feedback
- Намеренно вынес три антипаттерна текущего кода в design-решения, чтобы не повторить: (1) hardcoded имена брендов (`paradox`, `alisperi`, `two peaks`) переезжают в `supplier_hints.yaml`; (2) тихий пустой результат заменён на обязательный `ParseResult.status` + `ParseError`/`ParseWarning`; (3) хардкоженные top-N лимиты header-детектора заменены на параметры конфига с векторизацией numpy.
- DDD-рефакторинг в `infrastructure/parsers/excel_parser.py` (3805 строк) описан как **основа** V2, не как параллельная ветка. Его `__init__.py` всё ещё реэкспортит legacy `ExcelParser`; в плане миграции (§12.1) это снимается на этапе V5.
- В §6 я зафиксировал конкретные веса источников (user 1.0 / header_exact 0.9 / ... / position 0.3) и пороги (`θ_field = 0.45`, `θ_optional = 0.30`) как defaults, явно отметив что они должны калиброваться regression harness'ом на корпусе реальных прайсов. Точные числа — open question для следующего worker'а с harness'ом.
- `ParsedItem` мета-поля (`confidence`, `field_confidences`, `warnings`) не ломают текущую БД-схему: §3 описывает adapter `ParsedItem → DBPriceItem`, который берёт подмножество полей; полный `ParseResult` сохраняется в новую таблицу `ParseRun` для аудита.
- Я не нашёл `PULL_REQUEST_TEMPLATE.md` в репо, поэтому body PR написал сам по структуре handoff.

## Suggested follow-ups
- Worker для regression harness: собрать корпус реальных прайс-файлов в `tests/fixtures/excel-parser/`, выдать harness, который прогоняет старый парсер и (для shadow-mode) новый, диффит результаты по `ParsedItem`. Откалибровать веса источников и пороги confidence на этом корпусе.
- Worker для skeleton-имплементации `Pipeline` (V1 в §12.1): создать пакет `backend/parser_app/pipeline/`, реализовать стадии как тонкие обёртки над текущей логикой, добавить feature flag `EXCEL_PARSER_PIPELINE_V2=off`. Старый `parse(...)` остаётся дефолтом.
- Worker для YAML-реестров: вынести лексиконы и hardcoded supplier-hints из `parsers/supplier_profiles.py` и `normalizers.py` в `backend/parser_app/registries/*.yaml` с loader-ом и hot-reload в DEBUG.
- Worker для БД-схемы feedback loop: миграции для `SupplierColumnMapping`, `ParsingFeedback`, `ParseRun` (поля описаны в §9 architecture.md).
- Worker для UI ambiguous-mapping: когда финальный score колонки ниже порога — показывать админу drop-down со всеми кандидатами и причинами; правка сохраняется в `SupplierColumnMapping` с `scope=exact_file|supplier|global`.