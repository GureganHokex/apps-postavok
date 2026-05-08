<!-- orchestrate handoff
task: design-operations
branch: orch/excel-parser-resilient-design/design-operations
agentId: bc-cdf402e6-dd69-4e38-b6cf-eaf19409d36d
runId: run-4a23e9e5-d050-4146-a079-0d43d0162520
resultStatus: finished
finishedAt: 2026-05-08T18:20:39.844Z
-->

## Status
success

## Branch
orch/excel-parser-resilient-design/design-operations

## What I did
- Добавил `docs/design/excel-parser/operations.md`: **часть A** (цели harness, корпус и хранение, golden JSON + CLI-спека обновления, таблица метрик с формулами precision/recall/F1 и item-level recall, дизайн pytest/CI, A/B с v1, fuzz, 12 синтетических edge-case xlsx), **часть B** (strangler + `PARSER_V2_ENABLED`, фазы 0–5 с exit criteria, псевдокод `parse_dispatcher.py`, откат, решение в пользу доведения существующего DDD в `infrastructure/` до v2, чек-лист ролей, риски), **часть C** (прод-логи/метрики, ≥3 алёрта с порогами из ТЗ + доп. shadow-mismatch, эскиз дашборда, UI для ambiguous mapping).
- Закоммитил и запушил ветку; открыл **draft PR #5** в `main`.

## Measurements
- `LOC(docs/design/excel-parser/operations.md)`: 0 → 278
- `migration_phases_with_exit_criteria`: 0 → 6 (фазы 0–5)
- `alerts_with_explicit_thresholds`: 0 → 4 (три обязательных из ТЗ + один для shadow)
- `synthetic_edge_case_fixtures_specified`: 0 → 12
- `PR(draft)`: none → #5

## Verification
type-check-only (документ сверялся с acceptance-чеклистом ТЗ; исполняемый код и CI не менялись)

## Notes, concerns, deviations, findings, thoughts, feedback
- В тексте зафиксировано расхождение имён флага между handoff архитектуры (`EXCEL_PARSER_PIPELINE_V2`) и этим ТЗ (`PARSER_V2_ENABLED`); рекомендован один канон + алиас в settings.
- Workflow `.github/workflows/parser-tests.yml` и скрипт `scripts/make_excel_fixtures.py` **намеренно не добавлялись** (вне области PR), только описаны как последующая имплементация.
- Точное значение порога \(\tau\) для матчинга строк в harness оставлено параметром конфигурации с калибровкой по корпусу — как и веса voting из архитектуры.

## Suggested follow-ups
- Отдельный PR: минимальный pytest-harness + `tests/fixtures/excel-synthetic/` + первые golden под synthetic.
- Отдельный PR: `.github/workflows/parser-tests.yml` по спецификации из документа.
- Отдельный PR: скрипт генерации синтетических xlsx из таблицы A.8 и `manage.py parser_update_golden`.
- Принять единое имя feature-flag в коде/settings и синхронизировать `architecture.md` при необходимости.