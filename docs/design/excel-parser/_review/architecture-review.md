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
