<!-- orchestrate handoff
task: aggregate-design
branch: orch/excel-parser-resilient-design/aggregate-design
agentId: bc-e4c16fa3-d17a-4af8-a051-35f3e7b6ce18
runId: run-c1f0b80d-65ac-4873-933d-f4bb68473a67
resultStatus: finished
finishedAt: 2026-05-08T18:42:39.028Z
-->

All work is committed and pushed; PR #6 updated. `.orchestrate/` left intact. Now the handoff:

## Status
success

## Branch
`orch/excel-parser-resilient-design/aggregate-design`

## What I did
- На ветке `orch/excel-parser-resilient-design/aggregate-design` уже лежал предыдущий аггрегационный `README.md` (290 строк, все 7 разделов, 14 осей, верный verdict). Сохранил его как базу — повторил pattern из `_review/architecture-review.md`, где second-pass верификатор не force-push'ил поверх первой проходки.
- Поверх добавил коммит `b5d25bf` с интеграцией второго прохода ревью: в таблицу «Реакция планнера на замечания» добавлен столбец `ID ревью`, новые строки для **M-3+OQ-1** (фасад `parse(...) -> list[dict]` теряет `ParseResult.status`), **M-7** (Loader sanitize vs §15 риски — нужен ADR), **M-5** (user-mapping на несуществующую колонку), **M-6** (hot-reload только в DEBUG), **M-2** (TL;DR без `MetaExtractor`), `m-2/m-3/m-8/m-9/m-11`. Цитата verdict теперь содержит оба прохода.
- В «Открытые вопросы» добавлены три блокера контракта v2 (voting `argmax` vs `sum`/`mean`, контракт фасада при `failed`, scope-коллизия user-mapping) — теперь 10 пунктов, прежние 1–7 смещены на 4–10. Перенумерация согласована с Action items.
- Обновил draft PR #6 (`docs(excel-parser): aggregate design README — единая точка входа`) свежим описанием с историей коммитов и сводным verdict.
- Изменений вне `docs/design/excel-parser/README.md` нет; `backend/`, `frontend/`, `.github/`, `scripts/`, `architecture.md`, `operations.md`, `contracts/**`, `_review/**` не трогал; `.orchestrate/` оставлен в покое.

## Measurements
- `LOC(docs/design/excel-parser/README.md): 0 → 341` (новый файл; первый коммит — 290, после интеграции second-pass — 341)
- `sections (TL;DR/Состав/Решения/14 осей/Verdict/Action items/Открытые вопросы): n/a → 7`
- `axes covered in table: 14 / 14`
- `Action items numbered 1..N: 1..10`
- `Open questions numbered 1..N: 1..10`
- `commits on branch ahead of main: 0 → 2` (`7766b32`, `b5d25bf`)

## Verification
not-verified

Design-only документ; формальные acceptance проверены через `Grep` (все 7 заголовков `^## ...` присутствуют, 14 строк `^| <digit> |` в таблице осей, нумерация Action items и Open questions последовательна 1..10). Семантическая проверка двух коммитов на ветке: первый коммит — полная аггрегация прежнего worker'а, второй коммит — additive-интеграция second-pass review без удаления контента.

## Notes, concerns, deviations, findings, thoughts, feedback
- **Главная находка:** на ветке `aggregate-design` уже был коммит `7766b32` с готовым README на 290 строк от предшествующего worker'а — все acceptance criteria уже выполнены. Я не force-push'ил поверх, а пошёл по precedent'у `_review/architecture-review.md` (где second-pass верификатор сохранил первого, добавил под отдельным заголовком). Здесь, поскольку README — единый документ и две точки входа невозможны, я просто обогатил существующий файл явными ID из второго прохода ревью и закрыл gap'ы (M-3 + OQ-1 фасад silent-empty, M-7 Loader sanitize, M-5/M-6, voting strategy в OQ).
- **Содержательно:** прежний README уже включал findings и first-pass и second-pass review без явных ID; моё дополнение — это explicit ID-mapping, что облегчает следующему fix-architecture worker'у грепать ревью по идентификатору.
- **Обнаруженная inconsistency, которую не правил:** в таблице 14 осей (строка 112 README) для оси 10 в столбце «Механизм» ещё стоит «снять защиту листа на чтение» — это цитата из `architecture.md` §4. Это противоречит §15 (M-7), но я не правил, так как описание оси отражает то, что **сейчас** написано в `architecture.md`, а решение об ADR ушло в Action item #1 и в строку M-7 реакции планнера. После fix-architecture-PR строка автоматически станет согласованной.
- **Опасения:** Action item #1 в существующем README уже агрегирует high+med+low в один большой PR. Это может вырасти. После моих добавлений (M-3, M-7, M-5, M-2, m-2/m-3/m-8/m-9/m-11) #1 ещё больше — fix-architecture worker может разумно разделить на два sub-PR (контрактный + Loader-ADR), но решение оставляю планнеру.
- **Соответствие user-rules:** проект на Python (Django), документация на русском — соответствует «один язык проекта», «сначала архитектурная идея, потом код» (документ — design-only без правок кода).

## Suggested follow-ups
- Worker `fix-architecture` (must-fix перед skeleton): атакует Action item #1 + #2 в строгой последовательности, отдельный sub-PR на ADR Loader-стратегии (M-7) и ADR контракта фасада (M-3 / OQ-1) — оба ADR живут в `docs/adr/`, не в `docs/design/excel-parser/`.
- ADR-worker по `EXCEL_PARSER_PIPELINE_V2` vs `PARSER_V2_ENABLED` + `PARSER_LEGACY_FORCE` (Open question #6) — без него `parse_dispatcher.py` (Action item #7) не стартует.
- Решение по voting strategy `argmax` vs `sum`/`mean` (Open question #1 / M-9 / OQ-3) — нужно от owner'а **до** старта Action item #4 (HeaderDetector калибруется первым на harness'е).
- Privacy-lead worker: политика приватного корпуса прайсов (Open question #5) — анонимизация ПДн, маскировка цен, Git LFS submodule vs object storage. От этого зависит SLA harness'а и gate перед V5 «drop legacy».