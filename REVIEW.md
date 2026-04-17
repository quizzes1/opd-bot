# Ревью-ТЗ: правки бота opd-bot

**Автор ревью:** Senior Python Developer
**Дата:** 2026-04-17
**Область:** вся кодовая база `src/opdbot/`, миграции, тесты, инфраструктура

Задачи сгруппированы по приоритету. Каждая содержит:
- **Где:** файл(ы) и место
- **Проблема:** что не так и почему
- **Что сделать:** конкретные шаги
- **Acceptance:** как проверить, что правка закрыта

---

## P0 — Критические баги (чинить до любой демо/стенда)

### 1. Race condition при бронировании слота — возможен овербукинг
**Где:** [src/opdbot/db/repo/slots.py:26-32](src/opdbot/db/repo/slots.py#L26-L32) `book_slot`

**Проблема.** Логика «прочитать → проверить capacity → инкрементить» не атомарна. Два кандидата, нажавшие кнопку одновременно, оба пройдут проверку `booked_count < capacity` и получат забронированный слот сверх ёмкости.

**Что сделать.**
- Заменить на атомарный UPDATE с фильтром по capacity:
  ```python
  result = await session.execute(
      update(Slot)
      .where(Slot.id == slot_id, Slot.booked_count < Slot.capacity, Slot.is_active.is_(True))
      .values(booked_count=Slot.booked_count + 1)
  )
  if result.rowcount == 0:
      return None  # слот занят / деактивирован
  ```
- На Postgres уровень изоляции по умолчанию (READ COMMITTED) корректно обработает; на SQLite — тоже (serialized writes).
- Вернуть обновлённый объект отдельным `SELECT`.

**Acceptance.** В юнит-тесте запустить 5 параллельных `book_slot` для slot с capacity=2 — ровно 2 успешных.

---

### 2. `create_all` + Alembic — двойная схема, расхождение prod/dev
**Где:** [src/opdbot/main.py:33-35,68](src/opdbot/main.py#L33-L35), [src/opdbot/main.py:68](src/opdbot/main.py#L68)

**Проблема.** `Base.metadata.create_all` на каждом старте создаёт таблицы по текущим моделям. Если одновременно используется Alembic — при добавлении поля в модель оно появится в БД до миграции, `alembic upgrade` увидит несоответствие или молча разъедется. Классическая двойная ответственность за схему.

**Что сделать.**
- Удалить функцию `create_tables()` и её вызов из `main()`.
- В `README.md` явно прописать: единственный способ инициализации — `uv run alembic upgrade head`.
- Для ускорения dev добавить команду-хелпер в `Makefile`/`justfile`: `alembic upgrade head`.

**Acceptance.** Убрать `opdbot.db`, запустить бота — должен упасть с ошибкой подключения к несуществующей БД. После `alembic upgrade head` стартует нормально.

---

### 3. Вебхук-ветка падает при старте
**Где:** [src/opdbot/main.py:71-81](src/opdbot/main.py#L71-L81)

**Проблема.** `web.run_app(...)` — синхронная функция, запускает свой event-loop. Вызов из уже запущенного async `main()` → `RuntimeError: asyncio.run() cannot be called from a running event loop` (в зависимости от версии aiohttp). Даже если не крешнется — после `run_app` возврат управления не произойдёт, корректное завершение не отработает.

**Что сделать.**
- Использовать `aiohttp.web.AppRunner` / `TCPSite` через async API:
  ```python
  runner = web.AppRunner(app)
  await runner.setup()
  site = web.TCPSite(runner, host="0.0.0.0", port=8080)
  await site.start()
  # ждать до Ctrl+C
  await asyncio.Event().wait()
  ```
- Вынести инициализацию в отдельную функцию `run_webhook(bot, dp)` чтобы `main()` не разрастался.

**Acceptance.** Выставить `WEBHOOK_URL=https://example.com`, запустить — логи должны показать "site started on 0.0.0.0:8080" без эксепшена.

---

### 4. «Запросить документ» спамит всех кандидатов
**Где:** [src/opdbot/bot/handlers/hr/review.py:316-354](src/opdbot/bot/handlers/hr/review.py#L316-L354)

**Проблема.** В обработчике `hr_send_doc_request` HR выбирает конкретное требование из списка, но код берёт **все** заявки в статусе `docs_submitted` с этой целью и рассылает запрос каждому. Комментарий `# We need to get the app ID from the conversation state` в коде признаёт проблему. Это рабочий, но некорректный код, который мы не можем отпустить в прод.

**Что сделать.**
- Хранить `app_id` через FSM: в `hr_request_document` (когда HR нажимает «Запросить документ» в карточке заявки) поставить состояние `HrRequestDocStates.choosing_req` и положить `app_id` в `state.update_data`.
- В `hr_send_doc_request` прочитать `app_id` из `state.get_data()`, уведомить только этого кандидата.
- Добавить `HrRequestDocStates` в `src/opdbot/bot/states/hr.py`.
- Удалить хелпер `list_applications_by_goal` — больше не нужен.
- Создать запись `Message` со статусом запроса и кратким комментом.

**Acceptance.** Создать 2 заявки, нажать «Запросить документ» на первой — уведомление получает только первый кандидат.

---

### 5. Superadmin не получает уведомления, предназначенные HR
**Где:** [src/opdbot/bot/middlewares/auth.py:27-34](src/opdbot/bot/middlewares/auth.py#L27-L34), [src/opdbot/db/repo/users.py:34-38](src/opdbot/db/repo/users.py#L34-L38)

**Проблема.** Middleware выдаёт superadmin роль `admin` в памяти, но в БД у него остаётся `candidate` (или вообще нет записи). Функции уведомлений (`notify_new_docs`, `notify_doc_rejected` и т.д.) ищут получателей через `get_all_hr` — возвращает только `role==hr`. Суперадмин никогда ничего не получит.

**Что сделать.**
- В `/start` (или в отдельном bootstrap-хендлере на первом `get_or_create_user`) — если `tg_id` в `settings.superadmin_tg_ids`, записать `user.role = UserRole.admin` в БД.
- Расширить `get_all_hr` → переименовать в `get_all_staff` и возвращать `role IN (hr, admin)`. Обновить все вызовы.
- Удалить повышение роли из middleware (остаётся только чтение из БД) — middleware не должен иметь сайд-эффектов.

**Acceptance.** Суперадмин, не прописанный вручную как HR, после `/start` получает уведомление о новой заявке.

---

### 6. `docs_submitted` фиксируется без проверки `is_required`
**Где:** [src/opdbot/bot/handlers/candidate/docs.py:138-156](src/opdbot/bot/handlers/candidate/docs.py#L138-L156)

**Проблема.** `pending = [r for r in all_reqs if r.id not in uploaded_ids]` считает все требования. Если кандидат не загрузил необязательный документ (пропустил кнопкой — кстати, кнопки нет), он никогда не уйдёт из цикла. С другой стороны — сейчас вообще нет кнопки «пропустить необязательный», и если в каталоге HR сделал `is_required=False`, бот всё равно потребует файл.

**Что сделать.**
- Фильтровать pending: `if r.is_required and r.id not in uploaded_ids`.
- Добавить inline-кнопку «Пропустить» в `DOC_REQUEST`, если `req.is_required is False`. Обработчик кнопки — переход к следующему требованию без сохранения.

**Acceptance.** Создать `DocumentRequirement(is_required=False)`, пройти онбординг — появляется кнопка «Пропустить», после нажатия переход на следующий шаг.

---

## P1 — Серьёзные проблемы (ломают функциональность или безопасность)

### 7. Enum-типы в Postgres: миграции не обратимы
**Где:** [migrations/versions/0001_init.py:182-191](migrations/versions/0001_init.py#L182-L191)

**Проблема.** SQLAlchemy `sa.Enum(..., name="userrole")` в Postgres создаёт тип `CREATE TYPE userrole AS ENUM(...)`. При `drop_table` тип НЕ удаляется. `alembic downgrade base && upgrade head` упадёт с ошибкой «type already exists».

**Что сделать.**
- В `downgrade()` после `drop_table` добавить явные `DROP TYPE` для всех enum (на Postgres; на SQLite команда будет no-op, обернуть в `if op.get_context().dialect.name == "postgresql"`).
- Альтернатива: перейти на `sa.Enum(..., native_enum=False)` — тогда это будет VARCHAR + CHECK, портируемо между SQLite/PG и мигрируется без плясок.

**Acceptance.** `alembic downgrade base && alembic upgrade head` на чистом Postgres отрабатывает без ошибок.

---

### 8. Индексы отсутствуют на горячих полях
**Где:** [src/opdbot/db/models.py](src/opdbot/db/models.py), [migrations/versions/0001_init.py](migrations/versions/0001_init.py)

**Проблема.** `applications.user_id`, `applications.status`, `documents.application_id`, `documents.status`, `messages.application_id`, `slots(kind, starts_at, is_active)` — всё без индексов. При 1000 заявок и 10 док/заявку HR-фильтры будут seq-scan'ом.

**Что сделать.**
- В моделях проставить `index=True` на указанные одиночные поля.
- Для `slots` — композитный индекс через `__table_args__`:
  ```python
  __table_args__ = (Index("ix_slots_kind_starts_at", "kind", "starts_at"),)
  ```
- Создать миграцию `0002_indexes.py` через `alembic revision --autogenerate`.

**Acceptance.** `\di` в psql показывает новые индексы. `EXPLAIN` на запросе `list_applications` использует index scan.

---

### 9. `docxtpl` optional-импорт скрывает ошибки
**Где:** [src/opdbot/services/documents.py:8-13](src/opdbot/services/documents.py#L8-L13)

**Проблема.** `try/except ImportError` + флаг `DOCXTPL_AVAILABLE` — попытка «graceful degrade». Но `docxtpl` указан как обязательная зависимость в [pyproject.toml:15](pyproject.toml#L15). Если `docxtpl` не импортнулся, это реальный баг окружения, а бот при клике «Сформировать характеристику» выдаст `RuntimeError` в рантайме вместо падения на старте.

**Что сделать.**
- Удалить `try/except`, сделать обычный `from docxtpl import DocxTemplate`.
- Убрать `DOCXTPL_AVAILABLE` и проверку в `_render_template`.

**Acceptance.** Удалить `docxtpl` из окружения — бот падает на старте с ImportError, а не ломает генерацию в момент использования.

---

### 10. Типизация `app: object` в services/documents.py
**Где:** [src/opdbot/services/documents.py:37,57,77](src/opdbot/services/documents.py#L37)

**Проблема.** Сигнатуры `render_application(app: object)` вынуждают использовать `getattr(...)` — теряются типы, IDE не подсказывает, опечатки в именах атрибутов не ловятся. Это было сделано чтобы избежать циклического импорта, но импорт вполне возможен напрямую.

**Что сделать.**
- Заменить `app: object` на `app: "Application"` (forward-ref, чтобы избежать циклической зависимости), импорт через `if TYPE_CHECKING:`:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from opdbot.db.models import Application
  ```
- Заменить `getattr(user, "full_name", "") or ""` на `app.user.full_name or ""`.
- Убрать все `getattr`-костыли.

**Acceptance.** `mypy src/opdbot/services/documents.py` не ругается; IDE автокомплитит поля `app.user.full_name`.

---

### 11. Флаг `updated_at` устанавливается вручную
**Где:** [src/opdbot/db/repo/applications.py:49,81,91](src/opdbot/db/repo/applications.py#L49)

**Проблема.** В модели [models.py:127-129](src/opdbot/db/models.py#L127) уже есть `onupdate=func.now()`. Ручное `application.updated_at = datetime.now()` — это (а) дубль (б) timezone-naive Python-время вместо server_default. При переходе на timezone-aware DateTime поломается.

**Что сделать.** Удалить все `application.updated_at = datetime.now()` в репозиториях. Убедиться, что `onupdate` срабатывает на flush.

**Acceptance.** Тест: обновить статус заявки, прочитать `updated_at` — он > `created_at`.

---

### 12. Несогласованные пути: абсолютные vs относительные
**Где:** [src/opdbot/services/storage.py:30-34](src/opdbot/services/storage.py#L30-L34), [src/opdbot/services/documents.py:16-20](src/opdbot/services/documents.py#L16-L20), [src/opdbot/bot/handlers/hr/documents_gen.py:207](src/opdbot/bot/handlers/hr/documents_gen.py#L207)

**Проблема.** `Document.file_path` — относительный путь от `storage_root`, а `GeneratedDocument.file_path` — абсолютный (Path возвращается as-is из `_get_output_path`). В `hr_download_generated_doc` используется `Path(gd.file_path)` напрямую, а в `hr_download_document` — `Path(settings.storage_root) / doc.file_path`. Это ломает переносимость хранилища (сменили монтирование → все пути в `generated_documents` битые).

**Что сделать.**
- В `documents.py` `_get_output_path` возвращать `Path`, в `services.documents` при записи в БД сохранять `.relative_to(settings.storage_root)`.
- Унифицировать чтение: всегда через хелпер `services.storage.get_absolute_path(relative)`.

**Acceptance.** В БД все `file_path` начинаются с `{user_id}/`, а не с `C:\...` или `/app/...`.

---

### 13. `POSTGRES_PASSWORD:-secret` — опасный дефолт
**Где:** [docker-compose.yml:7,22](docker-compose.yml#L7)

**Проблема.** Если админ забыл `.env`, Postgres поднимется с паролем `secret`. На стенде с публичным портом — уязвимость.

**Что сделать.** Убрать дефолт: `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?must be set}` — compose откажется стартовать без переменной. Добавить строку в `README.md`.

**Acceptance.** `docker-compose up` без `POSTGRES_PASSWORD` в `.env` выдаёт «POSTGRES_PASSWORD must be set».

---

### 14. `MemoryStorage` теряет FSM при рестарте
**Где:** [src/opdbot/main.py:47](src/opdbot/main.py#L47)

**Проблема.** Кандидат в процессе загрузки 8 документов; бот перезапускается → FSM сброшен, кандидат получает главное меню без контекста. UX-деградация, которая усугубится в проде.

**Что сделать.**
- Добавить опциональный `RedisStorage` при наличии `REDIS_URL` в конфиге:
  ```python
  if settings.redis_url:
      storage = RedisStorage.from_url(settings.redis_url)
  else:
      storage = MemoryStorage()
  ```
- В dev оставить Memory, в compose поднять Redis как сервис.
- Зависимость: `aiogram[redis]` или `redis>=5`.

**Acceptance.** С `REDIS_URL` заданным, прервать бота на шаге 3/6, рестарт — кандидат получает "Пришлите документ 3/6" при следующем сообщении.

---

### 15. Нет обработки `TelegramRetryAfter`
**Где:** [src/opdbot/services/notifications.py](src/opdbot/services/notifications.py), [src/opdbot/bot/handlers/candidate/docs.py:147-154](src/opdbot/bot/handlers/candidate/docs.py#L147-L154)

**Проблема.** При рассылке уведомлений 10+ HR одновременно Telegram вернёт `TelegramRetryAfter`. Сейчас — просто логируется, уведомление теряется.

**Что сделать.**
- В `notify_user` перехватывать `TelegramRetryAfter`, ждать `e.retry_after`, повторять один раз:
  ```python
  except TelegramRetryAfter as e:
      await asyncio.sleep(e.retry_after)
      return await bot.send_message(...)  # one retry
  ```
- Рассылку по HR делать через `asyncio.gather(...)` с семафором на 20 одновременных запросов.

**Acceptance.** Замокать `send_message` который первые 2 вызова выдаёт RetryAfter(1) — функция возвращает True.

---

### 16. Медосмотр: дата не фиксируется
**Где:** [src/opdbot/bot/handlers/hr/documents_gen.py:18-61](src/opdbot/bot/handlers/hr/documents_gen.py#L18-L61)

**Проблема.** `hr_send_medical_referral` генерирует документ и отправляет файл кандидату, но `application.medical_at` остаётся `NULL`. В карточке HR эта дата навсегда «—».

**Что сделать.**
- После генерации направления предложить HR выбрать слот типа `medical` (если настроены) или ввести дату вручную → сохранить в `application.medical_at`.
- Либо просто ставить «factual_medical_sent_at» (неявно) — нужно согласовать.

**Acceptance.** После нажатия «Отправить на медосмотр» → выбор даты → в карточке отображается.

---

### 17. Ошибка в middleware: `event.event` не существует в aiogram 3
**Где:** [src/opdbot/bot/middlewares/auth.py:20-23](src/opdbot/bot/middlewares/auth.py#L20-L23)

**Проблема.** `event.event if hasattr(event.event, "from_user") else None` — у `Update` нет атрибута `.event`. Код мёртвый (работает только через `data["event_from_user"]`, которое aiogram заполняет сам), но при нестандартных типах апдейтов сломается.

**Что сделать.** Упростить: взять `event_from_user` только из `data`, если нет — вернуть дефолт. Удалить ветку с `isinstance(event, Update)`.

**Acceptance.** Code review: ветка с `event.event` удалена, `hasattr` не используется.

---

### 18. Запрос на скачивание документа не проверяет, что заявка существует
**Где:** [src/opdbot/bot/handlers/hr/review.py:103-127](src/opdbot/bot/handlers/hr/review.py#L103-L127) `hr_download_document`

**Проблема.** Берётся `Document` по id, путь строится от `storage_root`, файл отправляется. Если HR-callback «протёк» через логи/скриншот неадмину, тот тоже имеет `role==hr` → может скачать любой документ по id (перебором). Это by design (все HR видят всё), но лучше хотя бы логировать.

**Что сделать.**
- Добавить запись в `AuditLog` на каждое скачивание: `event=doc_downloaded, details=doc_id`.
- Аналогично для `hr_download_generated_doc`.

**Acceptance.** После скачивания в `audit_logs` появилась запись с `actor_tg_id` и `doc_id`.

---

### 19. Прикрепление файла в `notify_user` отправляет ДВА сообщения
**Где:** [src/opdbot/services/notifications.py:11-13](src/opdbot/services/notifications.py#L11-L13)

**Проблема.** Сначала `send_message(text)`, потом `send_document(document)` — два отдельных сообщения. UX ломается если первое прошло, а второе упало с RetryAfter.

**Что сделать.**
- Если `document` передан — использовать `bot.send_document(tg_id, document, caption=text, parse_mode="HTML")`. Одно сообщение, атомарно.
- Учесть лимит подписи 1024 символа — если `text` длиннее, fallback на два сообщения с комментарием.

**Acceptance.** `hr_send_medical_referral` отправляет одно сообщение с файлом и подписью.

---

### 20. Валидация файла: MIME из Telegram — не источник правды
**Где:** [src/opdbot/utils/validators.py](src/opdbot/utils/validators.py), [src/opdbot/bot/handlers/candidate/docs.py:88-99](src/opdbot/bot/handlers/candidate/docs.py#L88-L99)

**Проблема.** Telegram-клиент может выставить `mime_type=""` или неправильный. Мы верим MIME, а расширение файла (`file_name`) игнорируем.

**Что сделать.**
- В `validate_file` принимать также `filename`, сверять по `Path(filename).suffix.lower().lstrip(".")`.
- MIME — дополнительная проверка, не основная.
- Рассмотреть `python-magic` для magic-byte проверки первого килобайта (защита от переименования `.exe` в `.pdf`) — опционально.

**Acceptance.** Отправить файл `test.pdf` с `mime_type=""` — проходит валидацию.

---

## P2 — Качество кода, рефакторинг, UX

### 21. Импорты внутри функций — code smell
**Где:** [src/opdbot/bot/handlers/candidate/status.py:62-66](src/opdbot/bot/handlers/candidate/status.py#L62-L66), [src/opdbot/bot/handlers/hr/review.py:48-49, 117-118, 324-325, 357-360](src/opdbot/bot/handlers/hr/review.py#L48-L49), [src/opdbot/bot/handlers/hr/catalog.py:22, 40, 153, 194](src/opdbot/bot/handlers/hr/catalog.py#L22), [src/opdbot/bot/handlers/hr/applications.py:49, 134-136, 155](src/opdbot/bot/handlers/hr/applications.py#L49)

**Проблема.** 20+ мест с `from ... import ...` внутри функций. Ухудшает читаемость, прячет циклические зависимости. `InlineKeyboardBuilder` импортируется в 8 разных местах.

**Что сделать.** Вынести все импорты наверх файла. Если возник циклический импорт — развязать через `TYPE_CHECKING` или вынести общий хелпер в отдельный модуль.

**Acceptance.** `ruff check --select I` проходит без ошибок import-order.

---

### 22. «📄 Подать заявку» создаёт дубликат заявки
**Где:** [src/opdbot/bot/handlers/candidate/status.py:60-81](src/opdbot/bot/handlers/candidate/status.py#L60-L81)

**Проблема.** Кандидат с активной заявкой в статусе `docs_in_progress` нажимает кнопку — создаётся вторая `Application`. В «Мои заявки» появятся обе, FSM переходит на новую, документы у старой осиротевают.

**Что сделать.**
- Перед созданием проверять активные заявки: если есть в `docs_in_progress` / `docs_submitted` / `interview_scheduled` — показать кнопку «Продолжить текущую» или «Отменить и начать новую» (подтверждение).
- При отмене — перевести старую в `cancelled`.

**Acceptance.** Ручной тест: создать заявку, не доделать, нажать «Подать заявку» — диалог предлагает действия.

---

### 23. Меню кандидата не скрывает лишнее после финализации
**Где:** [src/opdbot/bot/keyboards/main_menu.py:5-10](src/opdbot/bot/keyboards/main_menu.py#L5-L10)

**Проблема.** Кандидат `approved` или `rejected` видит в меню «Записаться на собеседование» и «Изменить документы». Нажатие выдаст «Нет активной заявки».

**Что сделать.**
- Сделать `candidate_main_menu(has_active_application: bool)` — если нет активной, скрыть нерелевантные кнопки и оставить «Подать заявку» + «Мои заявки».
- Передавать флаг из хендлеров.

**Acceptance.** После approve меню кандидата показывает только «Мои заявки» и «Подать заявку».

---

### 24. Регулярка телефона пропускает `(` `)`
**Где:** [src/opdbot/bot/handlers/candidate/onboarding.py:19,43](src/opdbot/bot/handlers/candidate/onboarding.py#L19)

**Проблема.** `phone = text.replace(" ", "").replace("-", "")` не убирает `()`. Пользователь вводит `+7 (900) 123-45-67` — валидация падает, UX раздражающий.

**Что сделать.**
- Нормализовать: `re.sub(r"[^\d+]", "", text)`.
- После — проверять по регулярке.
- Хранить в одном каноническом формате `+79001234567`.

**Acceptance.** Тест: `validate_phone("+7 (900) 123-45-67")` → принято, сохранено как `+79001234567`.

---

### 25. Фильтр заявок — только один фиксированный статус, без «Все активные»
**Где:** [src/opdbot/bot/keyboards/hr.py:34-42](src/opdbot/bot/keyboards/hr.py#L34-L42)

**Проблема.** Кнопка «Все» игнорирует отменённые/отклонённые — HR вынужден листать мусор. Нет фильтра по цели, по дате.

**Что сделать.**
- Добавить фильтр «Активные» (status not in [rejected, cancelled]).
- Добавить вторичный фильтр по цели (подменю после выбора статуса).
- Добавить пагинацию (см. задачу 26).

**Acceptance.** HR видит раздельные списки активных, завершённых, отказов.

---

### 26. Пагинация заявок: жёсткий `limit=20`, без «дальше»
**Где:** [src/opdbot/db/repo/applications.py:60-61](src/opdbot/db/repo/applications.py#L60-L61), [src/opdbot/bot/handlers/hr/applications.py:33-61](src/opdbot/bot/handlers/hr/applications.py#L33-L61)

**Проблема.** 21-я заявка невидима. Offset пропихивается в сигнатуру репозитория, но никто не передаёт.

**Что сделать.**
- Кнопки «◀️ Предыдущие / Следующие ▶️» с callback `hr:filter:{key}:{page}`.
- Страница хранится в callback_data (stateless).

**Acceptance.** С 25 заявками отображается страница 1/2, кнопка «Следующие» ведёт на 21-25.

---

### 27. Поиск через двойной цикл — N+1
**Где:** [src/opdbot/bot/handlers/hr/applications.py:157-166](src/opdbot/bot/handlers/hr/applications.py#L157-L166)

**Проблема.** Для каждого найденного пользователя вызывается `list_applications(session)` → ВСЕ заявки из БД, фильтруются в Python.

**Что сделать.**
- Один JOIN: `SELECT Application ... JOIN User ... WHERE User.full_name ILIKE :q OR ...`.
- Вынести в репозиторий `search_applications_by_user_query(query, limit)`.

**Acceptance.** EXPLAIN показывает один запрос вместо N+1.

---

### 28. Рандомные строки прямо в хендлерах, не в `texts.py`
**Где:** [src/opdbot/bot/handlers/hr/applications.py:126](src/opdbot/bot/handlers/hr/applications.py#L126) «Введите ФИО...», [src/opdbot/bot/handlers/hr/slots.py:43,75,89,103](src/opdbot/bot/handlers/hr/slots.py#L43), [src/opdbot/bot/handlers/hr/documents_gen.py:75,83,90,98](src/opdbot/bot/handlers/hr/documents_gen.py#L75) и ещё ~30 мест

**Проблема.** `texts.py` существует, но большая часть сообщений остаётся прямо в коде. Инконсистентность.

**Что сделать.** Вынести все пользовательские строки в `texts.py`. Кодовое ревью — прогрепать `message.answer(`, `edit_text(`, `callback.answer(` на русские литералы.

**Acceptance.** `grep -rE 'answer\("[А-Я]' src/` возвращает 0 строк.

---

### 29. Алиасинг `Message as DbMessage` — путаница
**Где:** [src/opdbot/db/models.py:185](src/opdbot/db/models.py#L185), [src/opdbot/bot/handlers/candidate/feedback.py:9](src/opdbot/bot/handlers/candidate/feedback.py#L9), [src/opdbot/bot/handlers/hr/review.py:13](src/opdbot/bot/handlers/hr/review.py#L13)

**Проблема.** Модель БД `Message` коллидирует с `aiogram.types.Message`. Везде приходится алиасить.

**Что сделать.** Переименовать модель в `ChatMessage` (или `AppMessage`). Обновить все импорты, миграцию на переименование таблицы делать не нужно (имя таблицы остаётся `messages`).

**Acceptance.** Ни одного `Message as DbMessage` в коде.

---

### 30. Логи пишутся в относительный `logs/bot.log`
**Где:** [src/opdbot/logging.py:14](src/opdbot/logging.py#L14)

**Проблема.** Если бот запущен не из корня репо, логи пишутся в `<cwd>/logs/bot.log`. В контейнере это `/app/logs/bot.log` (ок), но локально при запуске из `src/` — путь сломается.

**Что сделать.** Сделать путь настраиваемым через `settings.log_dir: Path`, по умолчанию `Path(__file__).resolve().parents[2] / "logs"`.

**Acceptance.** `uv run python -c "from opdbot.logging import setup_logging; setup_logging()"` из любой директории — логи в одном и том же месте.

---

### 31. `settings = Settings()` падает на import без `.env`
**Где:** [src/opdbot/config.py:25](src/opdbot/config.py#L25)

**Проблема.** Alembic-команды, `python -c "from opdbot import ..."`, IDE-линтеры — всё падает с `ValidationError: bot_token required`. Это мешает, например, запустить `alembic upgrade head` без валидного токена.

**Что сделать.**
- Сделать `bot_token: str = ""` (опциональный), но в `main.py` добавить проверку `if not settings.bot_token: raise SystemExit("BOT_TOKEN is required")`.
- Alembic миграции не используют токен → смогут запускаться без него.

**Acceptance.** `unset BOT_TOKEN && uv run alembic upgrade head` — работает. `uv run python -m opdbot.main` — падает с понятным сообщением.

---

### 32. Отсутствует глобальный `/cancel` для HR
**Где:** [src/opdbot/bot/handlers/common.py:52-56](src/opdbot/bot/handlers/common.py#L52-L56)

**Проблема.** HR застрял в `HrSlotStates.waiting_duration` (случайно зашёл), теперь каждое его сообщение = попытка ввести длительность.

**Что сделать.** `cmd_cancel` уже очищает state — OK. Но добавить в каждом HR FSM-хендлере (или через middleware) — reply-клавиатура с кнопкой «❌ Отмена», не inline-кнопка.

**Acceptance.** Войти в создание слота, нажать «❌ Отмена» — возврат в HR-меню.

---

### 33. Валидация характеристики: `period_to >= period_from`
**Где:** [src/opdbot/bot/handlers/hr/documents_gen.py:105-113](src/opdbot/bot/handlers/hr/documents_gen.py#L105-L113)

**Проблема.** HR вводит дату окончания раньше начала — документ сгенерируется со смешной продолжительностью.

**Что сделать.** После ввода `period_to` проверить >= `period_from`, иначе ошибка «Дата окончания должна быть позже начала».

**Acceptance.** Ввести period_from=01.05, period_to=20.04 — бот отказывает.

---

### 34. `slots_keyboard` формат без года
**Где:** [src/opdbot/bot/keyboards/calendar.py:12](src/opdbot/bot/keyboards/calendar.py#L12) `strftime("%d.%m %H:%M")`

**Проблема.** Слот на `01.01 09:00` неоднозначен через год. В кнопке ограничение 64 символа — места хватит для `%d.%m.%Y`.

**Что сделать.** Заменить на `%d.%m.%Y %H:%M` или `%d.%m %H:%M (через N дн.)`.

**Acceptance.** Кнопка слота показывает полную дату.

---

### 35. Двойной вызов `get_requirements_for_goal`
**Где:** [src/opdbot/bot/handlers/candidate/docs.py:81,137](src/opdbot/bot/handlers/candidate/docs.py#L81)

**Проблема.** Один запрос в начале хендлера, ещё один через 50 строк — две round-trip в БД.

**Что сделать.** Вызвать один раз, сохранить в переменной `all_reqs`, переиспользовать.

**Acceptance.** Лог SQL показывает один `SELECT document_requirements`.

---

### 36. Зависимость `python-docx` неиспользуется
**Где:** [pyproject.toml:14](pyproject.toml#L14)

**Проблема.** Весь рендер через `docxtpl`. `python-docx` установлен, но не импортируется.

**Что сделать.** Удалить из `pyproject.toml`, пересобрать lock (`uv sync`).

**Acceptance.** `grep -r "import docx" src/` ничего не находит.

---

### 37. `Application.status=draft` остаётся после выбора цели
**Где:** [src/opdbot/db/repo/applications.py:13,11-15](src/opdbot/db/repo/applications.py#L11-L15), [src/opdbot/bot/handlers/candidate/onboarding.py:82](src/opdbot/bot/handlers/candidate/onboarding.py#L82)

**Проблема.** После `create_application` статус `draft`. Переход в `docs_in_progress` должен происходить при первой загрузке документа, но код этого не делает — сразу скачок в `docs_submitted`.

**Что сделать.**
- После первого сохранённого документа ставить `docs_in_progress`.
- `draft` оставить только для «выбрал цель, ни одного файла».
- Либо убрать `docs_in_progress` из enum, если не используем.

**Acceptance.** После загрузки 1 документа из 6 — статус `docs_in_progress`.

---

### 38. `Application.cancelled` — нет пути попасть в него
**Где:** [src/opdbot/db/models.py:42](src/opdbot/db/models.py#L42)

**Проблема.** Статус в enum есть, но ни кандидат, ни HR не могут в него перевести.

**Что сделать.**
- Добавить кандидату в «Мои заявки» кнопку «Отменить заявку» для активных.
- HR: кнопка «Отменить» в карточке (отличается от «Отказ» — инициатор кандидат/внутренняя причина).

**Acceptance.** Кандидат может отменить свою заявку, статус `cancelled`.

---

### 39. `handle_document_upload` не ловит случай, когда файл > 20 МБ
**Где:** [src/opdbot/bot/handlers/candidate/docs.py:89-99](src/opdbot/bot/handlers/candidate/docs.py#L89-L99)

**Проблема.** Bot API не позволяет скачивать файлы > 20 МБ (без local Bot API). Telegram даже не доставит такое сообщение хендлеру — ок. Но если кандидат шлёт 49 МБ через «как документ» — приходит, `bot.download_file` падает с `BadRequest`. Сейчас это не обработано.

**Что сделать.**
- Если `size > 20 * 1024 * 1024` — отдать пользователю «файл слишком большой для Telegram, сожмите».
- `max_size_mb` из каталога применять тоже.

**Acceptance.** Отправка файла 25 МБ → понятное сообщение, не трейсбек.

---

### 40. `Application.documents` загружается только в `get_application` без фильтра
**Где:** [src/opdbot/db/repo/applications.py:23-25](src/opdbot/db/repo/applications.py#L23-L25)

**Проблема.** `selectinload(Application.documents)` подтягивает все документы, включая `superseded`. В карточке HR они попадают в UI.

**Что сделать.**
- Либо фильтровать на стороне БД через `with_loader_criteria`/`and_`.
- Либо использовать репозиторий `get_documents_for_application` который уже фильтрует, а из `get_application` убрать `selectinload(documents)`.

**Acceptance.** В карточке HR нет superseded-документов.

---

## P3 — Инфраструктура, тесты, сопровождаемость

### 41. Нет линтера и форматтера
**Что сделать.** Добавить в `pyproject.toml`:
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
strict = true
```
Прогнать `ruff check --fix` один раз, зафиксировать.

### 42. Нет CI
**Что сделать.** `.github/workflows/ci.yml`: на PR запускать `uv sync --all-extras`, `ruff check`, `pytest`.

### 43. Тестов почти нет
**Что сделать.** Покрыть:
- `services/storage.py::save_tg_file` (мок Bot).
- `services/documents.py::render_*` (фикстуры с минимальными DOCX-шаблонами).
- `db/repo/slots.py::book_slot` — ПАРАЛЛЕЛЬНЫЙ сценарий (см. задачу 1).
- Smoke-тест FSM онбординга через `aiogram_tests` или моки.
Целевое покрытие критичного пути — 60%.

### 44. Нет `Makefile`/`justfile`
**Что сделать.** Добавить команды:
```
install: uv sync
migrate: uv run alembic upgrade head
dev: uv run python -m opdbot.main
test: uv run pytest
lint: uv run ruff check
fmt: uv run ruff format
```

### 45. README: несколько актуализаций
- Команда `pip install python-docx reportlab fpdf` — удалить, эти зависимости не используются.
- Убрать упоминание `reportlab`/`fpdf` из секции «Стек» (их нет в pyproject).
- Добавить раздел «Первоначальная настройка HR»: как повысить роль первому сотруднику через `SUPERADMIN_TG_IDS` + `/grant_hr`.

### 46. `templates/README.md` — создать
**Что сделать.** Отдельный файл со списком Jinja-тегов на каждый из трёх шаблонов, примерами. Сейчас [README.md:140-150](README.md#L140-L150) ссылается на него, но его нет.

### 47. Добавить `healthcheck` в docker-compose для бота
**Что сделать.** Простой endpoint `/health` в webhook-режиме либо команда `uv run python -c "import opdbot"` как проверка.

### 48. Логика бэкапа описана, но не автоматизирована
**Что сделать.** Либо добавить cron-контейнер в compose, либо убрать упоминание «бэкап робокопи» из README (он не включён).

### 49. Неточности в `GeneratedDocument.kind` enum в `characteristic`
**Где:** [src/opdbot/bot/handlers/hr/documents_gen.py:175](src/opdbot/bot/handlers/hr/documents_gen.py#L175)

**Проблема.** Кнопка показывает `gd.kind.value` = `practice_characteristic` (на латинице). UX.

**Что сделать.** Словарь `GEN_DOC_LABELS = {"application_form": "Заявление", ...}` в `texts.py`, использовать в UI.

### 50. Бот молча игнорирует сообщения вне FSM и вне reply-кнопок
**Где:** общее

**Проблема.** Кандидат в главном меню пишет «Когда собеседование?» — бот не отвечает. Нечего подсказать.

**Что сделать.** Глобальный fallback-хендлер: если не совпало ни с чем — «Не понял команду, нажмите кнопку в меню или /help». С низким приоритетом.

---

## Порядок исполнения (рекомендация)

**Неделя 1 — критические баги:**
1. № 1 (race slot), 2 (create_all), 3 (webhook), 4 (request_doc broadcast), 5 (superadmin notify), 6 (is_required)

**Неделя 2 — функциональные проблемы:**
11 (updated_at), 12 (paths), 14 (Redis), 15 (retry), 16 (medical_at), 19 (single-message), 22 (duplicate app), 9/10 (docx типизация)

**Неделя 3 — UX и качество:**
остальные P1/P2 + тесты (43) + линтер (41)

**Неделя 4 — инфра:**
P3 + документация

---

## Чек-лист приёмки релиза

- [ ] `alembic downgrade base && alembic upgrade head` проходит на Postgres
- [ ] `uv run pytest` — зелёный, покрытие ≥60% на `services/` и `db/repo/`
- [ ] `ruff check` без ошибок
- [ ] 2 кандидата одновременно бронируют один слот — один успех, один «занято»
- [ ] После рестарта бота кандидат продолжает FSM-шаги с места остановки (Redis)
- [ ] Суперадмин (не добавленный вручную HR) получает уведомления о новых заявках
- [ ] HR-запрос документа уходит только к одному кандидату
- [ ] Генерация DOCX работает на Windows и в Linux-контейнере
- [ ] Логи пишутся, ротируются, содержат audit-записи о скачиваниях
