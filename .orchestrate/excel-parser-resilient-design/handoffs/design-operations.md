<!-- orchestrate handoff
task: design-operations
branch: orch/excel-parser-resilient-design/design-operations
agentId: bc-254ccd2d-7368-49d9-b71e-a4cd53cff944
runId: run-afd0770c-012b-4c36-8d65-1644aee763be
resultStatus: finished
finishedAt: 2026-05-08T18:22:24.848Z
-->

## Status
success

## Branch
orch/excel-parser-resilient-design/design-operations

## What I did
- Собрал после rebase единственный файл `docs/design/excel-parser/operations.md`: три части (A harness, B strangler из 6 фаз с exit criteria, C telemetry/дашборд/admin UI), канонический флаг `EXCEL_PARSER_PIPELINE_V2` с синонимом `PARSER_V2_ENABLED`, таблица метрик с формулами precision/recall/F1 по полю и двум вариантам item-level recall, путь к эталону `manage.py parser_update_golden`, A/B отчёт `parser-ab-report.md`, ≥10 синтетических сценариев (до 13 в таблице), псевдокод `parser_app/services/parse_dispatcher.py` с shadow-режимом, обоснованное решение развивать существующий DDD-слой без третьей реализации, ≥3 прод-алёрта с порогами.
- Отправил изменения на `origin` и обновил draft PR [№5](https://github.com/GureganHokex/apps-postavok/pull/5) к `main`.

## Measurements
- `sections (частей A+B+C): n/a → 3`
- `LOC(docs/design/excel-parser/operations.md): 268`
- фаз миграции с exit criteria: `5 → >=5` (**6** явных строк в таблице B.2)
- алёртов с числовым порогом в C.2: `>=3 → 4` (три обязательных по ТЗ + один опционально для shadow)
- `pytest parser harness в репо: 0 файлов изменений → 0` (**дизайн-only** по acceptance)

## Verification
not-verified

Design-only документ без исполнимых тестов в этом PR; смысловая полнота — по чек-листу acceptance в задаче.

## Notes, concerns, deviations, findings, thoughts, feedback
- На удалённой ветке уже был набросок `operations.md`; при `git pull --rebase` был **add/add conflict** — итог **слита** версия из этой задачи с учётом деталей предшественника и требований acceptance (две формулы item-recall для ясности: покрывающее и строгое по \(\Phi_{\mathrm{req}}\)).
- Верхний handoff архитектуры упомянул путь **`infrastructure/parsers/`** без префикса `parser_app`; в документе уточнён фактический путь репозитория `backend/parser_app/infrastructure/...`.

## Suggested follow-ups
- Отдельный worker: реализация `tests/fixtures/excel-synthetic/`, скрипт `scripts/make_excel_fixtures.py`, `pytest` маркеры и реальный `.github/workflows/parser-tests.yml`.
- Реализовать `parser_update_golden`, `dispatch_parse`/флаги в settings и сбор Prometheus-метрик по событиям из §11 `architecture.md`.
- ADR: зафиксировать **единое** имя env-переменной и семантику `PARSER_LEGACY_FORCE` относительно `EXCEL_PARSER_PIPELINE_V2`.