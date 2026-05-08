<!-- orchestrate handoff
task: aggregate-design
branch: orch/excel-parser-resilient-design/aggregate-design
agentId: bc-1eeb3c3f-0663-424f-ba0a-1fd120a8169a
runId: run-2262cc17-2a5b-4bc9-b531-2f352c3dde5c
resultStatus: finished
finishedAt: 2026-05-08T18:33:29.537Z
-->

## Status
success

## Branch
`orch/excel-parser-resilient-design/aggregate-design`

## What I did
- Прочитал три upstream-артефакта (`architecture.md`, `architecture-review.md`, `parsed_item.schema.json`, `pipeline.py`, `operations.md`) с веток `design-architecture` и `design-operations` через `git show` (на `main` они физически не лежат — это будет интегрировано планнером).
- Создал ветку `orch/excel-parser-resilient-design/aggregate-design` от `main`.
- Написал `docs/design/excel-parser/README.md` (290 строк) — единую точку входа в стек документации:
  1. **TL;DR** — pipeline из 10 stateless-стадий вместо god-class, candidate+voting, реестры, tri-state status, миграция через flag.
  2. **Состав документации** — таблица из 7 артефактов с порядком чтения и описанием каждого.
  3. **Ключевые решения** — 12 буллетов с цитатами разделов исходников.
  4. **Покрытие 14 осей** — таблица `ось | механизм | где описано | риск`, все 14 строк заполнены (13 covered, 1 partial — ось 3, явно помечена как gap).
  5. **Verdict ревью** — копия `pass-with-comments` + матрица из 17 замечаний (high/med/low) с явным адресом куда уходит каждое (Action items #1–#10, issue, migration plan).
  6. **Action items** — 10 пронумерованных PR-ов в порядке приоритета: контракт-фикс → закрытие оси 3 → скаффолд + harness → HeaderDetector → ColumnMapper/Normalizer/Validator → реестры + feedback-loop → dispatcher+shadow → observability+админ-UI → A/B+canary → drop legacy.
  7. **Открытые вопросы** — 7 пунктов для owner'а: калибровка порогов, источник корпуса, канон env-флага (ADR), Φ_req, персистенция кандидата, promote-флоу синонимов, parallelism.
- Закоммитил, запушил и открыл draft PR [#6](https://github.com/GureganHokex/apps-postavok/pull/6).

## Measurements
- `LOC(docs/design/excel-parser/README.md): 0 → 290`
- `sections_present: 0 → 7` (TL;DR, Состав документации, Ключевые решения, Покрытие 14 осей, Verdict ревью, Action items, Открытые вопросы)
- `axes_in_table: required 14 → present 14` (13 covered, 1 partial)
- `action_items_numbered: required ≤10 → 10`
- `files_modified_outside_scope: 0 == 0`

## Verification
not-verified

Design-only документ; смысловая полнота проверена по acceptance: 7 разделов на месте (`grep "^##"` подтверждает), 14 строк в таблице осей (`awk + grep` подтверждает), 10 action items пронумерованы 1..10, ссылки на upstream-файлы (`architecture.md`, `contracts/`, `_review/`, `operations.md`, `diagrams/`) консистентны с тем, что лежит на upstream-ветках.

## Notes, concerns, deviations, findings, thoughts, feedback
- README ссылается на файлы (`architecture.md`, `_review/architecture-review.md`, `contracts/parsed_item.schema.json`, `contracts/pipeline.py`, `operations.md`, `diagrams/`), которые в моей ветке физически отсутствуют — они приходят с upstream-веток `design-architecture` и `design-operations`. Это сознательное решение: задача явно запрещает мне их трогать (`Do NOT modify`). Когда планнер сольёт ветки в `main` или на интеграционную ветку — все ссылки станут рабочими.
- Реакция планнера на ревью оформлена как таблица «замечание → принимается? → куда уходит» вместо вольного пересказа: это даёт явный аудит-trail и связку с Action items.
- В `_review/architecture-review.md` 17 замечаний (high/med/low в сводной таблице §13). 16 учтены в Action items #1 и #2, одно (low: «источник кандидата теряется при персистенции») вынесено в отдельный issue + Открытые вопросы #5, потому что оно меняет shape `field_confidences` и должно быть решено owner'ом до Action item #6.
- Open questions из handoff'ов upstream-ов (флаг `EXCEL_PARSER_PIPELINE_V2` vs `PARSER_V2_ENABLED`, Φ_req, корпус, promote-флоу) собраны в раздел «Открытые вопросы» — корректно эскалированы, без потерь.
- Я не создавал и не правил `architecture.md`/`operations.md`/`contracts/`/`_review/`/`diagrams/` — это только агрегационный README.
- `.orchestrate/` не трогал.

## Suggested follow-ups
- Action item #1 (контракт-фикс пакетом) — самый дешёвый и критический: разнобой `field` vs `field_name` зафиксируется в коде на skeleton-стадии, если не закрыть его сейчас.
- Action item #3 (скаффолд `parsers_v2/` + harness) — стартовать сразу после #1+#2: даёт зелёный baseline для всех последующих стадий.
- Прежде чем стартовать Action item #7 (`parse_dispatcher` + флаги), нужен ADR в `docs/adr/` фиксирующий канон env-флага — это Открытый вопрос #3, требует решения owner'а.
- Action item #10 (drop legacy) можно начинать только после того, как 14 осей зелёные на ≥30 файлах приватного корпуса — этот gate явно прописан и в `architecture.md` §12.1, и в `operations.md` §B.2, и в README.