# План разработки Telegram-бота ПТЗ (opd-bot)

## Контекст

Цель — автоматизировать процесс трудоустройства, практики и стажировки: сбор документов от кандидатов, согласование дат собеседования/медосмотра/обучения, генерация кадровых документов (заявление на приём, направление на медосмотр, характеристика практики) и передача всего этого HR-сотруднику ПТЗ через единый Telegram-бот. Репозиторий пуст (только `README.md`), проект делаем с нуля.

По ТЗ (ПДФ `Документ_DOCX.pdf`) бот встраивается в этапы: предварительный отбор → входное интервью → очное собеседование (остаётся офлайн) → оформление документов. Автоматизация должна закрыть ≥70% рутинных операций.

### Решения, согласованные с пользователем

| Параметр | Выбор |
|---|---|
| Фреймворк бота | aiogram 3.x |
| БД | SQLite для dev → PostgreSQL в проде (через SQLAlchemy + Alembic) |
| Хранение файлов | локальная ФС `storage/` + бэкап |
| HR-интерфейс | тот же бот, отдельное меню по Telegram ID |
| Шаблоны DOCX | часть есть — недостающие сверстать вручную |
| Список документов на цель | хранится в БД, редактируется HR из бота |
| MVP | путь кандидата + HR-админка + генерация DOCX/PDF |
| Вне MVP | CSV/Excel-экспорт, интеграция 1С/email |

---

## 1. Стек и зависимости

- **Python 3.11+**
- **aiogram 3.13+** — бот, роутеры, FSM, inline-клавиатуры
- **SQLAlchemy 2.x (async)** + **asyncpg** (prod) / **aiosqlite** (dev)
- **Alembic** — миграции
- **Pydantic v2 + pydantic-settings** — конфиг через `.env`
- **python-docx** — заполнение готовых DOCX-шаблонов
- **docxtpl** — Jinja-подстановки в DOCX (удобнее python-docx для сложных шаблонов)
- **docx2pdf** (Windows/MS Office) *или* **LibreOffice headless** — конвертация DOCX→PDF (оценить на целевой ОС деплоя)
- **aiogram-calendar** или собственная inline-клавиатура — выбор дат
- **loguru** — логирование
- **pytest + pytest-asyncio** — тесты

Менеджер зависимостей: `uv` (быстрый, lockfile из коробки) или `poetry`. По умолчанию — **uv**.

---

## 2. Структура проекта

```
opd-bot/
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── alembic.ini
├── README.md
├── docker-compose.yml          # postgres + бот (для prod)
├── migrations/                 # alembic
│   └── versions/
├── templates/                  # DOCX-шаблоны
│   ├── application.docx        # заявление на приём
│   ├── medical_referral.docx   # направление на медосмотр
│   └── practice_characteristic.docx
├── storage/                    # файлы кандидатов (gitignored)
│   └── {user_id}/{application_id}/{doc_code}_{ts}.ext
├── static/                     # картинки-схемы, инструкции
│   └── pass_scheme.jpg
├── src/
│   └── opdbot/
│       ├── __init__.py
│       ├── main.py             # entrypoint: Dispatcher, polling/webhook
│       ├── config.py           # Pydantic Settings
│       ├── logging.py
│       ├── db/
│       │   ├── base.py         # async engine, sessionmaker
│       │   ├── models.py       # все SQLAlchemy модели
│       │   └── repo/           # репозитории (User, Application, Document, Slot)
│       ├── bot/
│       │   ├── middlewares/
│       │   │   ├── db.py       # inject AsyncSession в handler
│       │   │   └── auth.py     # определение роли (candidate/hr)
│       │   ├── keyboards/      # inline + reply клавиатуры
│       │   │   ├── main_menu.py
│       │   │   ├── goals.py
│       │   │   ├── calendar.py
│       │   │   └── hr.py
│       │   ├── states/
│       │   │   ├── candidate.py   # FSM: OnboardingStates, DocUploadStates…
│       │   │   └── hr.py
│       │   ├── handlers/
│       │   │   ├── common.py      # /start, /help, /cancel
│       │   │   ├── candidate/
│       │   │   │   ├── onboarding.py   # выбор цели
│       │   │   │   ├── docs.py         # загрузка файлов
│       │   │   │   ├── scheduling.py   # выбор дат
│       │   │   │   ├── status.py       # "Мои заявки"
│       │   │   │   └── feedback.py     # "Связаться с HR"
│       │   │   └── hr/
│       │   │       ├── menu.py
│       │   │       ├── applications.py # список, карточка, фильтры
│       │   │       ├── review.py       # одобрение/запрос доп. док-тов
│       │   │       ├── slots.py        # управление слотами
│       │   │       └── catalog.py      # CRUD целей и требуемых документов
│       │   └── texts.py            # все строки в одном месте (ru)
│       ├── services/
│       │   ├── documents.py        # DOCX рендеринг (docxtpl)
│       │   ├── pdf.py              # DOCX → PDF
│       │   ├── storage.py          # сохранение/чтение файлов, нормализация путей
│       │   ├── notifications.py    # push кандидату/HR
│       │   ├── slots.py            # бизнес-логика слотов (выдача, бронь)
│       │   └── catalog.py          # работа с Goal/DocumentRequirement
│       └── utils/
│           ├── validators.py       # проверка mime/размера файла
│           └── datetime.py
└── tests/
    ├── conftest.py
    ├── test_handlers/
    ├── test_services/
    └── fixtures/
```

---

## 3. Схема БД

Все таблицы через SQLAlchemy 2.0 `DeclarativeBase` + `Mapped[]` аннотации. Ключевые модели:

### `User`
- `id` (PK, int)
- `tg_id` (unique, bigint)
- `tg_username`, `full_name`, `phone`
- `role` (enum: `candidate`, `hr`, `admin`)
- `is_active`, `created_at`

HR-пользователи заводятся сидером/`/grant_hr` командой суперадмина (id из `.env`).

### `Goal` (справочник целей)
- `id`, `code` (`employment`, `practice`, `internship`), `title`, `description`, `is_active`
- Сидируется начальными значениями миграцией.

### `DocumentRequirement` (какие документы нужны на цель)
- `id`, `goal_id` (FK), `code` (`passport`, `snils`, `inn`, `diploma`, `photo`…), `title`, `is_required`, `allowed_mime` (`jpeg,pdf,docx`), `max_size_mb`, `order`
- HR редактирует из бота (раздел "Каталог").

### `Application` (заявка кандидата)
- `id`, `user_id` (FK), `goal_id` (FK)
- `status` (enum: `draft`, `docs_in_progress`, `docs_submitted`, `interview_scheduled`, `interview_passed`, `training_scheduled`, `approved`, `rejected`, `cancelled`)
- `interview_at`, `medical_at`, `training_at` (nullable datetime)
- `hr_comment`, `created_at`, `updated_at`

### `Document` (файл от кандидата)
- `id`, `application_id` (FK), `requirement_id` (FK)
- `file_path` (относительно `storage/`), `tg_file_id`, `original_name`, `mime`, `size_bytes`
- `status` (enum: `uploaded`, `approved`, `rejected`, `superseded`), `reject_reason`
- `uploaded_at`

Замена файла → старый помечается `superseded`, новый `uploaded`.

### `GeneratedDocument` (то, что бот сгенерировал: заявление, направление, характеристика)
- `id`, `application_id`, `kind` (enum: `application_form`, `medical_referral`, `practice_characteristic`)
- `file_path` (DOCX), `pdf_path` (nullable), `created_at`

### `Slot` (свободные даты для записи)
- `id`, `kind` (enum: `interview`, `medical`, `training`)
- `starts_at`, `ends_at`, `capacity`, `booked_count`, `is_active`
- HR создаёт партиями из меню "Слоты".

### `Message` (переписка HR ↔ кандидат через бота)
- `id`, `application_id`, `from_role`, `text` / `requested_doc_code`, `created_at`

### `AuditLog`
- Ключевые события (смена статуса, одобрение/реджект, замена файла) — для отладки и безопасности.

---

## 4. FSM-сценарии кандидата (aiogram States)

Все состояния в [src/opdbot/bot/states/candidate.py](src/opdbot/bot/states/candidate.py):

1. **`Onboarding`** — `/start` → собираем ФИО, телефон → выбор цели inline-кнопками → создаётся `Application (status=draft)` → отправка инструкции по пропуску и схемы территории (картинка из `static/`) в зависимости от цели.
2. **`DocUpload`** — итерируем по `DocumentRequirement`, по одному за шаг. На каждом:
   - сообщение: "Пришлите `{title}` (форматы: {allowed_mime}, до {max_size} МБ)"
   - приём `message.document` или `message.photo`, валидация (`services/storage.validate`)
   - сохранение в `storage/{user_id}/{application_id}/`
   - подтверждение "Получено" + прогресс "3/8"
3. **`InterviewScheduling`** — inline-календарь (свободные `Slot` с `kind=interview`) → бронь → `Application.interview_at`, `Slot.booked_count+=1`.
4. **`MedicalStep`** — бот генерирует `medical_referral.docx` (см. §6) и присылает кандидату. По прохождении медосмотра HR отмечает факт.
5. **`TrainingScheduling`** — аналогично §3, но для `Slot.kind=training` + отправка маршрута/инструкции.
6. **`Done`** — итоговое сообщение, статус `docs_submitted`.

На любом шаге доступны:
- `/cancel` — возврат в главное меню
- inline-кнопка "Главное меню"
- главное меню: "Мои заявки", "Отправить документы", "Выбрать дату собеседования", "Выбрать дату обучения", "Изменить документы", "Связаться с HR"

FSM-состояние хранится в **aiogram MemoryStorage** для dev, **RedisStorage** опционально в проде (в MVP можно обойтись memory; при рестарте пользователь продолжит через меню).

---

## 5. HR-меню

Middleware [src/opdbot/bot/middlewares/auth.py](src/opdbot/bot/middlewares/auth.py) при каждом апдейте читает `User.role` по `tg_id`. Для роли `hr` доступен отдельный корневой роутер.

### Главное меню HR
- **Заявки** → список с фильтрами (статус, цель, дата) → карточка
- **Слоты** → просмотр/создание/деактивация
- **Каталог документов** → цели и список требуемых документов
- **Поиск** — по ФИО / Telegram username / номеру телефона

### Карточка заявки
- Шапка: ФИО, цель, статус, даты (собеседование/медосмотр/обучение)
- Список загруженных документов, у каждого кнопка "Скачать" (бот отсылает файл из `storage/`) и "Одобрить / Запросить замену"
- Список сгенерированных документов (заявление/направление/характеристика) с кнопкой "Скачать"
- Действия (inline-кнопки):
  - "Отметить обработанным"
  - "Назначить собеседование" (если дата не выбрана)
  - "Отправить на медосмотр" → триггерит генерацию направления и отправку кандидату
  - "Запросить документ" → выбор `DocumentRequirement` → уведомление кандидату
  - "Написать кандидату" → свободный текст, сохраняется в `Message`
  - "Принят" / "Отказ" → финальные статусы + уведомление кандидату
  - "Сформировать характеристику" (для практики/стажировки) → ввод темы/руководителя → DOCX

Все действия логируются в `AuditLog`.

---

## 6. Генерация документов

[src/opdbot/services/documents.py](src/opdbot/services/documents.py) — функции:

- `render_application(application: Application) -> Path` — `templates/application.docx` через `docxtpl`, подстановки: ФИО, дата рождения, цель, срок (до конца учёбы / период практики), дата.
- `render_medical_referral(application: Application) -> Path`
- `render_practice_characteristic(application: Application, supervisor: str, topic: str, period_from, period_to) -> Path`

Шаблоны используют Jinja-теги прямо в DOCX: `{{ full_name }}`, `{{ goal_title }}`, `{{ period }}` и т.д.

Недостающие шаблоны (часть у заказчика уже есть) помечаем в `templates/README.md` с примерами полей — сверстаем по мере получения.

PDF-вариант (опционально): [src/opdbot/services/pdf.py](src/opdbot/services/pdf.py) — через `libreoffice --headless --convert-to pdf`. В MVP отправляем DOCX, PDF — доработкой.

Сохранение: `storage/{user_id}/{application_id}/generated/{kind}_{ts}.docx` + запись в `GeneratedDocument`.

---

## 7. Хранилище файлов и безопасность

- **Пути**: `storage/{user_id}/{application_id}/{requirement_code}_{uploaded_at}.ext` — детерминированно, легко чистить.
- **Валидация на приёме** ([src/opdbot/utils/validators.py](src/opdbot/utils/validators.py)):
  - расширение ∈ `allowed_mime` требования
  - размер ≤ `max_size_mb`
  - простой magic-check через `python-magic` (опционально)
- **Доступ**: файлы отдаются только HR через бота (не HTTP). Кандидат получает только свои.
- **Права ОС**: директория `storage/` — `chmod 700` на Linux, на Windows — ACL только для сервисного пользователя.
- **Бэкап**: cron/Task Scheduler → `rsync`/`robocopy` в отдельную локацию раз в сутки. Описать в `README.md`, не кодить.
- **Секреты**: `.env` (не коммитить), пример в `.env.example` (токен бота, DSN БД, список HR TG-id).

Авторизация HR — whitelist Telegram ID в БД (`role=hr`). Суперадмин указывается в `.env` как `SUPERADMIN_TG_IDS=...`, он же через `/grant_hr <tg_id>` добавляет HR.

---

## 8. Уведомления и обратная связь

[src/opdbot/services/notifications.py](src/opdbot/services/notifications.py):
- `notify_candidate(user, text, **kwargs)` — через `bot.send_message`, с фолбэком на `aiogram.exceptions.TelegramForbiddenError`
- `notify_hr_pool(text)` — рассылка всем `role=hr`
- Триггеры:
  - новый документ загружен → HR (тихое уведомление)
  - статус заявки изменён → кандидат
  - HR запросил документ → кандидат + создание записи в `Message`
  - кандидат ответил → HR

---

## 9. Конфигурация и запуск

### `.env.example`
```
BOT_TOKEN=
DATABASE_URL=sqlite+aiosqlite:///./opdbot.db
# prod: postgresql+asyncpg://opdbot:pass@localhost:5432/opdbot
STORAGE_ROOT=./storage
TEMPLATES_ROOT=./templates
SUPERADMIN_TG_IDS=123456789
LOG_LEVEL=INFO
WEBHOOK_URL=          # пусто = polling
```

### Команды разработки
- `uv sync` — установка зависимостей
- `uv run alembic upgrade head` — миграции
- `uv run python -m opdbot.main` — запуск бота (polling)
- `uv run pytest` — тесты

### Docker (prod)
`docker-compose.yml`: сервисы `postgres`, `bot`; том `./storage` смонтирован в контейнер. Описание в `README.md`.

---

## 10. Этапы реализации (рекомендуемый порядок)

1. **Каркас** (1–2 дня): `pyproject.toml`, `config.py`, логирование, подключение к БД, минимальный `main.py` с `/start`, Dockerfile.
2. **Модели + миграции** (1 день): все таблицы из §3, сиды `Goal` и стартовых `DocumentRequirement`, сидер суперадмина.
3. **Онбординг кандидата** (2 дня): FSM, выбор цели, главное меню, "Мои заявки".
4. **Сбор документов** (2–3 дня): пошаговая загрузка, валидация, замена, хранилище.
5. **Слоты и календарь** (2 дня): модель, HR-меню управления слотами, inline-календарь для кандидата, бронь.
6. **HR-админка** (3 дня): список заявок, карточка, одобрение/реджект документов, фильтры.
7. **Генерация DOCX** (2 дня): заявление, направление, характеристика, docxtpl.
8. **Каталог документов в БД** (1 день): HR CRUD через бота.
9. **Уведомления, переписка** (1–2 дня): HR ↔ кандидат.
10. **Тесты и полировка** (2–3 дня): покрытие критичных путей, logger, обработка ошибок Telegram API (ретраи).
11. **Деплой** (1 день): docker-compose, systemd-unit / Windows Service, бэкап.

Итого: **~3–4 недели** одним разработчиком, сходится с ТЗ (3–5 недель).

---

## 11. Критические файлы (будут созданы)

- [pyproject.toml](pyproject.toml), [.env.example](.env.example), [alembic.ini](alembic.ini)
- [src/opdbot/main.py](src/opdbot/main.py), [src/opdbot/config.py](src/opdbot/config.py)
- [src/opdbot/db/models.py](src/opdbot/db/models.py) — главный файл со схемой
- [src/opdbot/bot/handlers/candidate/](src/opdbot/bot/handlers/candidate/) — весь пользовательский путь
- [src/opdbot/bot/handlers/hr/](src/opdbot/bot/handlers/hr/) — админская часть
- [src/opdbot/services/documents.py](src/opdbot/services/documents.py) — DOCX-рендер
- [templates/](templates/) — шаблоны документов
- [migrations/versions/0001_init.py](migrations/versions/0001_init.py)

---

## 12. План верификации

- **Локальный прогон**: `uv run python -m opdbot.main` с тестовым ботом (отдельный токен `@opdbot_dev_bot`).
- **Сценарий кандидата** (ручной): `/start` → цель "Практика" → загрузить все документы (тестовые файлы) → выбрать дату собеседования → получить уведомление → отправить медосмотр → получить направление DOCX → проверить содержимое в Word.
- **Сценарий HR** (ручной, второй аккаунт): добавить себя через `/grant_hr` суперадмином → открыть список заявок → скачать документ → одобрить → запросить замену одного документа → проверить, что кандидат получил уведомление → сформировать характеристику → проверить DOCX.
- **DB**: `sqlite3 opdbot.db` — проверить статусы, даты, связи; прогнать `alembic downgrade base && upgrade head` — миграции обратимы.
- **Тесты**: `uv run pytest` — юнит-тесты сервисов (`documents`, `storage`, `slots`) и хотя бы smoke-тест FSM через `aiogram.test` (или mock).
- **Нагрузка/ошибки**: специально прислать файл неправильного формата / больше лимита → ожидаем аккуратное сообщение, а не 500.
- **Приёмка**: демо на двух реальных кандидатах и одном HR-сотруднике ПТЗ (по ТЗ — финальный этап перед релизом).

---

## 13. Вне MVP (backlog)

- CSV/Excel-экспорт заявок (1 день) — `openpyxl`/`pandas`.
- Интеграция с 1С / email HR-отдела (отдельная сессия, требует API 1С).
- Перевод HR-панели в веб (FastAPI + Jinja) при росте объёма.
- i18n (если понадобится англ. версия).
- Redis FSM storage и вебхук-режим (вместо polling) при нагрузке >50 RPS.
