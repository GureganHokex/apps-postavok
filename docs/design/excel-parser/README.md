# Устойчивый парсинг Excel-прайсов — точка входа

Этот документ — **единственная точка входа** в дизайн нового пайплайна
парсинга прайс-листов в `apps-postavok`. Если вы открываете каталог
впервые — прочтите его сверху вниз, а потом ныряйте в артефакты по
ссылкам в разделе [«Состав документации»](#состав-документации).

Скоп — **дизайн**, а не код. Изменений в `backend/`, `frontend/`,
`.github/`, `scripts/` в этой ветке нет.

---

## TL;DR

Текущий парсер — god-class на 2963 строки (`backend/parser_app/parsers/excel_parser.py`)
с четырьмя fallback-стратегиями чтения, эвристическим поиском
заголовков и хардкодом профилей поставщиков; параллельно лежит
недоделанный DDD-рефакторинг на 3805 строк, всё ещё реэкспортирующий
тот же god-class. Предлагается заменить его на цепочку stateless-стадий
`Loader → SheetClassifier → MetaExtractor → RegionDetector → HeaderDetector → ColumnMapper → RowExtractor → Normalizer → Validator → Deduplicator → TelemetrySink`,
где каждая стадия имеет формальный DTO-контракт и `Protocol`-интерфейс,
а решения принимаются взвешенным голосованием `Candidate(value, confidence, reasons)`
с конфигурируемыми весами и порогами; знания о синонимах/профилях
вынесены в YAML+БД-реестры с горячей перезагрузкой и feedback-loop
из админки. Это даёт явный `ParseResult.status` (никаких тихих пустых
списков), наблюдаемость каждой стадии, регрессионный harness на корпусе
реальных прайсов и план миграции через feature flag
`EXCEL_PARSER_PIPELINE_V2` (off → shadow → canary → on → drop legacy)
без поломки внешнего API.

## Состав документации

Полный стек артефактов в этом каталоге (порядок чтения — сверху вниз):

| # | Файл | Назначение |
|---|------|-----------|
| 1 | [`README.md`](./README.md) | Этот документ. Точка входа, ключевые решения, action items, открытые вопросы. |
| 2 | [`architecture.md`](./architecture.md) | Архитектурный документ (15 разделов, 5 mermaid-диаграмм): TL;DR, оси изменчивости, контракт `ParsedItem`, граф стадий, confidence/voting, реестры, расширяемость, feedback-loop, производительность, наблюдаемость, backward-compat, план миграции, риски. |
| 3 | [`contracts/parsed_item.schema.json`](./contracts/parsed_item.schema.json) | JSON Schema (draft-07) для `ParsedItem` и вложенного `ParseWarning`. Используется harness'ом и при сериализации `ParseResult` в `ParseRun.result`. |
| 4 | [`contracts/pipeline.py`](./contracts/pipeline.py) | Псевдокод контрактов модулей: `Protocol`-интерфейсы стадий, `dataclass`-DTO, иерархия исключений, перечень стадий. **Без реализации** — это «спецификация в Python». |
| 5 | [`_review/architecture-review.md`](./_review/architecture-review.md) | Verdict ревью архитектурного документа (`pass-with-comments`), 14 осей с классификацией covered/partial/missing, поперечные несоответствия между `architecture.md`, `pipeline.py` и `parsed_item.schema.json`, замечания severity high/med/low. |
| 6 | [`operations.md`](./operations.md) | Операционный дизайн: (A) evaluation harness — корпус, golden snapshots, метрики, A/B, fuzz, ≥10 синтетических edge-фикстур; (B) migration plan — strangler-fig, 6 фаз с exit criteria, точки переключения, откат, соотношение с DDD-слоем; (C) observability — события, Prometheus-метрики, ≥3 алёрта с порогами, дашборд, админ-UI ambiguous. |
| 7 | [`diagrams/`](./diagrams/) *(зарезервировано)* | Каталог под выгрузки mermaid-диаграмм в SVG, если потребуется отдельный артефакт для презентаций. На текущем этапе диаграммы живут inline в `architecture.md` §4.1, §12.1, §14.1, §14.2, §14.3. |

Если вы новый разработчик — читайте в порядке 1 → 2 → 3 → 4 → 5 → 6.
Если вы планируете следующий PR — начинайте с этого README (разделы
[Verdict ревью](#verdict-ревью) и [Action items](#action-items)).

## Ключевые решения

- **Pipeline вместо god-class.** 10 stateless-стадий, каждая —
  отдельный модуль с `Protocol`-интерфейсом и DTO-контрактом
  (`architecture.md` §4, §5; `contracts/pipeline.py`).
- **Candidate + confidence + voting вместо if-цепочек.** Все детекторы
  возвращают `Candidate(value, confidence ∈ [0,1], reasons, source)`;
  финальный выбор — взвешенный voting с порогами `θ_field=0.45` /
  `θ_optional=0.30` (`architecture.md` §6).
- **Источники с весами.** `user=1.0`, `header_exact=0.9`,
  `header_stem=0.75`, `header_fuzzy=0.6`, `header_embedding=0.55`,
  `content=0.65`, `profile=0.5`, `position=0.3` — defaults, калибруются
  на harness'е.
- **YAML + БД реестры вместо хардкода.** Лексиконы (`field_lexicon.yaml`,
  `format_lexicon.yaml`, `currency_lexicon.yaml`, `volume_patterns.yaml`,
  `supplier_hints.yaml`, `meta_patterns.yaml`) и user-overrides
  (`SupplierColumnMapping`, `SupplierProfileOverride`) — внешние данные
  с hot-reload (`architecture.md` §7, §9).
- **Tri-state `ParseResult.status` (`ok` / `partial` / `failed`).**
  Тихий пустой результат запрещён; пустые items без `errors`
  невозможны (`architecture.md` §13).
- **Два класса инцидентов: `ParseWarning` (мягкое) и `ParseError`
  (жёсткое).** Жёсткие останавливают лист или файл, мягкие
  аккумулируются в `ParseResult.warnings` (`architecture.md` §5.1, §13).
- **Backward-compat через тонкий фасад.** Внешний
  `ExcelParser.parse(...) -> List[Dict]` сохраняет сигнатуру
  посимвольно; внутри — диспатч на legacy или v2 по флагу
  (`architecture.md` §12, `operations.md` §B.3).
- **Strangler-fig миграция в 6 фаз.** `harness+corpus` → `v2 за флагом` →
  `shadow` → `canary` → `full v2 + emergency legacy` → `drop v1`,
  каждая с измеримым exit criterion (`operations.md` §B.2).
- **Канонический флаг — `EXCEL_PARSER_PIPELINE_V2`** с алиасом
  `PARSER_V2_ENABLED` и emergency-rollback `PARSER_LEGACY_FORCE`
  (`operations.md` §A intro, §B.1, §B.4).
- **DDD-слой как фундамент v2.** Существующий
  `backend/parser_app/infrastructure/parsers/excel_parser.py` дорабатывается
  под Pipeline — третья реализация не плодится (`operations.md` §B.5).
- **Наблюдаемость per-stage.** ≥14 структурированных событий с
  `parse_run_id`, `file_hash`, `pipeline_version`; ≥3 Prometheus-метрики
  и ≥3 алёрта с числовыми порогами; персистентный `ParseRun` для
  post-mortem (`architecture.md` §11; `operations.md` §C.1, §C.2).
- **Harness как gate миграции.** Pytest-driven, фикстуры в
  `tests/fixtures/excel-synthetic/` (≥10 edge-cases), приватный корпус
  через Git LFS, golden-snapshots в формате `*.expected.json` рядом
  с файлом, A/B отчёт `parser-ab-report.md` (`operations.md` §A).

## Покрытие 14 осей изменчивости

Полная классификация covered/partial/missing с цитатами строк — в
[`_review/architecture-review.md`](./_review/architecture-review.md) §1.
Здесь — сводка с механизмом и риском.

| # | Ось изменчивости | Механизм | Где описано | Риск |
|---|------------------|----------|-------------|------|
| 1 | Положение строки заголовков 1..N, multi-row | `RegionDetector` ищет data-region; `HeaderDetector` пробует склеить N подряд идущих строк (combined ≥ each + 0.1) | `architecture.md` §4 (RegionDetector / HeaderDetector), §6.1 | Конфликт «multi-row + 50% числовых»: две границы могут расходиться (review §15) |
| 2 | Номенклатура колонок: синонимы, опечатки, рус/англ, регистр | `ColumnMapper` с пятью источниками: user → exact → stem → fuzzy → embedding → content → profile → position | `architecture.md` §4 (ColumnMapper), §6.2, §7 (`field_lexicon.yaml`) | Дрейф лексикона: новые синонимы должны попадать в YAML через PR, не как хардкод |
| 3 | Distributor vs Brewery; brewery как префикс / в имени файла / **в значении `beer_name`** | Filename-case: `MetaExtractor` + `supplier_hints.yaml`. Group-header-case: `RowExtractor` + лексикон brewery. **Inline-prefix-case (`"Paradox - Stout 5%"`): не покрыт текущим дизайном** — review поднял это как high-замечание | `architecture.md` §4 (MetaExtractor / RegionDetector / RowExtractor), §6.3 | **HIGH (gap):** нужна стадия `BrewerySplitter` либо подстадия `Normalizer` — см. [Action items](#action-items) #2 |
| 4 | Множество листов, в т.ч. служебные | `SheetClassifier` делит на `data / meta / trash` по плотности, лексикону, доле числовых | `architecture.md` §4 (SheetClassifier), §11 событие `sheet_classified` | Низкий: ложноположительная классификация служебного листа как `data` ловится событием с `confidence` |
| 5 | Объединённые ячейки и group-headers | `Loader` делает unmerge (значение копируется в каждую ячейку); `RegionDetector` помечает group-header строки; `RowExtractor` прокидывает `group_context` | `architecture.md` §4 (Loader / RegionDetector / RowExtractor), §5.1 (`RawRow.group_context`) | Средний: group-header в первой колонке без лексиконного совпадения может уехать в `data` |
| 6 | Цена и остаток в визуально похожих колонках | `ColumnMapper` content-voting: для `price` — `numeric_ratio * range_fit ∈ [10, 100000]`; для `stock` — `numeric_ratio ∧ mean ≤ 10000 ∧ diff_from_price_col` | `architecture.md` §4 (ColumnMapper), §6.2, §13 правило перевыбора | Высокий: «цена с НДС» vs «без НДС» — фикстура 12 в `operations.md` §A.8 |
| 7 | Format-фасовка иконками/короткими словами (банка, can, ж/б, кега…) | `FormatNormalizer` + `format_lexicon.yaml` → enum `{bottle, can, keg, other, unknown}` | `architecture.md` §4 (Normalizer), §7, `parsed_item.schema.json` enum | Низкий: новые формы фасовки решаются добавлением строки в YAML |
| 8 | Объём `0,33 / 0.33 / 330 ml / 1/2 л` | `VolumeNormalizer` + `volume_patterns.yaml` (regex + `multiplier_to_litres`) → `Decimal` в литрах | `architecture.md` §4 (Normalizer), §7 | Средний: schema `parsed_item.schema.json` сейчас отклоняет `"12,50"` — фикс в Action items #1 |
| 9 | Валюта в отдельной колонке vs внутри строки цены (`'250 руб'`) | `CurrencyNormalizer` + `currency_lexicon.yaml`; пример в §4 — `'250 руб → (250, RUB)'` | `architecture.md` §4 (Normalizer), §7 | Низкий: дефолтная валюта — `FileMeta.default_currency` из `MetaExtractor` |
| 10 | Сломанный xlsx (autoFilter, sharedStrings, защищённый лист) | `Loader` sanitize: распаковать zip → удалить битые `<autoFilter>` → починить кодировку sharedStrings → снять защиту листа на чтение | `architecture.md` §4 (Loader), §13 (`LoaderError("autofilter_xml_invalid")`, `"sheet_protected"`) | Низкий: фикстура 11 в `operations.md` §A.8 покрывает |
| 11 | Пустые строки, разделители, промежуточные тоталы | `RowExtractor` классифицирует строки как `data / group_header / total / divider / noise` | `architecture.md` §4 (RowExtractor), §11 события `row_classified`, `row_dropped` | Низкий |
| 12 | Google Sheets как CSV | `Loader` через `csv.Sniffer` (разделитель + кодировка); встраивается как `LoaderAdapter` по mime/ext | `architecture.md` §4 (Loader), §8 plug-in points | Низкий |
| 13 | Мета-данные в имени файла или верхних 1–5 строках | `MetaExtractor` (regex-реестр `meta_patterns.yaml`) → `FileMeta(supplier_name, price_date, default_currency)`; не блокирующий | `architecture.md` §4 (MetaExtractor), §5.1 (`FileMeta`) | Низкий |
| 14 | Пользовательский `supplier_column_mapping` извне (БД из админки) | `ColumnMapper` источник `user` с весом 1.0; `SupplierColumnMapping` с `scope ∈ {exact_file, supplier, global}`; promote-флоу при `hits_count ≥ N` | `architecture.md` §4 (ColumnMapper), §6, §9; `operations.md` §C.4 | Средний: коллизия `field_lexicon.yaml` vs БД-маппинг разрешается весами (`user=1.0` > `header_exact=0.9`), но в §7/§9 это не прописано явно — review (low) |

Итого по review: **13 covered / 1 partial (ось 3) / 0 missing**.
Закрытие partial — задача [Action item #2](#action-items).

## Verdict ревью

**`pass-with-comments`** (полный текст —
[`_review/architecture-review.md`](./_review/architecture-review.md)).

> Архитектурный документ — содержательный, охватывает заявленный
> объём, не имеет пропусков на уровне формальных acceptance.
> Найденные замечания — design-инконсистенции (`field_name` vs `field`,
> `ParseError` наследование, brewery-prefix-в-имени) и недокрытие в
> schema (минимумы для денежных полей). Они должны быть устранены
> **до** старта worker'а skeleton-implementation, потому что именно
> skeleton-стадия закрепит контракты в коде. Регрессионный harness и
> калибровка порогов — корректно вынесены в follow-up worker'ы.

### Реакция планнера на замечания

Каждое замечание из таблицы §13 ревью получает явный адрес: либо
закрывается в первом же PR (skeleton + контракты), либо уезжает в
отдельную задачу/issue, либо в migration plan.

| Severity | Замечание (краткое) | Принимается? | Куда уйдёт |
|----------|---------------------|--------------|------------|
| high | Ось 3: brewery-as-prefix внутри `beer_name` не покрыт | да | Action item #2: добавить `BrewerySplitter` в `architecture.md` §4 + `pipeline.py` (отдельный design-PR перед skeleton) |
| high | `ParseWarning.field` vs `field_name` рассогласовано между arch.md / schema / pipeline.py | да | Action item #1: контракт-фикс единым PR (канон — `field`; pipeline.py использует `field_name` с `metadata={"json_name": "field"}`) |
| high | `ParseError` наследование расходится между §5.1 и pipeline.py; противоречит §13 | да | Action item #1: канон — `ParseError` отдельный класс (как в pipeline.py), §5.1 и §13 правятся под него |
| med | JSON Schema: `price`/`volume`/`stock` без `minimum: 0`; pattern не применяется к числам; `"12,50"` отклоняется | да | Action item #1 (тривиальный hotfix в schema) |
| med | §6.3 `SupplierTypeDetector`: формула не нормализована | да | Action item #2 (тот же design-PR): `clip(sum, 0, 1)` или явная пометка «относительный score» |
| med | §3 + schema: `format_type` — обязательный или нет? | да | Action item #1: добавить в `required` в schema (default есть, поведение consistent) |
| med | §10.1: SLO без плана валидации | да | Action item #4 + migration plan: SLO валидируется harness'ом на ≥30 файлах из production (явный gate перед V5 «drop legacy») |
| med | §5.2 vs pipeline.py: `LoaderError` vs `FileLoadError`; `RowExtractorWarning` без класса | да | Action item #1 (привести §5.2 к именам из pipeline.py) |
| low | §4.1 vs §14.1: две pipeline-диаграммы без подписи редакции | да | Action item #2 (косметика в одном PR с brewery-splitter) |
| low | §11 + §3 + §9: источник кандидата теряется при персистенции | принимается частично | issue «расширить `field_confidences` до `dict[str, Candidate]` или добавить `field_sources`» — **не блокер skeleton'а** |
| low | §10.2: top-200 cols без статистики корпуса | да | Action item #4 (откалибровать на harness-корпусе вместе с порогами confidence) |
| low | §9 опечатка «Petr-loop» → «Feedback-loop» | да | Action item #1 (one-liner) |
| low | §15: multi-row + «50% числовых» — конфликт правил | да | Action item #2 (явный приоритет: multi-row кандидат → старт data = `max(rows)+1`, игнорировать 50%-правило в пределах кандидата) |
| low | §6: не описан случай «никакой кандидат не закрыл optional поле» | да | Action item #2 (одна фраза в §6: `field_confidences[f]=0`, поле = `None`) |
| low | §12: нет явного раздела «Rollback» | да | Action item #1 (одна фраза в §12: `flag=off` глобально, V1-фасад транспарентно откатывается) |
| low | §7 / §9: коллизия lexicon vs БД-маппинг разрешается весами, но не прописана | да | Action item #2 (одна фраза в §7) |
| low | §14.2 sequence: куда деваются `invalid_items` после loop'а | да | Action item #2 (одна фраза или mermaid-комментарий в §14.2) |

Open questions из ревью (калибровка весов, корпус, YAML-реестры, БД-схема feedback,
admin-UI) — корректно эскалированы, не блокируют design-фазу. Они уходят
в [Action items](#action-items) #4–#10 и [Открытые вопросы](#открытые-вопросы).

## Action items

Упорядочены по приоритету. Каждый пункт = один следующий PR.

1. **Контракт-фикс пакетом (high+med+low дизайн-патч).** Один design-PR
   правит `architecture.md` и `contracts/`:
   - привести `ParseWarning.field` к единому имени во всех трёх артефактах
     (канон — `field` в JSON; в pipeline.py хранить как `field_name` с
     `metadata={"json_name": "field"}`);
   - синхронизировать `ParseError` (отдельный класс, как в pipeline.py) +
     обновить §5.1 и §13;
   - в `parsed_item.schema.json` добавить `minimum: 0` для `price`,
     `volume`, `stock`; зафиксировать «Decimal как строка с точкой»;
     добавить `format_type` в `required`;
   - в §5.2 переименовать `LoaderError` → `FileLoadError`,
     `RowExtractorWarning` → `ParseWarning(code="no_data_rows")`;
   - в §12 добавить раздел «Rollback» (одна фраза);
   - исправить опечатку «Petr-loop» → «Feedback-loop» (§9 строка 580).
2. **Закрытие оси 3 + остальные low-замечания дизайна.** Дизайн-PR:
   - добавить `BrewerySplitter` (либо как пятую под-стадию `Normalizer`,
     либо как опциональную стадию между `RowExtractor` и `Normalizer`)
     в `architecture.md` §4 + добавить confidence-формулу в §6 + добавить
     `Protocol` в `pipeline.py`;
   - нормализовать формулу `SupplierTypeDetector` (§6.3) — `clip(sum, 0, 1)`;
   - явно прописать приоритет `multi-row > 50%-числовых` (§6.1 / §15);
   - явно прописать поведение «никакой кандидат не закрыл optional» (§6);
   - явно прописать разрешение коллизии lexicon vs БД (§7);
   - подписать `§14.1` как «компактная версия §4.1» и добавить комментарий
     про `invalid_items` в §14.2;
   - подписать defaults весов/порогов как «placeholder, калибруется на
     harness'е» (§6).
3. **Скаффолд `parsers_v2/` + harness-каркас.** Реализационный PR (фаза 0
   из `operations.md` §B.2):
   - создать `backend/parser_app/parsers_v2/` с пустыми модулями стадий
     по списку из `pipeline.py` (`Loader`, `SheetClassifier`, ...,
     `TelemetrySink`) — каждый реализует `Protocol` с `raise
     NotImplementedError("stage scaffold")`, чтобы DI-каркас и тесты
     контрактов прогонялись;
   - вынести DTO из `contracts/pipeline.py` в реальный код
     (`parsers_v2/contracts.py`);
   - завести `tests/fixtures/excel-synthetic/` + `scripts/make_excel_fixtures.py`
     (≥10 фикстур из `operations.md` §A.8);
   - добавить pytest-маркеры `parser_eval`, `slow` в `pyproject.toml` /
     `pytest.ini`;
   - **никакой** имплементации стадий — только каркас и зелёный harness
     на синтетике с заглушками.
4. **`HeaderDetector` + `RegionDetector` (первая боевая стадия).**
   Реализационный PR: confidence-формула из §6.1, multi-row, лексикон
   через YAML-реестр `field_lexicon.yaml` (под flag-декоратором).
   Параллельно — реальная реализация `Loader` с sanitize-шагами
   (`autoFilter` / `sharedStrings`). Exit criterion: harness на синтетике
   ≥ 95% PASS по полю `beer_name`.
5. **`ColumnMapper` + `Normalizer` + `Validator`.** Реализационный PR:
   все 5 источников кандидатов; content-voting для `price` vs `stock`;
   `VolumeNormalizer` / `CurrencyNormalizer` / `FormatNormalizer` /
   `AbvNormalizer` / `BrewerySplitter`; range-checks. Exit: harness
   ≥ 95% PASS по `price`, `volume`, `format_type`.
6. **Реестры (YAML + БД) + feedback-loop.** Реализационный PR:
   `field_lexicon.yaml`, `format_lexicon.yaml`, `currency_lexicon.yaml`,
   `volume_patterns.yaml`, `supplier_hints.yaml`, `meta_patterns.yaml`
   с loader'ом и hot-reload по mtime в DEBUG; модели `SupplierColumnMapping`,
   `SupplierProfileOverride`, `ParseRun`, `ParsingFeedback` (Django
   migrations); decorator `@register_*` для plug-in points.
7. **`parse_dispatcher` + флаги + shadow-режим.** Реализационный PR
   (фазы 1–2 из `operations.md` §B.2):
   `backend/parser_app/services/parse_dispatcher.py` по псевдокоду §B.3;
   синонимы env `EXCEL_PARSER_PIPELINE_V2` / `PARSER_V2_ENABLED` +
   emergency-флаг `PARSER_LEGACY_FORCE` + ADR в `docs/adr/` фиксирующий
   единый канон; sampling/async-сравнение в shadow; первый Prometheus-метрик
   `parser_runs_total{status}` и `parser_parse_seconds`. Exit:
   `parser_failure_rate < 0.5%` v2 на shadow-week.
8. **Observability + алёрты + дашборд + админ-UI ambiguous.**
   Реализационный PR (`operations.md` §C):
   structured logging для всех 14 событий (§11);
   3 Prometheus-метрики + ≥3 алёрта с порогами (`A1`/`A2`/`A3`);
   Grafana-дашборд в репо (JSON);
   admin-UI блок «колоночный выбор» (`scope ∈ {exact_file, supplier, global}`)
   при `field_confidences[f] < θ_field`.
9. **A/B + canary rollout.** Реализационный PR (фазы 3–4 из §B.2):
   `parser-ab-report.md` генератор (`Δ F1`, `Δ R_item`, переходы статусов);
   allow-list по `Supplier.id`; drill отката; per-supplier rollout. Exit:
   `R_item^strict` v2 не хуже baseline более чем на δ=0.01 у пилотов; 14
   календарных дней зелёных алёртов.
10. **Drop legacy (фаза 5).** Удаление `backend/parser_app/parsers/excel_parser.py`,
    миграция последних эвристик из `parsers/supplier_profiles.py` в YAML;
    убрать реэкспорт из `infrastructure/parsers/excel/__init__.py`;
    update runbook'ов. Gate: 14 осей зелёные в harness'е на ≥30 файлах
    приватного корпуса; SLO P95 валидирован на проде.

## Открытые вопросы

Нужны решения owner'а проекта/пользователя — без них следующие worker'ы
не могут двигаться без рисков.

1. **Калибровка весов источников и порогов confidence.** Дефолты
   (`user=1.0 ... position=0.3`, `θ_field=0.45`, `θ_optional=0.30`,
   header-формула `0.4/0.3/0.2/0.1`, fuzzy-фильтры `0.85/0.7`) —
   placeholder. Нужны цифры с реального корпуса. Решается совместно с
   Action item #3 (harness готовит данные) и #4 (HeaderDetector
   калибруется первым).
2. **Источники приватного корпуса прайсов.** Сколько файлов в нём, где
   хранится (Git LFS submodule vs object storage), кто отвечает за
   анонимизацию ПДн / маскировку цен. От этого зависит SLA harness'а
   (`operations.md` §A.2) и gate миграции (минимум 30 файлов до V5).
3. **Окончательный канон env-флага.** `EXCEL_PARSER_PIPELINE_V2` (прод)
   vs `PARSER_V2_ENABLED` (оркестрационное ТЗ): нужен ADR в `docs/adr/`
   с фиксацией одного имени, поведения алиаса и семантики
   `PARSER_LEGACY_FORCE`. Action item #7 не стартует без этого решения.
4. **Φ_req — обязательные поля для item-level recall.** В `operations.md`
   §A.4 указан минимум `beer_name` + `price` «плюс доменные». Нужна
   фиксация: входят ли `volume`, `format_type`, `currency`, `brewery` в
   обязательное множество для `R_item^strict` (влияет на gate в §B.2).
5. **Источник кандидата при персистенции `ParseRun`.** Расширять
   `field_confidences: dict[str, float]` до `dict[str, Candidate]` или
   добавить отдельное поле `field_sources: dict[str, str]`? Влияет на
   schema `parsed_item.schema.json` и на сложность post-mortem-анализа.
   Review-замечание (low), но решать до Action item #6 (модель
   `ParseRun.result`).
6. **Promote-флоу синонимов в `field_lexicon.yaml`.** При `hits_count ≥ N`
   на `SupplierColumnMapping` инфраструктура «предлагает» админу promote
   синоним. Кто фактический owner ревью этих PR (data-роль или backend)
   и какое значение `N` — нужно решение перед Action item #6.
7. **Параллелизм листов.** `EXCEL_PARSER_PARALLEL_SHEETS` —
   ThreadPool (I/O) vs ProcessPool (CPU). Принципиальный выбор отложен
   до измерений на корпусе; зависит от профиля файла (узкие/широкие).
   Не блокер, но желательно решить до Action item #5.
