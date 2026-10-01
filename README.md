# Andromeda backend schema v1

SQLAlchemy 2 ORM-модели и Alembic-миграции создают PostgreSQL-схему Andromeda Schema v1. Проект использует синхронный SQLAlchemy с psycopg 3; API, парсеры и recommendation engine сюда не входят.

## Запуск миграций

Нужны Python 3.11+ и PostgreSQL 13+ (`gen_random_uuid()` встроен в PostgreSQL 13 и новее).

```powershell
python -m pip install -e .
$env:DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE"
python -m alembic upgrade head
```

`DATABASE_URL` задаётся отдельно для приложения и Alembic. `.env.example` содержит шаблон, но автоматически не загружается. Для приложения engine создаётся функцией `andromeda.db.session.create_db_engine()`.

## Состав схемы

48 таблиц сгруппированы по предметным областям:

- приём: университеты, кафедры, программы, кампании, offerings, конкурсные пулы, статистика, экзамены и требования, олимпиады;
- учебные планы: curricula, курсы и предметные области;
- правила: правила, версии, наборы версий, scope на программы и offerings;
- профили: внешние аккаунты, экзамены, олимпиады, индивидуальные достижения, политики дополнительных баллов, квоты и shortlist;
- provenance: источники и полученные артефакты;
- ontology: типы объектов, свойств и связей, ссылки на объекты и assertions.

ORM-модели находятся в `src/andromeda/db/models/`, `Base` и naming convention — в `src/andromeda/db/base.py`. Схема поднимается миграциями из `alembic/versions/`.

UUID генерируется PostgreSQL через `gen_random_uuid()`; ORM также умеет заранее получить UUID через `uuid4`. Деньги, баллы и кредиты хранятся в `NUMERIC`; календарные значения — в `DATE`; временные отметки и valid-time — в `TIMESTAMPTZ`. Assertions сохраняют значение в `TEXT`, проверяя его на соответствие ontology `data_type`; JSONB и GIN-индексы не нужны, пока нет запросов по JSON.

## Направления и конкретные образовательные программы

`program` представляет кодированное направление или специальность. `educational_program` хранит конкретную траекторию/профиль, её кафедру, срок и описание. `program_offering` и `curriculum` ссылаются одновременно на направление и конкретную траекторию; составной FK не позволяет указать траекторию другого направления или университета. `program_department` остаётся связью на уровне направления, а точная кафедра траектории задаётся в `educational_program`.

На старых данных миграция создаёт траектории по связям `program_department` только там, где направление однозначно связано с кафедрой. Если существующий offering или curriculum связан с нулём либо несколькими кафедрами, миграция останавливается и требует явного сопоставления вместо угадывания. `program.duration_months` допускает NULL: при разных сроках обучения источником истины служит конкретная `educational_program.duration_months`.

## Профиль и достижения

`user_profile.principal_id` — nullable уникальный внешний principal. Таблица `user_external_identity` хранит связи с несколькими провайдерами (`max`, `web` и другие) и не реализует аутентификацию. `achievement_type` задаёт изменяемый каталог индивидуальных достижений; `user_achievement` хранит достижения профиля, а `achievement_policy` задаёт дополнительные баллы и необязательный лимит их учёта для конкретной кампании и типа достижения. Виды достижений, включая ГТО, не зашиты в колонки профиля. `user_quota` связывает профиль, кампанию и тип квоты.

## Статистика приёма

`admission_statistic.year` заменён на nullable `snapshot_date`. Год кампании уже доступен через `competition_pool → program_offering → admission_campaign`; отдельный год записи статистики дублировал этот контекст и допускал несовпадение. Дата хранится только когда источник действительно сообщает дату снимка/публикации. Если дата неизвестна, она остаётся NULL; БД допускает не более одной недатированной записи на пул. Проходной и средний баллы не ограничены значением 100: это могут быть суммы нескольких ЕГЭ.

Миграция из старой версии схемы отклоняет upgrade, если в `admission_statistic` есть строки и по старому году нельзя восстановить реальную дату снимка. Следующая миграция разрешает NULL вместо фиктивной даты. Downgrade к версии с обязательной датой завершится ошибкой при NULL; downgrade новой модели также защищён от потери данных, которые старые ключи направления не могут представить.

## Целостность данных

- Составные FK не позволяют связать программу с кампанией, образовательной траекторией или кафедрой другого университета; FK траектории также проверяет её направление. Уникальные ключи защищают кампанию, track-specific offering, конкурсный пул, статистический снимок и M:N-связи от повторов.
- `USER_EXAM.score`, `REQUIREMENT_NODE.min_score` и `OLYMPIAD_BENEFIT.confirmation_score` ограничены диапазоном `0..100`. Ограничение не применяется к агрегированным проходным и средним баллам.
- `OLYMPIAD_BENEFIT.confirmation_exam_id` указывает подтверждающий экзамен; он может быть NULL, если конкретный вид льготы не требует подтверждения.
- `REQUIREMENT_SET` создаётся как `draft`; draft может быть пустым или неполным. PostgreSQL при переходе в `published` проверяет непустое дерево, ровно один корень, отсутствие циклов, отсутствие детей у exam-узлов, число детей у `and`/`or` и достаточное количество детей у `at_least`. Опубликованные наборы и их узлы неизменяемы. Версионирование требований оставлено на следующий этап.
- `POLICY_RULE_VERSION` может содержать scope на несколько программ и/или конкретных offerings. Набор scope-записей работает как объединение; отсутствие scope означает глобальное правило в пределах кампании `RULE_SET`. При добавлении версии в набор БД проверяет, что scope применим хотя бы к одному offering этой кампании. Scope опубликованной версии неизменяем.
- `RULE_SET` фиксирует опубликованные версии правил. Набор, состав набора и версии правил становятся неизменяемыми после публикации.
- Составные FK проверяют соответствие `OBJECT_REF` и `ONTOLOGY_PROPERTY_TYPE`, а также source/target типов link assertion. Trigger `trg_fact_assertion_value_type` проверяет текстовое значение по ontology `data_type`.
- Assertions остаются provenance-записями, не заменяя canonical domain tables. `SOURCE → SOURCE_ARTIFACT → FACT_ASSERTION/LINK_ASSERTION` хранит происхождение, valid-time и доверие; recorded-time намеренно не добавлялся.
- Изменяемые бизнес-справочники представлены lookup-таблицами (`funding_type`, `quota_type`, `achievement_type` и другие). Закрытые технические множества статусов, типов requirement nodes и ontology data types ограничены `CHECK`.
- Исторические связи используют `RESTRICT`; `CASCADE` оставлен для чистых связующих таблиц scope и пользовательского shortlist. FK, используемые в обратных join, индексированы.

Триггеры защищают дерево требований и его lifecycle, опубликованные версии правил и наборы правил, immutable scopes и типизированные ontology facts. Остальные инварианты выражены через `NOT NULL`, `CHECK`, `UNIQUE` и составные FK.

## Проверка на PostgreSQL

Интеграционные тесты используют настоящий PostgreSQL и disposable database. Для локального запуска:

```powershell
python -m pip install -e ".[test]"
$env:DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/EMPTY_TEST_DATABASE"
python -m alembic upgrade head
python -m pytest -q
python -m alembic check
```

Тест `test_migration_lifecycle` проверяет upgrade, `alembic check`, downgrade до `base` и повторный upgrade. Остальные PostgreSQL-тесты проверяют ключевые FK, уникальности, направление/траекторию/кафедру offering и curriculum, requirement trees, scores, scopes, immutable публикации, ontology typing, датированные и недатированные snapshots, достижения и квоты. GitHub Actions запускает полный suite, затем полный цикл downgrade/upgrade и suite повторно на PostgreSQL 17.
