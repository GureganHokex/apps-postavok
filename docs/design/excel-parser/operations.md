# Операционный дизайн: evaluation harness и миграция Excel-прайс-парсера

Дополняет `architecture.md` и `contracts/` (pipeline, DTO, confidence, observability): здесь описано **как измерять качество парсера**, **как безопасно вытеснить god-class** `backend/parser_app/parsers/excel_parser.py`, и **что наблюдать в проде**. Изменений в коде приложения в этом документе нет.

**Флаги feature-toggle:** канонический ключ в прод-контуре **`EXCEL_PARSER_PIPELINE_V2`** (`false` по умолчанию). Рабочее имя **`PARSER_V2_ENABLED`** в оркестрационном ТЗ трактуем как **синоним**: при имплементации в `settings` допускается чтение обоих имён или явный алиас, чтобы деплои и текст задач не расходились.

---

## Часть A: Evaluation harness

### A.1 Цель harness

На **каждом коммите** и перед релизом harness должен измерять:

1. **Качество по полям** — precision / recall / F1 для ключевых полей (`brewery`, `beer_name`, `price`, объём/фасовка, валюта, остаток и др. В терминах `ParsedItem` и адаптера к БД).
2. **Дрейф версий** — сравнение отчётов двух сборок на одном корпусе (хеш коммита + версия пайплайна в метаданных отчёта).
3. **Скорость** — wall time полного парсинга файла; при необходимости p50/p95 по корпусу на эталонном runner CI для регрессии против SLO из архитектуры.
4. **Классификация результата** — доли `ok` / `partial` / `failed`, сопоставление с явным `ParseResult.status`; запрет маскировать регрессию «пустым списком».

**Готовность:** воспроизводимый прогон корпуса → JSON/CSV-артефакты + краткая сводка в stdout; одинаково локально и в CI (workflow подключается отдельной задачей, см. A.5).

### A.2 Корпус

1. **Сбор** — **анонимизированные** реальные `.xlsx` из переписки/архива поставщиков: исключить ПДн и чувствительные реквизиты при необходимости маскировать числа цен порядком величин; сохранить структуру объединений, пустых строк, нескольких таблиц на листе; «битый» XML autoFilter — по политике (воссоздавать только если нужно воспроизвести падение Loader’а контролируемо).

2. **Категоризация метаданными** для каждого файла (`corpus.manifest.json`): `supplier_kind` (дистрибьютор / пивоварня / смешанный и т.д.), **`complexity`** (`low` / `medium` / `high` по строке заголовка и фрактальной «грязи» таблицы), **`edge`** (список: «цена рядом с остатком», «валюта в заголовке», «производитель в имени», «сломанный autoFilter», др.).

3. **Хранение** — **приватный** полный корпус в отдельном репо + **Git LFS** или object storage; пути конфиденциальных образцов под `.gitignore` в основном репо или submodule. Публичный минимальный набор: **`tests/fixtures/excel-synthetic/`** (генерация см. A.8; при необходимости префикс `backend/tests/...` согласовать с Django layout). Альтернативный локальный каталог **`tests/fixtures/excel/`** — только записи имён файлов игнорируются в VCS если политика это требует.

4. **Версионирование** — тег набора `corpus-vYYYY.MM.idx` + manifest хэш файла, путь эталона, дата поступления, версия пайплайна **baseline v1**.

### A.3 Golden snapshots

1. **Формат:** рядом с `price.xlsx` лежит **`price.xlsx.expected.json`** (sidecar): упорядоченный массив нормализованных `ParsedItem` или обёртка `{ "parse_result": { "status", "warnings", "items": [...] } }` согласно `contracts/parsed_item.schema.json`.

2. **Версионирование:** правки эталона только через MR; поля `_golden_schema_version`, `_reviewed_by` / ссылка на тикет.

3. **CLI обновления (проект):** **`python manage.py parser_update_golden <path/to/file.xlsx>`** — записывает **кандидат** `.expected.json.pending`, не перетирает существующий `.expected.json` без `--force`; финальное применение в неинтерактивном режиме только с **`--i-understand-this-changes-contract`** и ревью; в основном CI **запрет** генерации эталона (только read-only сравнение).

4. **Два режима истины эталона:** (a) вручную валидирован бизнесом; (b) «snapshot v1» для чистого поведенческого регресса Legacy — смешение в один отчёт метрик допускать только по раздельным меткам.

### A.4 Метрики и формулы

**Нормализация** значений выполняется той же функцией домена **`norm(field, value)`**, что используется в production `Normalizer` (фиксируется в коде harness). Множество сравниваемых полей \(\mathcal{F}\) задаётся manifest.

**Сопоставление строк (matching):** эталонные позиции \(G\), предсказанные \(P\); строим оптимальное (или допустимо жадное при больших N) паросочетание по скорости схожести ключа **пивоварня + название + объём** и допуска по цене; порог ребра \(\tau\) задаёт конфиг harness.

Для каждого поля \(f\) вводим счётчики по сумме по всем парам матчинга \(M\) и «осиротевшим» строкам:

| Символ | Смысл |
|--------|--------|
| \(\mathrm{TP}_f\) | пары из \(M\) с эквивалентным **после нормализации** значением \(f\) |
| \(\mathrm{FN}_f\) | эталонные строки где требовалось значение \(f\), но нет успешной пары или в паре поле ошибочно |
| \(\mathrm{FP}_f\) | предсказанные случаи с ненулевым \(f\) без подтверждения матчингом или с явной ошибкой (для «optional» см. исключение в коде правил домена) |

**Таблица метрик:**

| Метрика уровня | Формула |
|----------------|---------|
| Precision по полю \(f\) | \(\displaystyle P_f = \frac{\mathrm{TP}_f}{\mathrm{TP}_f + \mathrm{FP}_f}\); при \(\mathrm{TP}_f+\mathrm{FP}_f=0\) → `n/a` |
| Recall по полю \(f\) | \(\displaystyle R_f = \frac{\mathrm{TP}_f}{\mathrm{TP}_f + \mathrm{FN}_f}\) |
| F1 по полю \(f\) | \(\displaystyle \mathrm{F1}_f = \frac{2 P_f R_f}{P_f + R_f}\) |
| **Item-level recall** (позиционная покрыта) | \(\displaystyle R_{\mathrm{item}}^{\mathrm{cov}} = \frac{\bigl|\{ g \in G \mid \exists p \in P : (g,p)\in M \}\bigr|}{|G|}\) |
| **Item-level recall** (строго по ключевым полям) | \(\displaystyle R_{\mathrm{item}}^{\mathrm{strict}} = \frac{\bigl|\{ g\in G \mid \exists (g,p)\in M,\ \forall f\in\Phi_{\mathrm{req}}\ \text{совпало} \}\bigr|}{|G|}\), где \(\Phi_{\mathrm{req}}\) включает как минимум `beer_name` и `price` плюс доменные |

**Файл и артефакты:** статус **`ok`** если \(R_{\mathrm{item}}^{\mathrm{strict}}=1\) и нет критических отклонений по порогам; **`partial`** при \(R_{\mathrm{item}}^{\mathrm{cov}} \geq \tau_{\mathrm{partial}}\); иначе **`failed`**; дополнительно **`parse_ms_wall`**. Выход harness: **`artifacts/parser-eval/<run_id>/summary.json`**, **`per-field.csv`**, stdout-сводка; при A/B см. парный **`parser-ab-report.md`**.

### A.5 Регрессионный harness

1. **`pytest`** — `pytest.mark.parametrize("fixture_path", manifest_paths)`; тест золотых пар валидирует список `ParsedItem`/адаптер `List[Dict]` против `.expected.json` в зависимости от режима регрессии.

2. **Конфигурация** — секция **`[tool.pytest.ini_options]`** в `pyproject.toml` **или** `pytest.ini`; маркеры `parser_eval`, `slow`, корневая директория тестового пакета (создаётся при внедрении).

3. **Локальный запуск:** `pytest -m parser_eval -q` с **`PARSER_EVAL_CORPUS_ROOT`** указывающим закрытый корпус; без секретов — только синтетика из `excel-synthetic/`.

4. **CI workflow** `.github/workflows/parser-tests.yml` **не создаётся в этом change-set** — только контракт: checkout, optional `git lfs pull` с секретами, установка окружения, `pytest -m parser_eval`; артефакты `summary.json`; на форках без приватных субмодулей — skip или synthetic-only job.

### A.6 A/B сравнение с v1

1. Прогоны **Legacy** через публичный `ExcelParser.parse(supplier_type, brewery_name, supplier_column_mapping)` и **candidate** (`parsers_v2` / DDD `Pipeline`) при идентичных входных mapping из manifest.
2. Нормализация обоих логов diff к общему слою **`ParsedItem[]`** перед сравнением.
3. **Отчёт** `artifacts/parser-eval/parser-ab-report.md`: \(\Delta \mathrm{F1}_{price}\), \(\Delta R_{\mathrm{item}}\), delta предупреждений, переходы `status`.

4. Классификация изменений:

| Тип | Сигнал |
|-----|--------|
| Улучшение | рост \(R_{\mathrm{item}}\) / ключевых \(\mathrm{F1}_f\); `failed→ok` без резкого роста ложных цен из допуска |
| Регресс | падение ценового поля или строго item-recall; вспышка ambiguous при прежнем `ok` в v1; систематический сдвиг `brewery` |

### A.7 Fuzz и мутации

Стресс на **confidence + voting**:

1. сдвиг шапки в окне строк \(0\dots N-1\);
2. перестановка / дубликаты колонок в теле данных;
3. удаление случайной доли строк (или отдельный режим только «без падения исключением» если golden не синхронизируется генератором);
4. синонимы заголовков по реестрам + «шумовые» варианты.

Ожидание: корректные **статусы**, отсутствие silent-empty, понятный набор предупреждений.

### A.8 Фикстуры с edge-cases (≥10 синтетических xlsx)

Генерируются скриптом **`scripts/make_excel_fixtures.py`** (**реализация — отдельная задача**).

| № | Имя (рекомендуемое) | Что проверяет |
|---|---------------------|---------------|
| 1 | `header_row_07.xlsx` / `hdr_row_06.xlsx` | Заголовок на строке \(\ge 7\), текст выше блока данных |
| 2 | `brewery_inline_name.xlsx` | Производитель только в названии напитка |
| 3 | `brewery_own_column.xlsx` | Отдельная колонка `brewery`; канонический `beer_name` без дубля |
| 4 | `currency_RUB_vs_rub_synonyms.xlsx` | Валютные синонимы в шапке / групповой строке |
| 5 | `volume_ml_cl_mixed.xlsx` | смешение мл/cl/л включая русскую запятую («0,33 л») |
| 6 | `price_near_stock_cols.xlsx` | Соседство «розница» и «остаток» со схожими заголовками |
| 7 | `multi_table_sheet.xlsx` | Две таблицы одной страницы разной шапки |
| 8 | `empty_rows_inside_block.xlsx` | Шум-пустые строки в середине блока |
| 9 | `merged_header_cells.xlsx` | Объединённые заголовки + подшапки |
| 10 | `pseudo_transpose.xlsx` | Заголовки в столбце A («транспонированное» восприятие) |
| 11 | `autofilter_corrupt_placeholder.xlsx` | Порча filter XML; Graceful degraded Loader без kill процесса |
| 12 | `ambiguous_duplicate_nds_columns.xlsx` | «Цена без НДС» vs «Цена с НДС» как ловушка column-mapper |
| 13 | `duplicate_sku_rows.xlsx` | Дубликаты ключей как нагрузка на `Deduplicator` |

---

## Часть B: Migration plan (strangler)

### B.1 Стратегия

**Strangler fig** + **feature flag** (**`EXCEL_PARSER_PIPELINE_V2`**, синоним **`PARSER_V2_ENABLED`** при чтении настроек). Наружу до Phase 5 стабильно держится `ExcelParser.parse(...) -> List[Dict]`.

### B.2 Фазы и exit criteria

| № | Фаза | Что происходит | Exit criteria перед следующей фазой |
|---|------|----------------|-------------------------------------|
| 0 | **Harness + corpus** | Есть синтетика в репо, приватный корпус согласован, baseline метрик Legacy зафиксирован (`baseline-v1.json`) | synthetic harness зелёный; утверждённые правила добавления эталона; параметр \(\tau\) matching задокументирован |
| 1 | **v2 за флагом** (`EXCEL_PARSER_PIPELINE_V2=false` по умолчанию) | Код пайплайна в `backend/parser_app/parsers_v2/` (**или эволюция DDD-слоя**, см. B.5), публичный `ExcelParser` **диспатчит** | Без включённого флага поведение **битово совпадает** с историческими smoke/snapshot точками; с флагом в dev исключений нет на synthetic-корпусе |
| 2 | **Shadow** | Ответ клиентов — v1; v2 считается **параллельно** (async / sampling / worker), результат только в телеметрии | \(\ge 95\%\) пар без необъяснимых расхождений цен в допуске; ошибки исключений v2 < **0{,}5 % попыток**; CPU-бюджет shadow не пробит неделю наблюдений |
| 3 | **Canary** по `Supplier.id` (1–2 пилота) | Ответ может идти из v2 только у allow-listed | По пилотам \(R_{\mathrm{item}}^{\mathrm{strict}}\) не хуже baseline v1 более чем на \(\delta\) (типично \(\delta=0{,}01\)); жалобы ниже SLA; успешный **drill отката** |
| 4 | **Full v2**, emergency Legacy | все поставщики на v2; Legacy остаётся по emergency-переключателю (напр. **`PARSER_LEGACY_FORCE=true`** only ops) | 14 календарных дней зелёных алёртов (часть C); harness по полному корпусу без новых регрессий относительно Phase 2–3 |
| 5 | **Удаление v1-кода** | чистка `parsers/excel_parser.py`, перенос лексики из `supplier_profiles.py` в реестры | мёртвый код удалён; покрытие harness ≥ порога продукта; обновлены runbook’и |

(Фаз шесть — требование «не меньше пяти» выполняется.)

### B.3 Точки переключения (`parse_dispatcher`)

Расположение: **`backend/parser_app/services/parse_dispatcher.py`** (новый модуль задачей).

```python
# parse_dispatcher.py — псевдокод, не производственный код

def parse_excel_dispatcher(file, supplier_type, brewery_name, supplier_column_mapping, supplier_id=None):
    cfg = settings.PARSER_PIPELINE

    def legacy():
        return legacy_excel_parser.parse(supplier_type, brewery_name, supplier_column_mapping)

    if getattr(cfg, "shadow_mode", False):
        ans = legacy()
        enqueue_async_compare(ans, supplier_id, lambda: pipeline_v2.run(...))
        return ans

    v2_allowed = getattr(cfg, "use_v2", False) or os.getenv("EXCEL_PARSER_PIPELINE_V2") == "true"
    supplier_ok = supplier_id_allowed(getattr(cfg, "supplier_allowlist_v2", set()), supplier_id)

    if v2_allowed and (not getattr(cfg, "supplier_allowlist_v2", None) or supplier_ok):
        return adapt_pipeline_to_legacy_dicts(pipeline_v2.run(...))

    return legacy()

```

Обёртка `ExcelParser.parse` делегирует сюда, сохраняя **сигнатуру**.

### B.4 Откат

1. Выключить канонический флаг и/или очистить canary IDs; при необходимости **`PARSER_LEGACY_FORCE=true`** переводит весь парсинг на Legacy независимо от промежуточных флагов (операционный последний контур безопасности — проектируется совместно с on-call).

2. **Перезапуск** процессов/воркеров после смены env.

3. **Схема БД** основной цены/номенклатуры **не** меняется откатом; таблицы `ParseRun` / feedback живут параллельно и могут временно быть пустыми.

### B.5 Соотношение с уже начатым DDD-слоем (`infrastructure/parsers/excel_parser.py`)

**Решение: довести существующий DDD-слой** (`infrastructure/parsers/excel_parser.py`, `domain/services/`, `application/use_cases/`) до реализации **Pipeline v2**, а не плодить третью ветку.

**Обоснование:** уже разделённые слои, повторное копирование четырёх fallback Loader-стратегий неэкономно; точка strangler должна висеть над **application use-case**, а не порождать дубль эвристик. Отдельная подфаза — **физический split** большого файла infrastructure на модули стадий **без** изменения поведения под harness.

Если противоречие с конфиденцами стадий обнаружено — только тогда параллельный прототип + ADR отменяет решение выше.

### B.6 Чек-лист по ролям

| Шаг | Backend | Ops / SRE | Администратор / данные |
|-----|---------|-----------|-------------------------|
| Подключить telemetry shadow | код + флаги | CPU/лаг мониторинг | информирование |
| Canary allow-list | PR + хранилище allow-list id | наблюдает алёрты | выбор поставщика |
| Full rollout merge | выпиливает временный техдолг | дашборд зелёный N дней | гайды на ручной mapping |
| Post cleanup | удаляет Legacy | экономия железа | обновляет инструкции |

«Ок переход»: метрики из таблицы B.2 столбец exit criteria + триггеры части C.

### B.7 Риски миграции и mitigation

| Риск | Проявление | Mitigation |
|------|------------|------------|
| Производительность двойных прогонов | деградация p95/CPU при shadow | async, sampling доли файлов, лимиты concurrency, circuit breaker shadow |
| Расхождение `dict` между v1 и v2 | «тихие» ошибки сохранения | единый `adapt_pipeline_to_legacy_dicts`, schema-check на границе, A/B diff |
| Параллельные БД-миграции feedback | смешение с rollout | включать записи ParseRun/ParsingFeedback **отдельным** mini-flag; мигрировать до wide canary если нужно |
| Переподгонка только под golden | утрата генерализации | регулярная замена образцов, fuzz блоки части A.7 |

---

## Часть C: Observability + alerting

### C.1 Метрики и структурированные логи проде

События (JSON + `trace_id`):

1. **`parse_started` / `parse_finished`** — `supplier_id`, `file_sha256`, длительность, `pipeline_version`, `loader_strategy`.

2. **`header_detected` / `region_detected`** — краткие структуры кандидатов и финального выбора.

3. **`column_mapping_decided`** — ранжированные `Candidate[T]` до и после tie-break из архитектурных весов.

4. **`parse_status`** итогового `ParseResult` + счётчик предупреждений по кодам стадии.

Prometheus минимально: счётчик **`parser_runs_total{status}`**, histogram **`parser_parse_seconds`** (или `*_bucket`), gauge **`parser_column_mapping_confidence_avg`**, счётчик провалов стадии **`parser_stage_failures_total{stage}`**.

### C.2 Алёрты (≥3 с явными порогами)

| ID | Алёрт | Условие | Действие |
|----|-------|---------|---------|
| A1 | **parser_failure_rate** | доля статусов `failed` среди попыток **> 5 % за 1 ч скользящего окна** (`parser_failure_rate > 0.05 / 1h`) | paging on-call парсинговой роли + freeze canary |
| A2 | **parser_p95** | **`parser_p95 > 5 s`** на окне **1 ч** | throttle shadow / временное снижение concurrency; escalation если повтор через 24 ч |
| A3 | **column_mapping_confidence_avg** | **`column_mapping_confidence_avg < 0,6`** на окне **24 ч** rolling | уведомление команды доменных данных; усилить консервативный режим ambiguity |
| A4 *(опционально rollout)* | Shadow mismatch spike | **`parser_shadow_mismatch_rate > 2 %`** за **`24 ч`** | блок Phase 3, triage A/B отчёта |

### C.3 Дашборд (эскиз)

1. Стек времени `ok` / `partial` / `failed` + отдельный ряд только canary-поставщиков.
2. p50/p95/p99 **`parser_parse_seconds`**.
3. Heatmap ошибок по стадии `Loader→…→Validator`.
4. Топ ошибок по `supplier_id`.
5. Распределение уверенностей столбца (гистограмма + rolling mean).

### C.4 Административный UI при ambiguous результате

1. Если итоговый score поля ниже \(\theta_{\mathrm{field}}\) (из конфигурации архитектуры), показываем блок «колоночный выбор» с ранжированными кандидатами (+ подписи вкладов источников).

2. Сэмплы первых **`N`** непустых ячеек кандидатной колонки рядом.

3. Кнопка **«Подтвердить mapping и запомнить»** пишет `SupplierColumnMapping` с `scope` в **{ `exact_file` (SHA-256), `supplier`, `global` }** и применяется при следующих запусках с весом «user».

4. Аудит: автор, временная метка, TTL override, revoke.

---

## Связность с кодовой базой

Публичный API на переходном этапе: **`ExcelParser(BaseParser).parse(...) -> List[Dict]`**.

Авторегрессионных `test_*.py` специализированных под текущие парсеры **ещё нет** — первичный противовес задаёт harness этого документа.

---

## Открытые вопросы

1. Окончательно зафиксировать один env-ключ документации (`EXCEL_PARSER_PIPELINE_V2` против `PARSER_V2_ENABLED`) в ADR конфиг-слоя Django.

2. Уточнить \(\Phi_{\mathrm{req}}\) и допуск fuzzy-сопоставления для полей после нормализации (крепость, упаковка).
