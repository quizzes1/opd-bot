# opd-bot

Telegram-бот для автоматизации трудоустройства, практики и стажировки в ПТЗ.

Закрывает ≥70% рутинных операций HR: сбор документов от кандидатов, согласование дат собеседования/медосмотра/обучения, генерация кадровых документов (заявление на приём, направление на медосмотр, характеристика практики).

---

## Функциональность

### Для кандидата
- Регистрация (ФИО, телефон) и выбор цели: трудоустройство / практика / стажировка
- Пошаговая загрузка документов с валидацией формата и размера
- Выбор даты собеседования и обучения из доступных слотов
- Просмотр статуса заявки
- Переписка с HR через бота

### Для HR
- Список заявок с фильтрами по статусу и цели
- Карточка кандидата: скачать документы, одобрить / отклонить каждый
- Управление слотами (создание, деактивация)
- Запрос дополнительных документов
- Отправка сообщений кандидату
- Генерация DOCX: заявление, направление на медосмотр, характеристика практики
- CRUD каталога требуемых документов по каждой цели

---

## Стек

| Компонент | Технология |
|---|---|
| Бот | [aiogram 3.x](https://docs.aiogram.dev/) |
| БД (dev) | SQLite + aiosqlite |
| БД (prod) | PostgreSQL + asyncpg |
| ORM / миграции | SQLAlchemy 2 async + Alembic |
| Конфиг | pydantic-settings + `.env` |
| DOCX-шаблоны | docxtpl (Jinja2 в Word) |
| Логирование | loguru |
| Менеджер зависимостей | [uv](https://docs.astral.sh/uv/) |

---

## Быстрый старт (dev)

### 1. Установить зависимости

```bash
uv sync
```

### 2. Настроить окружение

```bash
cp .env.example .env
```

Открыть `.env` и заполнить:

```
BOT_TOKEN=<токен от @BotFather>
SUPERADMIN_TG_IDS=<ваш Telegram ID>
```

### 3. Создать таблицы и применить миграции

```bash
uv run alembic upgrade head
```

Это создаст `opdbot.db` с таблицами и заполнит справочники (цели, базовые требования к документам).

### 4. Запустить бота

```bash
uv run python -m opdbot.main
```

### 5. Тесты

```bash
uv run pytest
```

---

## Первоначальная настройка HR

После первого запуска бота (свежая база) роли `hr` нет ни у кого, кроме суперадминов из `SUPERADMIN_TG_IDS`. Чтобы выдать роль HR коллеге:

1. Коллега открывает бота и отправляет `/start` — это создаёт запись о пользователе в БД.
2. Узнайте его Telegram ID (через `@userinfobot` или из логов бота).
3. Суперадмин отправляет в бота:

   ```
   /grant_hr <telegram_id>
   ```

После этого пользователь видит HR-меню. Команда `/grant_hr` доступна только суперадминам — обычные HR её не видят.

Полный список зарегистрированных пользователей и их ролей доступен напрямую через БД:

```bash
sqlite3 opdbot.db "SELECT id, tg_id, full_name, role FROM users;"
```

---

## Структура проекта

```
opd-bot/
├── src/opdbot/
│   ├── main.py                  # точка входа
│   ├── config.py                # настройки через .env
│   ├── db/
│   │   ├── models.py            # все SQLAlchemy-модели
│   │   ├── base.py              # engine, sessionmaker
│   │   └── repo/                # репозитории (users, applications, documents, slots)
│   ├── bot/
│   │   ├── handlers/
│   │   │   ├── common.py        # /start, /help, /cancel, /grant_hr
│   │   │   ├── candidate/       # онбординг, загрузка документов, расписание, статус
│   │   │   └── hr/              # заявки, ревью документов, слоты, каталог, генерация DOCX
│   │   ├── middlewares/         # DB-сессия, роль пользователя
│   │   ├── keyboards/           # inline и reply клавиатуры
│   │   ├── states/              # FSM-состояния кандидата и HR
│   │   └── texts.py             # все строки на русском
│   ├── services/
│   │   ├── documents.py         # рендеринг DOCX через docxtpl
│   │   ├── pdf.py               # конвертация DOCX → PDF (LibreOffice)
│   │   ├── storage.py           # сохранение файлов из Telegram
│   │   └── notifications.py     # push-уведомления кандидату и HR
│   └── utils/
│       ├── validators.py        # проверка mime-типа и размера файла
│       └── datetime.py          # вспомогательные функции для дат
├── migrations/                  # Alembic (версии миграций)
├── templates/                   # DOCX-шаблоны (создаются вручную)
├── storage/                     # файлы кандидатов (gitignored)
├── tests/
├── .env.example
├── docker-compose.yml
└── pyproject.toml
```

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `BOT_TOKEN` | — | Токен бота (обязательно) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./opdbot.db` | DSN базы данных |
| `STORAGE_ROOT` | `./storage` | Папка для файлов кандидатов |
| `TEMPLATES_ROOT` | `./templates` | Папка с DOCX-шаблонами |
| `SUPERADMIN_TG_IDS` | — | Telegram ID суперадмина (через запятую) |
| `LOG_LEVEL` | `INFO` | Уровень логов |
| `WEBHOOK_URL` | `` | URL вебхука (пусто = polling) |

---

## DOCX-шаблоны

Шаблоны создаются вручную в MS Word и кладутся в `templates/`. Теги — Jinja2-синтаксис `{{ поле }}`.

| Файл | Поля |
|---|---|
| `application.docx` | `full_name`, `phone`, `goal_title`, `application_id`, `date` |
| `medical_referral.docx` | `full_name`, `phone`, `goal_title`, `application_id`, `date` |
| `practice_characteristic.docx` | `full_name`, `goal_title`, `supervisor`, `topic`, `period_from`, `period_to`, `date` |

Подробнее — в [templates/README.md](templates/README.md).

---

## Роли и доступ

| Роль | Как назначить | Возможности |
|---|---|---|
| `candidate` | автоматически при `/start` | подача заявки, загрузка документов, запись на слоты |
| `hr` | суперадмин через `/grant_hr <tg_id>` | полная HR-панель |
| `admin` | `SUPERADMIN_TG_IDS` в `.env` | все права HR + назначение ролей |

---

## Деплой (Docker)

```bash
# скопировать и заполнить .env
cp .env.example .env

docker-compose up -d
```

`docker-compose.yml` поднимает PostgreSQL и бот-контейнер. Том `./storage` монтируется в контейнер.

После первого запуска применить миграции:

```bash
docker-compose exec bot uv run alembic upgrade head
```

### Бэкап файлов и БД

Директория `storage/` (загруженные документы) и БД (`opdbot.db` или dump из Postgres) должны бэкапиться регулярно.

Скрипт `scripts/backup.sh` (Linux/macOS) делает дневной бэкап файлов и Postgres-дампа в `./backups/<дата>/`. На Windows — аналогичный `scripts/backup.bat`. Запускать через cron / Планировщик задач.

Быстрый ручной бэкап:

```bash
# Postgres
docker-compose exec -T postgres pg_dump -U opdbot opdbot > backups/db-$(date +%Y%m%d).sql

# Файлы кандидатов
tar -czf backups/storage-$(date +%Y%m%d).tar.gz storage/
```

---

## Healthcheck

Контейнер бота имеет встроенный healthcheck (см. `docker-compose.yml`), который проверяет, что процесс жив. При работе через webhook (`WEBHOOK_URL` задан) дополнительный HTTP-эндпоинт `/health` отвечает `200 OK`.

---

## Разработка

```bash
# установить зависимости (включая dev)
uv sync

# запустить тесты
uv run pytest

# создать новую миграцию после изменения моделей
uv run alembic revision --autogenerate -m "описание"

# применить миграции
uv run alembic upgrade head

# откатить последнюю миграцию
uv run alembic downgrade -1
```
