# Verdict: pass-with-comments

Критическое ревью документа `docs/design/excel-parser/architecture.md`,
JSON Schema `docs/design/excel-parser/contracts/parsed_item.schema.json`
и псевдокода `docs/design/excel-parser/contracts/pipeline.py` после
worker'а `design-architecture` (ветка
`orch/excel-parser-resilient-design/design-architecture`, коммит `20fb4e9`).

Ревью проведено по 11 пунктам чек-листа верификации. Все формальные
acceptance worker'а соблюдены (15 разделов, 5 mermaid-диаграмм, валидный
draft-07 JSON Schema, ast.parse проходит, 14 осей упомянуты). Найденные
замечания — содержательные и контрактные несвязанности, не блокирующие
пайплайн в целом, но требующие правки перед фиксацией дизайна как
основы для следующих worker'ов (skeleton-implementation и regression
harness).

## Резюме

- Что хорошо: чёткий граф стадий и контракты DTO, явный
  `ParseResult.status` против тихого пустого результата (раздел §13),
  формальный confidence/voting с весами и порогами (§6), feedback-loop
  через `SupplierColumnMapping` (§9), реестры в YAML+БД (§7), план
  миграции через feature flag в 5 шагов (§12.1), 5 mermaid-диаграмм без
  рассинхрона стадий между §4.1 / §14.1 / §14.2 / §14.3.
- Что плохо: ось 3 («brewery как префикс внутри строки названия»)
  адресована только частично — ни одна стадия не описывает
  splitter `"Paradox - Stout 5%"` → `(brewery, beer_name)`;
  `ParseWarning.field` vs `field_name` расходится между §5.1, schema и
  pipeline.py; JSON Schema не закрывает `minimum: 0` для `price`,
  `volume`, `stock` (regex применяется только к строковой форме);
  CSV-decimal (`12,50`) не пройдёт schema-pattern, хотя §3 говорит
  «Decimal как строка для сохранения точности».
- Что обязательно поправить: единый источник правды для
  `ParseWarning`/`ParseError` (одно из: `field` или `field_name`,
  во всех трёх артефактах одинаково); явный шаг или подстадия для
  brewery-as-prefix в названии (§4 ColumnMapper или Normalizer);
  `minimum: 0` в schema для денежных/количественных полей; уточнить в
  §5.1, что `ParseError` — отдельный тип, а не наследник `ParseWarning`
  (или привести pipeline.py к наследованию).

## 1. Покрытие 14 осей изменчивости

| #  | Ось                                                              | Статус            | Где / комментарий                                                                                                                                                                                                |
|----|------------------------------------------------------------------|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | Положение строки заголовков 1..N, multi-row                      | covered           | §4 `RegionDetector` (стр. 201–208), `HeaderDetector` (стр. 210–216), §6.1 (стр. 442–460). Multi-row case с правилом «combined ≥ each individual + 0.1» — корректно.                                              |
| 2  | Номенклатура колонок: синонимы, опечатки, рус/англ, регистр      | covered           | §4 `ColumnMapper` (стр. 218–240), §6.2 (стр. 461–478), §7 `field_lexicon.yaml` (стр. 510–523). Лексикон exact→stem→fuzzy→embedding явно задан.                                                                  |
| 3  | Distributor vs Brewery, brewery как префикс / в имени файла      | partially covered | Имя файла → §4 `MetaExtractor` (стр. 194–199) + §6.3 (стр. 479–489) + `supplier_hints.yaml`. **Не покрыт случай brewery-as-prefix внутри значения колонки `beer_name`** (например `"Paradox - Stout 5%"`). Ни одна стадия не описывает splitter; §3 хранит `brewery: str?` как отдельное поле, но Normalizer (§4 стр. 257–270) не объявляет `BrewerySplitter` для извлечения brewery из строки названия. См. замечание (high) ниже. |
| 4  | Множество листов, в т.ч. служебные                               | covered           | §4 `SheetClassifier` (стр. 182–192) + §11 событие `sheet_classified`.                                                                                                                                            |
| 5  | Объединённые ячейки и group-headers                              | covered           | §4 `Loader` unmerge (стр. 176–178), `RegionDetector` group_headers (стр. 201–208), `RowExtractor` классификатор `group_header` (стр. 246–253). DTO `RawRow.group_context` зафиксирован.                          |
| 6  | Цена и остаток в визуально похожих колонках                      | covered           | §4 `ColumnMapper` content voting (стр. 230–232), §6.2 stock-формула с `diff_from_price_col` (стр. 471–472), §13 правило перевыбора кандидата (стр. 736–737).                                                     |
| 7  | Format в виде иконок/коротких слов (банка, can, ж/б, кега…)      | covered           | §4 `Normalizer` → `FormatNormalizer` (стр. 265), §7 `format_lexicon.yaml`. Соответствует enum `FormatType` в pipeline.py:55–60.                                                                                  |
| 8  | Объём `0,33 / 0.33 / 330 ml / 1/2 л`                             | covered           | §4 `Normalizer` → `VolumeNormalizer` (стр. 262–263), §7 `volume_patterns.yaml`. Pipeline.py:298–306 фиксирует `VolumePattern(regex, multiplier_to_litres)`.                                                       |
| 9  | Валюта в отдельной колонке vs внутри строки цены ('250 руб')     | covered           | §4 `Normalizer` → `CurrencyNormalizer` (стр. 264) с явным примером `'250 руб → (250, RUB)'`. §7 `currency_lexicon.yaml`.                                                                                          |
| 10 | Сломанный xlsx (autoFilter, sharedStrings, защищённый лист)      | covered           | §4 `Loader` sanitize (стр. 167–174). §13 правило `LoaderError("autofilter_xml_invalid")` и `LoaderError("sheet_protected")` (стр. 729, 854).                                                                      |
| 11 | Пустые строки, разделители, промежуточные тоталы                 | covered           | §4 `RowExtractor` классификация `total / divider / noise` (стр. 246–253) + §11 события `row_classified`, `row_dropped`.                                                                                          |
| 12 | Google Sheets как CSV                                            | covered           | §4 `Loader` CSV-адаптер (стр. 175). `csv.Sniffer` для разделителя/кодировки.                                                                                                                                     |
| 13 | Мета-данные в имени файла или верхних 1–2 строках                | covered           | §4 `MetaExtractor` (стр. 194–199) + DTO `FileMeta` в pipeline.py:124–129.                                                                                                                                        |
| 14 | Пользовательский `supplier_column_mapping` извне                 | covered           | §4 `ColumnMapper` источник `user` с весом 1.0 (стр. 226–228). §6 таблица весов (стр. 421–430). §9 хранение в БД (стр. 551–578).                                                                                  |

Итого: **13 из 14 осей покрыты полностью, 1 ось покрыта частично**
(brewery-as-prefix внутри значения колонки имени).

## 2. Замечания по разделам документа

### (high) §4 + §3, ось 3 — нет стадии для brewery-as-prefix-в-имени

`docs/design/excel-parser/architecture.md`:43–63 в матрице осей пишет
для оси 3: «brewery как префикс / в имени файла». В §4 ниже описаны
два механизма: (а) `MetaExtractor` (стр. 194–199) для случая «brewery
в имени файла»; (б) `RegionDetector` + `RowExtractor` (стр. 201–253)
для group-header-строк. **Случай, когда brewery встроен в строку
названия позиции** (характерный для дистрибьюторов: `"Paradox - Imperial
Stout, 0.5L"`), нигде не описан как отдельная стадия или sub-pipeline
у `Normalizer`. `Normalizer` (стр. 257–270) перечисляет четыре
делегата (volume / currency / format / abv), но не `BrewerySplitter` /
`NameDecomposer`.

Что добавить:
- В §4 в описание `Normalizer` добавить пятую под-стадию
  `BrewerySplitter` или вынести её в отдельную опциональную стадию
  между `RowExtractor` и `Normalizer`.
- В §6 описать confidence для splitter (regex по разделителям
  `"-", " — ", ":", "()"` + проверка по brewery-лексикону).
- В §15 это уже частично упомянуто как риск
  («Group-header строки трактуются как data», стр. 851), но это **не
  тот же случай**.

Опционально: в `pipeline.py` добавить `BrewerySplitter(Protocol)` или
зафиксировать как ответственность `Normalizer`.

### (high) §5.1 + pipeline.py:182–196 + schema:130–148 — расхождение `ParseWarning.field` vs `field_name`

Один и тот же атрибут именуется по-разному в трёх артефактах:

| Артефакт                                | Имя поля     | Цитата                                                                  |
|-----------------------------------------|--------------|-------------------------------------------------------------------------|
| `architecture.md` §5.1, стр. 372        | `field`      | `field: str \| None`                                                    |
| `pipeline.py` строка 187, 196           | `field_name` | `field_name: Optional[str] = None`                                      |
| `parsed_item.schema.json` строка 146    | `field`      | `"field": { "type": ["string", "null"] }`                               |

Pipeline.py использует `field_name`, чтобы избежать столкновения с
`dataclasses.field`, что технически корректно. Но schema и текст §5.1
называют поле `field`. Это значит, что если `ParseWarning` будут
сериализовать через `dataclasses.asdict`, ключ JSON получится
`field_name` и не пройдёт `additionalProperties: false` в schema (либо
schema принимает `field`, которого нет в DTO — оба варианта
рассогласованы).

Что добавить:
- Принять одно имя как канон (рекомендация: `field` в JSON, поле
  Python оставить как `field_name` с `metadata={"json_name": "field"}` или
  переименовать в `field` с явным `# noqa` / другим обходом). Зафиксировать
  правило в §5.1 и в комментарии к `ParseWarning`/`ParseError` в pipeline.py.

### (high) §5.1 vs pipeline.py:190–196 — `ParseError` не наследует `ParseWarning`

`architecture.md` §5.1 строка 379:
```
@dataclass(frozen=True)
class ParseError(ParseWarning):
    pass
```

`pipeline.py` строка 190–196 объявляет `ParseError` как **отдельный**
dataclass с теми же полями, без наследования:
```
@dataclass(frozen=True)
class ParseError:
    code: str
    message: str
    ...
```

Frozen-dataclass в Python с наследованием другого frozen-dataclass
работает, и оба варианта компилируются. Но:
- §13 опирается на различение «error vs warning» (строка 723–725):
  «`ParseError` ≠ `ParseWarning`. Error означает, что данные не
  получены». Если `ParseError(ParseWarning)` — то error **есть** warning,
  что противоречит §13. То есть документ §5.1 сам себе противоречит.
- Тестовая логика `isinstance(x, ParseError)` будет вести себя
  по-разному в двух вариантах.

Что добавить:
- В §5.1 либо убрать наследование (`class ParseError:`), либо
  изменить §13 на «ParseError — частный случай ParseWarning с более
  жёсткой семантикой».
- pipeline.py уже даёт правильную (несвязанную) форму; синхронизировать
  arch.md под неё.

### (med) `parsed_item.schema.json` строки 45–69 — `price`/`volume`/`stock` пропускают отрицательные числа и Decimal с запятой

Текущая декларация:
```json
"price":  { "type": ["string","number","null"], "pattern": "^\\d+(\\.\\d+)?$" }
"volume": { "type": ["string","number","null"], "pattern": "^\\d+(\\.\\d+)?$" }
"stock":  { "type": ["string","number","null"], "pattern": "^\\d+(\\.\\d+)?$" }
```

Проверено эмпирически:
- `"price": -10` (число) проходит без ошибки (regex `pattern` в JSON
  Schema **не применяется** к нестроковым типам — это явное поведение
  draft-07).
- `"price": "-10"` (строка) — корректно отклоняется regex'ом.
- `"price": "12,50"` (строка с запятой, типичная русская локаль) —
  отклоняется regex'ом, хотя §3 (стр. 105) пишет «Decimal, сериализуется
  как строка». Не указано, что разделитель — точка.

`architecture.md` §3 строка 105–107: `price: Decimal? (≥ 0)`,
`volume: Decimal? (литры)`, но schema не реализует ни `≥ 0`, ни
канонизацию десятичного разделителя.

Что добавить в схему:
- Добавить `"minimum": 0` для каждого из `price`, `volume`, `stock`
  (применится к числам).
- Зафиксировать в §3 / в schema, что Decimal-строки используют точку
  (нормализация делается в Normalizer и приходит в DTO уже в формате
  `^\d+(\.\d+)?$`).
- Альтернативно: оставить `type` строго `["string","null"]` и
  применять только pattern. Тогда минимум закрывается regex'ом
  (`^\d+`).

### (med) §6.3 строки 479–489 — формула SupplierTypeDetector не нормализована

В §6.3 веса прибавляются:
```
+0.5 distributor
+0.4 brewery-only
+0.2 (file-name hint)
+0.3 distributor (multi-sheet)
```

Сумма для distributor может достигнуть 1.0+ (0.5 + 0.2 + 0.3 = 1.0
без brewery-only). Все остальные секции (§6.1, §6.2) явно ограничивают
score диапазоном [0, 1] через нормализацию. §6.3 — нет. Это не сломает
голосование (порог одного источника), но ломает однородность.

Что добавить:
- Привести формулу к виду `clip(sum, 0, 1)` или к нормализации через
  softmax / делению на сумму весов.
- Либо явно отметить, что score — относительный (не вероятность), и
  сравнивается только с другим candidate-ом того же детектора.

### (med) §3 + schema — `format_type` обязательный в schema или нет?

`architecture.md` §3 строка 108: `format_type: enum (см. ниже)`.
Schema (строки 8–14) `required` не включает `format_type`. Pipeline.py
строка 213: `format_type: FormatType = FormatType.UNKNOWN` (default).

Поведение consistent (default есть, поле всегда сериализуется),
но в JSON это означает, что внешний потребитель может прислать
`ParsedItem` без `format_type` — и схема пропустит. Если это
осознанное решение (внешним потребителям необязательно
передавать) — стоит явно отметить в §3. Иначе — добавить в `required`.

### (low) §4.1 vs §14.1 — разный набор стрелок в pipeline-диаграммах

§4.1 (строки 138–161) включает дугу `D[MetaExtractor] -->|FileMeta| Z`
и явные dotted-линии `*.events.-> T`. §14.1 (строки 743–757) —
упрощённая версия без telemetry. Это допустимая редакция (главная
схема + краткая), но в §14 не подписано «упрощённая версия §4.1».
Минорное несоответствие, не блокирующее.

Что добавить: подпись «§14.1 — компактная версия §4.1, без
telemetry» или удалить §14.1, оставив только §14.2 sequence + §14.3
classes (так минимум 2 диаграммы acceptance всё ещё выполняется через
§4.1 + §14.2).

### (low) §11 — нет явной привязки события `column_mapped` к источнику кандидата

В матрице (строки 629–644) для `column_mapped` указано
`sheet, field, source_col, source, confidence`. Это нормально. Но в
§9 ParseRun (строки 571–578) хранится `result: JSONB` — сериализованный
`ParseResult`. В `ParseResult` нет поля `ColumnPlan`, поэтому источник
кандидата (`user / header_exact / ...`) теряется на персистенции. Для
post-mortem при флапающих маппингах этого мало.

Что добавить:
- В §3 в `ParsedItem.field_confidences` рассмотреть `dict[str,
  Candidate]` (вместо `float`), чтобы хранить и `source` тоже. Или
  добавить отдельное поле `field_sources: dict[str, str]`.
- Либо явно фиксировать, что `ColumnPlan` сохраняется отдельно в
  `ParseRun.result.column_plan`.

### (low) §10.2 строка 597 — спорная ширина «top-200 колонок Excel хватает для всех известных прайсов»

Утверждение «top-200 колонок Excel хватает для всех известных
прайсов» — без ссылки на статистику корпуса. Текущий парсер режет
до top-20. Поднимать до 200 — оправдано, но обоснование «всех
известных» субъективное. Рекомендация: связать с harness-стадией
(open question) и калибровать вместе с порогами confidence.

### (low) §10.1 строки 588–593 — SLO без описания как валидировать

Таблица SLO (P95 ≤ 2 c для ≤ 5 МБ / 5 листов / 5k строк) — есть, но
способ валидации не описан. §11 даёт метрику
`parser_duration_seconds{stage}`, но как именно делать gating
(load-test vs регрессионный harness vs production-метрика) — не
сказано.

Что добавить: пункт в §10.1 «SLO валидируется регрессионным harness'ом
(см. follow-up worker) на корпусе из ≥ 30 файлов из production».

### (low) §9 строка 580 — опечатка «Petr-loop» вместо «Feedback-loop»

`architecture.md` строка 580: «Petr-loop: правка в
`SupplierColumnMapping` → ...». Видимо, имелось в виду «Feedback-loop»
или «Auto-loop». Опечатка.

### (low) §15 строка 850 — формула индексации после multi-row header

Митигация: «`HeaderCandidate.rows: tuple[int, ...]` + последняя
строка хедера = старт data». В §6.1 (строка 454) граница поиска:
«до первой строки, где доля числовых ≥ 0.5». Эти два правила
независимы и могут конфликтовать (если последняя header-строка
содержит ≥ 50% числовых — а такое бывает в multi-row, где вторая
строка содержит подзаголовки типа `0.33L | 0.5L | 1L`). Стоит явно
описать порядок: сначала найти multi-row кандидат, потом старт data
= max(rows)+1, **и игнорировать** правило «50% числовых» в пределах
multi-row кандидата.

## 3. Контракты модулей (§5)

- DTO формальные, frozen, с `Sequence`/`Mapping` (immutable hint) — OK.
- Таблица «что значит провал на каждой стадии» (стр. 393–408) —
  соответствует pipeline.py (`FileLoadError`, `SheetClassifierError`,
  `ColumnMapperError` — задефинированы строки 495–508).
- Глобальное правило «пустого результата без errors быть не может»
  (строка 407) — корректно и согласуется с §13.
- Замечание (med): pipeline.py не определяет `LoaderError` как класс,
  хотя §5.2 строка 397 на него ссылается. В pipeline.py есть
  `FileLoadError(PipelineStageError)` (строка 499) — это и есть
  Loader'овская ошибка. Несовпадение имён в тексте и в коде. Привести
  к одному (например, в §5.2 переименовать в `FileLoadError`).
- Замечание (low): `RowExtractorWarning("no_data_rows")` в §13 (строка
  733) не определён ни в pipeline.py, ни в §5.1. Видимо, это просто
  `ParseWarning(code="no_data_rows")`, но названо как класс. Уточнить.

## 4. Confidence & voting (§6)

- Формула header_confidence (стр. 444–450) — нормализована (сумма
  весов = 1.0), корректна.
- Источники и веса (стр. 421–430) — задокументированы, defaults в
  pipeline.py:251–258 есть.
- Tie-break (стр. 474–477) — три уровня правил, нормально.
- Порог `θ_field = 0.45`, `θ_optional = 0.30` (стр. 438–440) — есть,
  open question (handoff worker'а) — калибровка на harness'е.
- UI-fallback для ambiguous (стр. 440) — описан, но конкретный
  worker для UI вынесен в follow-ups (handoff). Принимаемо как
  open question.

Замечание (low): не описан случай, когда **никакой** кандидат
(включая position-fallback) не закрывает поле. По §5.2 (стр. 401)
для `mandatory_fields_missing` лист пропускается, но для optional
поля? Видимо `field_confidences[f] = 0`, поле = `None`. Стоит явно
прописать.

## 5. Backward compatibility (§12)

- Внешний `parse(...)` сохранён посимвольно (стр. 661–670). OK.
- Feature flag `EXCEL_PARSER_PIPELINE_V2` со значениями
  `off / shadow / on` — описан корректно (стр. 679–684).
- Путь возврата (rollback) — формально не выделен, но тривиально
  получается из `flag=off`. **Замечание (low)**: добавить явный
  раздел «Rollback» (одна фраза: «при критическом регрессе
  выставить флаг в `off` глобально, V1-фасад транспаррентно
  откатывается на legacy»).
- DDD-рефакторинг как основа V2 (стр. 690–695) — описан, риск
  расходимости поднят в §15 (строка 860).

## 6. Расширяемость (§7, §8)

- Plug-in points: новый поставщик / поле / детектор / Loader-формат
  (стр. 528–541) — описаны, decorator-стиль (`@register_*`).
- Реестры (§7) — YAML + БД, разделение ответственности «разработчик
  через PR» vs «админ через UI» — корректное.
- Замечание (low): §7 строка 506 — «hot-reload по mtime в DEBUG»,
  но не описан inotify / poll-интервал. Для production-DEBUG
  допустимо. OK.
- Замечание (low): нет описания как разрешается коллизия между
  `field_lexicon.yaml` и `SupplierColumnMapping` (БД). По §6 user
  имеет вес 1.0, header_exact — 0.9, поэтому БД-маппинг побеждает
  лексикон. Стоит явно прописать в §7 или §9.

## 7. Производительность (§10)

- SLO измеримы (P95, MB, листы, строки) — стр. 588–593.
- Streaming-mode для > 20 МБ — описан.
- Параллелизм — feature flag.
- Сравнительная таблица «до / после» — стр. 614–622, наглядная.
- Замечание (med, см. выше): план как валидировать SLO не описан.

## 8. Mermaid-диаграммы

- §4.1 pipeline (стр. 138–161) — ✓
- §12.1 migration roadmap (стр. 699–706) — ✓
- §14.1 pipeline (упрощённый) (стр. 743–757) — ✓
- §14.2 sequence (стр. 761–805) — ✓
- §14.3 class diagram (стр. 809–844) — ✓

Итого 5 диаграмм (требование ≥ 2 выполнено). Порядок стадий
консистентен между §4.1, §14.1, §14.2 и `pipeline.py PipelineStages`
(строки 468–479).

Замечание (low): в §14.2 sequence-диаграмме после loop'а сразу идёт
`P->>DD: dedupe(items)` — то есть Validator не упомянут перед
Deduplicator. На самом деле Validator вызывается **внутри** loop'а
(`P->>V: validate(items)`), и это согласуется с §4.1, где Validator
до Deduplicator. Но визуально читается, что Deduplicator после
loop'а получает `items` (валидные), а `invalid_items` теряются.
Стоит добавить в sequence явный «invalid_items аккумулируются
снаружи loop'а» комментарий.

## 9. Сравнение с текущим god-class

§10.3 (стр. 614–622) — таблица «Сейчас / Новая архитектура»:
- top-N лимиты (10/20) → конфигурируемые (30/200) ✓
- Multi-row headers (нет → есть) ✓
- Streaming (нет → есть) ✓
- Параллельные листы (нет → есть, под флаг) ✓

Концептуальная сложность которая ушла:
- 4 fallback-стратегии чтения листа в одном методе → единый Loader
  с adapter-pattern по mime/ext (§4 Loader, §8 plug-in points).
- Жёсткие if-цепочки в `_find_header_row` → confidence-формула в
  §6.1.
- Хардкоженные имена брендов в `supplier_profiles.py` →
  `supplier_hints.yaml` (§6.3 и §7).
- Тихий пустой результат → `ParseResult.status` (§13).

Концептуальная сложность которая осталась:
- Эвристическая природа scoring'а (формулы content/header воспринимают
  «магические числа» — 0.4 / 0.3 / 0.2 / 0.1 в §6.1; 0.85 / 0.7 в
  §6.2). Это **обосновано** в open question (калибровка на harness'е),
  но в документе нужно явно отметить, что defaults — placeholder.
- Постпроверка «stock похож на format_type» из текущего парсера
  переехала в §6.2 как content-based feature (correct), но
  правило-замена «если совпал с price — выбросить» теперь живёт в
  §13 строка 736–737. Описано, но без формулы. Стоит добавить
  conditions в §6.2.

## 10. JSON Schema (формальные проверки)

```bash
python3 -c "import json,jsonschema; jsonschema.Draft7Validator.check_schema(json.load(open('docs/design/excel-parser/contracts/parsed_item.schema.json'))); print('OK')"
# OK
```

Эмпирические тесты (sanity samples):
- minimal valid item — pass ✓
- extra field — corrected reject ✓ (`additionalProperties: false`)
- unknown field_confidences key — reject ✓
- negative numeric `price` — **pass** (gap, см. (med) выше)
- negative string `price` — reject (regex) ✓
- string `"12,50"` — reject (regex) (см. (med) выше)

## 11. pipeline.py (синтаксис)

```bash
python3 -c 'import ast; ast.parse(open("docs/design/excel-parser/contracts/pipeline.py").read())'
# (no output — clean parse)
```

✓ Файл синтаксически валиден.

Замечание (low): строка 153 — `Candidate(Generic[T])`. Использован
старый стиль через `TypeVar` (строка 149). Это нормально для
совместимости с Python 3.10+. PEP 695 (`class Candidate[T]:`) можно
рассмотреть в фазе imp, но не блокер.

## 12. Открытые вопросы из handoff worker'а

| Вопрос                                          | Решаемо локально | Эскалация       |
|-------------------------------------------------|------------------|------------------|
| Калибровка весов источников и порогов confidence | нет              | следующий worker (regression harness) |
| Корпус реальных прайс-файлов в `tests/fixtures/` | нет              | следующий worker (harness)            |
| YAML-реестры (вынос lexicon'ов из кода)         | нет              | следующий worker (registries)         |
| БД-схема feedback loop                           | нет              | worker (миграции)                     |
| UI ambiguous-mapping                             | нет              | worker (frontend / admin UI)          |

Все open questions имеют адресатов в follow-ups worker'а — корректно
эскалированы, не блокируют design-фазу.

## 13. Резюмирующая таблица замечаний

| Severity | Раздел                | Краткое описание                                                |
|----------|-----------------------|------------------------------------------------------------------|
| high     | §4 + §3 (ось 3)       | Нет стадии для brewery-as-prefix внутри `beer_name`              |
| high     | §5.1 / pipeline.py / schema | `ParseWarning.field` vs `field_name` рассогласованы          |
| high     | §5.1 vs pipeline.py   | `ParseError` объявлен как наследник в §5.1, как отдельный — в pipeline.py; противоречит §13 |
| med      | schema price/volume/stock | Нет `minimum: 0`; pattern не применяется к числам            |
| med      | §6.3                  | Формула SupplierTypeDetector не нормализована                    |
| med      | §3 + schema           | `format_type` обязательный или нет — решить и зафиксировать      |
| med      | §10.1                 | План валидации SLO не описан                                     |
| med      | §5.2 vs pipeline.py   | `LoaderError` vs `FileLoadError`, `RowExtractorWarning` без класса |
| low      | §4.1 vs §14.1         | Две pipeline-диаграммы без подписи о редакции                    |
| low      | §11 + §3 + §9         | Источник кандидата теряется при персистенции                     |
| low      | §10.2 (top-200 cols)  | Утверждение без ссылки на корпус                                 |
| low      | §9 строка 580         | Опечатка «Petr-loop» → «Feedback-loop»                           |
| low      | §15 строка 850        | Multi-row + «50% числовых» — конфликт правил, нет приоритета     |
| low      | §6                    | Нет описания «никакой кандидат не закрыл optional поле»          |
| low      | §12                   | Нет явного раздела «Rollback»                                    |
| low      | §7 / §9               | Не описано разрешение коллизии lexicon vs БД-маппинг             |
| low      | §14.2 sequence        | Validator vs Deduplicator: где invalid_items                     |

## 14. Acceptance check (verifier-specific)

- [x] `docs/design/excel-parser/_review/architecture-review.md` создан
- [x] В первой строке стоит `Verdict: pass-with-comments`
- [x] Все 14 осей классифицированы (covered/partial/missing): 13 covered, 1 partial, 0 missing
- [x] Каждое замечание ссылается на конкретный раздел / строку (с указанием § и строк документа)

## 15. Финальный вердикт

**`pass-with-comments`**. Архитектурный документ — содержательный,
охватывает заявленный объём, не имеет пропусков на уровне формальных
acceptance worker'а. Найденные замечания — design-инконсистенции
(`field_name` vs `field`, `ParseError` наследование, brewery-prefix-в-имени)
и недокрытие в schema (минимумы для денежных полей). Они должны быть
устранены **до** старта worker'а skeleton-implementation, потому что
именно skeleton-стадия закрепит контракты в коде. Регрессионный
harness и калибровка порогов — корректно вынесены в follow-up
worker'ы.

---

## Second-pass verifier review (independent run)

Verdict: pass-with-comments

Запущен второй независимый проход верификации поверх той же ветки `orch/excel-parser-resilient-design/design-architecture`. Совпадает с первой проходкой по итоговому вердикту (`pass-with-comments`). Ниже — дополнения и пересечения с первой проходкой; ничего из первого ревью не отменяется.

Verdict: pass-with-comments

# Critical review of `docs/design/excel-parser/architecture.md`

Документ ревьюится в составе artefact'ов worker'а `design-architecture` на ветке `orch/excel-parser-resilient-design/design-architecture`:

- `docs/design/excel-parser/architecture.md` — 860 строк, 15 разделов, 5 mermaid-диаграмм.
- `docs/design/excel-parser/contracts/parsed_item.schema.json` — 152 строки, JSON Schema draft-07.
- `docs/design/excel-parser/contracts/pipeline.py` — 562 строки, Protocol/dataclass DTO.

## 1. Mechanical acceptance

| Acceptance criterion (target task)                                                  | Result |
|-------------------------------------------------------------------------------------|--------|
| `architecture.md` создан и закоммичен в ветке worker'а                              | met    |
| Все 15 разделов присутствуют (TL;DR / Требования / Контракт / Pipeline / Контракты / Confidence / Реестры / Расширяемость / Feedback / Performance / Observability / BC / Failure / Diagrams / Risks) | met    |
| Минимум 2 mermaid-диаграммы внутри документа                                        | met (5: §4.1 flow, §12.1 migration, §14.1 pipeline, §14.2 sequence, §14.3 class) |
| `parsed_item.schema.json` валиден как JSON Schema draft-07                          | met (`jsonschema.Draft7Validator.check_schema(...)` → OK; positive sample валидируется, 4 negative sample корректно отклонены) |
| `pipeline.py` парсится python                                                       | met (`python -c 'import ast; ast.parse(...)'` → OK; модуль также успешно импортируется через `importlib.util` после регистрации в `sys.modules`) |
| Все 14 осей изменчивости явно адресованы                                            | met (см. §3 ниже)                                       |

## 2. Покрытие 14 осей изменчивости

| #  | Ось                                                              | Status            | Где / комментарий                                                                                                          |
|----|------------------------------------------------------------------|-------------------|----------------------------------------------------------------------------------------------------------------------------|
| 1  | Положение строки заголовков 1..N, multi-row                      | covered           | §4 `RegionDetector` (стр. 201–208) + `HeaderDetector` (стр. 210–217), §6.1 (стр. 444–460) явно описывает multi-row.         |
| 2  | Номенклатура колонок, синонимы, опечатки, рус/англ, регистр      | covered           | §4 `ColumnMapper` (стр. 218–240) — exact/stem/fuzzy/embedding; §6.2 (стр. 461–478); §7 (стр. 510–523) — `field_lexicon.yaml`. |
| 3  | Distributor vs Brewery, brewery в префиксе/имени файла            | covered           | §4 `RegionDetector`+`SheetClassifier`; §6.3 (стр. 479–490) `SupplierTypeDetector` confidence; supplier_hints.yaml.          |
| 4  | Множество листов, в т.ч. служебные                               | covered           | §4 `SheetClassifier` (стр. 182–192) — kind ∈ data/meta/trash.                                                                |
| 5  | Объединённые ячейки и group-headers                              | covered           | §4 Loader unmerge (стр. 178), `RegionDetector` (стр. 201–208) делает group-header контекстом, `RowExtractor` (стр. 242–255) классифицирует kind=group_header. |
| 6  | Цена и остаток в визуально похожих колонках                      | partially covered | §6.2 (стр. 470–472): "content (stock): numeric_ratio ∧ mean(values) ≤ 10000 ∧ diff_from_price_col". Концепция верная, но формула выражена через `∧` без числовой агрегации — см. замечание M-1. |
| 7  | Format в виде иконок/коротких слов (банка, can, ж/б, кега…)      | covered           | §4 `Normalizer` → `FormatNormalizer` (стр. 264–266); §7 `format_lexicon.yaml`.                                              |
| 8  | Объём `0,33 / 0.33 / 330 ml / 1/2 л`                             | covered           | §4 `VolumeNormalizer` (стр. 263); §7 `volume_patterns.yaml`; в `pipeline.py` есть `VolumePattern(regex, multiplier_to_litres)`. |
| 9  | Валюта в отдельной колонке vs внутри строки цены ('250 руб')     | covered           | §4 `CurrencyNormalizer` (стр. 264) с примерами `250 руб / 250₽ / RUB 250 / $5`; §7 `currency_lexicon.yaml`.                   |
| 10 | Сломанный xlsx (autoFilter, sharedStrings, защищённый лист)      | covered           | §4 Loader sanitize (стр. 170–174) — переносит логику текущего `_create_temp_file_without_filters`, плюс `sharedStrings.xml` и снятие защиты на чтение. Правда, на стр. 854 риски говорят "защищённые листы → `LoaderError('sheet_protected')`, без попыток обхода", что противоречит "снять защиту на чтение" в §4 — см. M-7. |
| 11 | Пустые строки, разделители, промежуточные тоталы                 | covered           | §4 `RowExtractor` (стр. 242–255) — kind ∈ data/group_header/total/divider/noise.                                            |
| 12 | Google Sheets как CSV                                            | covered           | §4 Loader (стр. 175) — `csv.Sniffer` для разделителя/кодировки.                                                              |
| 13 | Мета-данные в имени файла или верхних строках                    | covered           | §4 `MetaExtractor` (стр. 194–199) — отдельная под-стадия, regex-реестр `meta_patterns.yaml`. NB: TL;DR (стр. 15) MetaExtractor пропускает — см. M-2. |
| 14 | Пользовательский `supplier_column_mapping` извне                  | covered           | §4 `ColumnMapper` (стр. 220–227) — source `user`, weight 1.0; §9 (стр. 543–578) feedback-loop. Однако нет описания, что делать, если user mapping ссылается на несуществующую колонку — см. M-5. |

Итого **14/14 covered**, из них одна — partial (`6` — цена vs остаток), остальные — со ссылками на конкретные разделы и строки.

## 3. Замечания по существу

Уровни: **B**locker (требует правки до merge) / **M**ajor (надо адресовать в этой или следующей итерации) / **m**inor (косметика).

### B-блокеров не найдено.

### M — major (надо адресовать)

- **M-1. §6.2 (стр. 470–472), формула content-confidence для `stock` плохо формализована.**
  Запись `numeric_ratio ∧ mean(values) ≤ 10000 ∧ diff_from_price_col` использует логическое `∧` для смешения булевых предикатов и числовых параметров, не давая числового score'а в `[0, 1]`. Это критическое место для оси 6 (price vs stock) — следующему worker'у с harness'ом не на что калиброваться. Нужно дать явную формулу (например, `score = numeric_ratio * range_fit_stock * (1 - corr_with_price_col)`), указать `range_fit` для стока, и описать как ведёт себя метрика на пограничных кейсах (одна и та же колонка содержит и цены, и остатки).

- **M-2. TL;DR (§1, стр. 14–17) рассинхрон с реальной цепочкой.**
  В TL;DR `Loader → SheetClassifier → RegionDetector → HeaderDetector → ColumnMapper → RowExtractor → Normalizer → Validator → Deduplicator → TelemetrySink` — `MetaExtractor` пропущен, хотя является отдельной стадией в §4.1, §4.2, §14.1, §14.2, §14.3 и обсуждается в осях 3 и 13. Читатель TL;DR делает неверную модель.

- **M-3. §12 Backward compatibility (стр. 657–705) не описывает rollback из V2 в V0 при production-инциденте.**
  Документ описывает `off → shadow → on → drop`, но не явно: что делать, если V2 на проде упал/выдал регрессию? Понятно, что флаг можно вернуть в `off`, но §13 (стр. 712–737) одновременно говорит "Тихий пустой результат запрещён" — а §12 фасад "Логирует warnings/errors, но не возвращает их (для совместимости)" (стр. 677). На границе фасада строгий `ParseResult.status` теряется. Нужно либо явно обозначить эту "двойную мораль" как сознательное компромиссное решение для совместимости, либо ввести второй внешний API (`parse_strict()` / `parse_v2()`), который возвращает полный `ParseResult` без потери информации. Иначе цель "явный failure вместо тишины" недостижима для существующих вызывающих.

- **M-4. Несоответствие контрактов между `architecture.md` §5.1 (стр. 378–380) и `pipeline.py` (стр. 181–196):**
  - markdown: `class ParseError(ParseWarning): pass` (наследование);
  - pipeline.py: `ParseError` — отдельный dataclass, без наследования;
  - markdown: поле `field` (стр. 376);
  - pipeline.py: поле `field_name` (потому что `field` коллизит с `dataclasses.field`, стр. 187, 196);
  - JSON Schema (`parsed_item.schema.json`, строка 146) использует поле `field` — соответствует markdown, но не pipeline.py.

  Нужно унифицировать: либо переименовать поле в `field` через `dataclasses.field` workaround (`from dataclasses import field as _field`), либо переименовать в JSON Schema на `field_name`. Иначе при попытке скинуть `ParsedItem.warnings → JSON` через `dataclasses.asdict` сериализатор положит ключ `field_name`, который не валидируется текущей schema.

- **M-5. §4 ColumnMapper и §6 — не описано поведение при конфликте user mapping с реальностью.**
  Если в `SupplierColumnMapping.mapping` админ указал имя колонки, которой нет в текущем файле (например, поставщик переименовал колонку), что произойдёт? Пишется ли warning, есть ли fallback на header-based, или маппинг тихо игнорируется? §5.2 (стр. 401) описывает случай "не закрыты обязательные поля" → error, но конкретно "user mapping не сматчился" — отдельно не разобран.

- **M-6. §7 hot-reload только в DEBUG (стр. 506–508).**
  Это разумный default, но в проде нужен явный путь для админа поменять YAML-реестр без релиза. Иначе обещание §2.4 ("устойчивость = добавление синонимики без редеплоя") не выполняется. Минимум — описать SIGHUP / signal-handler / админ-команду `manage.py reload_lexicons`.

- **M-7. §4 Loader (стр. 174) vs §15 Risks (стр. 854).**
  В §4 написано "снять защиту на чтение" (для защищённых xlsx), а в рисках — "Loader возвращает `LoaderError('sheet_protected')`, без попыток обхода". Это противоположные стратегии. Решить и зафиксировать одну.

- **M-8. §10 Performance (§10.1 SLO) — нет явного плана, как валидировать SLO.**
  Сказано "regression harness ≥ 95% PASS на корпусе, P95 ≤ SLO" (стр. 708–709), но не указан инструмент (`pytest-benchmark` / собственный harness / time-замер в CI), на каком объёме корпуса (сколько файлов, какого размера), и как фиксировать baseline при изменениях. Performance-валидация остаётся на следующего worker'а — это ОК, но текущий документ должен явно сказать "harness + perf-CI определяются harness-worker'ом, веса 0.45/0.30 — placeholder". Сейчас формулировка слишком расплывчата.

- **M-9. §6 voting (стр. 432–440) — argmax по score, без агрегации множественных голосов.**
  Если три источника независимо проголосовали за колонку X (header_exact, content, profile) — победа всё равно достанется максимальному единичному score. Согласие нескольких источников не повышает уверенность. Это спорное решение для устойчивости; в текущем god-class profile/content fallback'и тоже работают по принципу "первое подходящее". Возможно, разумно — сумма или average ограниченных весов. Если решение принимается сознательно, нужно его обосновать (`sum`/`mean` приведёт к шумовым голосам position-fallback'а перевешивающим один сильный header_exact). В текущем виде — open question.

### m — minor (косметика и форма)

- **m-1.** §9 стр. 580 — "Petr-loop" — опечатка, должно быть "Feedback-loop" (или "обратная связь").
- **m-2.** §7 стр. 508 — "индекс по `supplier_id` + `file_hash_prefix`" — `file_hash_prefix` нигде не определён выше; нужно сослаться или определить (например, "первые 8 hex-символов sha256 содержимого файла").
- **m-3.** §10.2 стр. 596–612 vs §4 Loader стр. 165–168 — режим streaming "openpyxl read_only" для файлов > 20 МБ конфликтует с описанием Loader как "однократное чтение листа в numpy-массив". Стоит явно сказать, что в streaming-режиме теряется part of merge-handling и каких-то стадий (RegionDetector ?) — иначе SLO для крупных файлов под вопросом.
- **m-4.** §4.1 mermaid (стр. 138–161) — `RegionDetector → HeaderDetector → ColumnMapper`, но `ColumnMapper` в §14.3 принимает `region` как аргумент (`headers, region, user, profile`). На диаграмме это сокрытое ребро. Не блокер, но иногда вводит в заблуждение.
- **m-5.** §3 (стр. 117) — `format_type ∈ {"bottle", "can", "keg", "other", "unknown"}`. JSON Schema (стр. 64) и pipeline.py (стр. 213) согласованы. Но в табличке §3 у `format_type` нет `?`-маркера, а в JSON Schema поле не в `required`. Нужно либо явно сказать "default = 'unknown'", либо включить в `required`.
- **m-6.** §5.1 markdown `ParsedItem` тело подменено на `# см. §3` (стр. 367–368). Это OK как cross-reference, но хочется хоть один полный псевдокод-блок где-то близко (полный есть в pipeline.py — этого достаточно, просто заметка).
- **m-7.** `pipeline.py` `from __future__ import annotations` + `dataclass` + `Generic[T]` корректно проходят `ast.parse` и (с регистрацией в `sys.modules`) загружаются через `importlib`. Стандартный `python pipeline.py` запустить нельзя из-за известного quirk dataclasses при `__module__ is None` — это не баг файла, но документально хорошо бы пометить, что файл — псевдокод, не runnable script.
- **m-8.** §11 Prometheus-метрики (стр. 647–652): `parser_column_confidence{field}` — 11 значений field — ОК; `parser_rows_dropped_total{reason}` — кардинальность не ограничена. Нужно зафиксировать, что `reason` — это enum (фиксированный набор), а не свободный текст из warnings.
- **m-9.** §4.2 Normalizer для ABV (стр. 266) — "если число < 1, считаем долей". Это эвристика, которая ломается на 0.5%-non-alc beers. Достоинство — что есть `field_confidences[abv]`, можно понизить уверенность; но эвристику стоит зафиксировать в §15 Risks.
- **m-10.** §8 (стр. 525–541) — добавление нового поля требует правок: Field enum + ParsedItem dataclass + JSON Schema + lexicon. Это означает, что "новое поле" — это releasable change, не registry-only. Не блокер, но "расширяемость без правок ядра" (§2.4) формально нарушается для добавления нового поля. Стоит уточнить, что речь о новых типах поставщиков и детекторах, а не о новых полях в ParsedItem.
- **m-11.** §9 `ParsingFeedback.expected: text, actual: text` (стр. 568–569) — лучше JSONB, потому что админ может правит mapping не одной строкой, а dict'ом.

## 4. Контракты модулей

Каждый модуль в §5.1 имеет вход/выход, в §5.2 — поведение при провале. Ошибки прокидываются наверх через `ParseError`/`ParseWarning` (DTO) и `PipelineStageError` (исключения) — см. `pipeline.py` стр. 495–508. Проверка "магических полей" пройдена: всё типизировано через dataclass-frozen и Protocol с `runtime_checkable`. Замечание M-4 описывает рассогласование между `architecture.md` §5.1 и `pipeline.py` по полю `field`/`field_name` и наследованию `ParseError`.

## 5. Confidence & voting

§6 фиксирует:
- веса источников (стр. 421–430), defaults в `pipeline.py` `PipelineConfig` (стр. 250–259);
- формулу `score(c) = c.confidence * weight(c.source)` (стр. 432–436);
- порог `θ_field = 0.45` для обязательных, `θ_optional = 0.30` (стр. 438–440);
- tie-break по 3 правилам (стр. 474–477);
- ambiguous-путь — UI-fallback (стр. 440), таблица в БД для feedback (§9).

Замечания: **M-1** (формула для stock), **M-9** (нет агрегации множественных голосов).

## 6. Backward compatibility

§12 описывает фасад, feature flag `EXCEL_PARSER_PIPELINE_V2` с тремя значениями, 5-этапный rollout. Замечания: **M-3** (rollback и потеря строгого ParseResult на границе фасада).

## 7. Расширяемость

§7+§8 — реестры и plug-in points. Реестры (YAML + БД) зафиксированы в таблице (стр. 495–504). Feedback-loop §9 не противоречит реестрам: правки админа живут в БД, после `hits_count ≥ N` идёт PR в YAML — единый source of truth сохраняется. Замечание **m-10** (новое поле всё-таки требует правок ядра) не критично.

## 8. Производительность

§10 SLO измеримы (P95 ≤ 2с, ≤ 8с, streaming-mode для > 20 МБ). План валидации — см. **M-8**.

## 9. Mermaid соответствие тексту

5 диаграмм в документе:
- §4.1 (стр. 138–161): pipeline flow с telemetry — соответствует §4.2.
- §12.1 (стр. 699–706): migration roadmap V0→V5.
- §14.1 (стр. 743–757): pipeline (повтор).
- §14.2 (стр. 761–805): sequence для одного файла. Соответствует §4.2; loop per data sheet корректен.
- §14.3 (стр. 809–844): class-диаграмма Pipeline + 11 Protocol-стадий. Соответствует `pipeline.py`.

Рассинхрон только один: §1 TL;DR не содержит `MetaExtractor`, хотя все диаграммы его показывают (см. **M-2**).

## 10. Сравнение с текущим god-class

§10.3 (стр. 614–622) даёт явную сравнительную таблицу. §2.1 описывает текущие проблемы. §12 описывает миграцию через DDD-инфраструктуру, которая уже частично существует (`infrastructure/parsers/excel/`).

Концептуальная сложность, которая **уходит**:
- 4 fallback-стратегии чтения листа → одна стратегия Loader с явным sanitize.
- Хардкоженные top-N лимиты → конфигурируемые с векторизацией.
- Тихая постпроверка `stock vs format_type` → явный content-based кандидат с warning.
- Hardcoded имена ('paradox', 'alisperi', 'two peaks') → YAML.
- Тихий пустой результат → `ParseResult.status` (с оговоркой M-3).

Концептуальная сложность, которая **остаётся**:
- multi-row headers — новое требование, риск признан явно (стр. 850).
- ambiguous columns (price vs stock) — формализовано, но формула требует калибровки (M-1).
- profile-detection — переехало с эвристики на confidence-формулу (§6.3), но факт несколько профилей и нескольких источников остаётся.
- xls (legacy) — `xlrd==1.2.0` или `libreoffice`-fallback (§4 Loader, стр. 173–174) — наследие.

## 11. Открытые вопросы из handoff'а worker'а

Worker отметил 5 follow-up'ов: regression harness, skeleton-имплементация, YAML-реестры, БД-схема feedback, UI ambiguous. Все они решаются параллельными worker'ами на следующих итерациях оркестрации; эскалации к планнеру не требуют. Конкретные числовые пороги (0.45 / 0.30 / веса источников) — placeholder, калибровка ответственность harness-worker'а; это явно зафиксировано в §6 и в handoff'е, проблем нет.

Не задано worker'ом, но требует решения планнера (через next worker):

- **OQ-1.** Как себя ведёт фасад `parse(...) → list[dict]` при `ParseResult.status = "failed"`? Возвращать пустой список (M-3) или поднимать exception? От ответа зависит API-контракт всех существующих вызывающих.
- **OQ-2.** Single user mapping (§4 ColumnMapper источник `user`) — это per-file, per-supplier или per-tenant? Документ говорит про `scope = exact_file | supplier | global` (§9), но как разрешается конфликт между user-маппингом supplier-уровня и user-маппингом file-уровня в одном `ColumnMapper.map(...)` вызове, не описано.
- **OQ-3.** Voting strategy (M-9) — argmax vs sum/mean. Решить до начала harness-калибровки.

## 12. Итоговый вердикт

`pass-with-comments`.

Архитектура достаточна для запуска harness-worker'а и skeleton-worker'а: контракты стабильны, JSON Schema валидируется, DTO согласованы (с поправкой M-4), все 14 осей покрыты, mermaid-диаграммы согласованы (с поправкой M-2). Замечания M-1, M-3, M-4, M-7 — must-fix перед началом V2-имплементации, остальные M-/m- — желательные правки при следующем pass'е по `architecture.md`.
