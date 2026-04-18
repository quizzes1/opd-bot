WELCOME = (
    "Добро пожаловать в бот оформления ПТЗ!\n\n"
    "Здесь вы можете подать заявку на трудоустройство, практику или стажировку.\n"
    "Для начала введите ваше полное ФИО:"
)

ASK_PHONE = "Введите ваш номер телефона (например: +79001234567):"

ASK_GOAL = "Выберите цель обращения:"

GOAL_SELECTED = "Цель выбрана: <b>{goal}</b>\n\nТеперь нужно загрузить необходимые документы."

MAIN_MENU = "Главное меню. Выберите действие:"

MY_APPLICATIONS = "Ваши заявки:"

NO_APPLICATIONS = "У вас пока нет заявок. Нажмите «Подать заявку» чтобы начать."

ACTIVE_APPLICATION_EXISTS = (
    "У вас уже есть активная заявка #{app_id}. Дождитесь завершения текущего процесса "
    "или отмените заявку в разделе «Мои заявки»."
)

APPLICATION_CANCELLED = "❌ Заявка #{app_id} отменена."

CANCELLED = "Действие отменено. Вы в главном меню."

HELP_TEXT = (
    "Этот бот помогает оформить документы для трудоустройства, практики или стажировки в ПТЗ.\n\n"
    "Доступные команды:\n"
    "/start — начать / перезапустить\n"
    "/cancel — отменить текущее действие\n"
    "/help — эта справка"
)

# Document upload
DOC_REQUEST = (
    "Шаг {current}/{total} — <b>{title}</b>{optional}\n"
    "Допустимые форматы: {allowed_mime}\n"
    "Максимальный размер: {max_size} МБ\n\n"
    "Пришлите файл или фото."
)
DOC_RECEIVED_SIMPLE = "✅ Получено: <b>{title}</b>"
DOC_INVALID_MIME = "❌ Неверный формат файла. Допустимые: {allowed_mime}. Попробуйте ещё раз."
DOC_TOO_LARGE = "❌ Файл слишком большой. Максимальный размер: {max_size} МБ."
DOC_TOO_LARGE_FOR_TG = (
    "❌ Файл превышает лимит Telegram для скачивания ботом (20 МБ). "
    "Сожмите файл или отправьте его по частям."
)
DOC_OPTIONAL_MARK = " (необязательно)"
DOC_SKIP_BUTTON = "Пропустить"
DOC_SKIPPED = "⏭ Документ пропущен."
ALL_DOCS_DONE = (
    "✅ Все документы загружены!\n\n"
    "Ваша заявка передана на проверку HR. "
    "Вы получите уведомление о результате."
)

# Scheduling
CHOOSE_INTERVIEW_DATE = "Выберите удобную дату и время для собеседования:"
CHOOSE_TRAINING_DATE = "Выберите удобную дату и время для обучения:"
NO_SLOTS_AVAILABLE = "К сожалению, свободных слотов нет. Обратитесь к HR через кнопку «Связаться с HR»."
SLOT_BOOKED = "✅ Записались на {kind}: <b>{dt}</b>"

# Status labels
STATUS_LABELS = {
    "draft": "Черновик",
    "docs_in_progress": "Загрузка документов",
    "docs_submitted": "Документы на проверке",
    "interview_scheduled": "Собеседование назначено",
    "interview_passed": "Собеседование пройдено",
    "training_scheduled": "Обучение назначено",
    "approved": "Принят ✅",
    "rejected": "Отказ ❌",
    "cancelled": "Отменено",
}

GOAL_LABELS = {
    "employment": "Трудоустройство",
    "practice": "Практика",
    "internship": "Стажировка",
}

SLOT_KIND_LABELS = {
    "interview": "собеседование",
    "medical": "медосмотр",
    "training": "обучение",
}

APPLICATION_CARD = (
    "📋 <b>Заявка #{app_id}</b>\n"
    "Цель: {goal}\n"
    "Статус: {status}\n"
    "Создана: {created_at}\n"
    "{interview_line}"
    "{training_line}"
)

# HR texts
HR_WELCOME = "Меню HR. Выберите действие:"
HR_APPLICATIONS_LIST = "Список заявок (показаны {count}):"
HR_NO_APPLICATIONS = "Заявок нет."
HR_APPLICATION_CARD = (
    "📋 <b>Заявка #{app_id}</b>\n"
    "Кандидат: {full_name} (@{username})\n"
    "Телефон: {phone}\n"
    "Цель: {goal}\n"
    "Статус: {status}\n"
    "Создана: {created_at}\n"
    "{interview_line}"
    "{training_line}"
    "Комментарий HR: {hr_comment}\n"
)

HR_DOC_APPROVED = "✅ Документ «{title}» одобрен."
HR_DOC_REJECTED = "❌ Документ «{title}» отклонён. Кандидат получил уведомление."
HR_ASK_REJECT_REASON = "Укажите причину отклонения документа:"

HR_SLOT_CREATED = "✅ Слот создан: {kind} — {dt}"
HR_ASK_SLOT_DATE = "Введите дату и время слота (формат: ДД.ММ.ГГГГ ЧЧ:ММ):"
HR_ASK_SLOT_DURATION = "Введите длительность в минутах (например: 30):"
HR_ASK_SLOT_CAPACITY = "Введите количество мест (например: 1):"

HR_MEDICAL_ASK_DATE = (
    "Укажите дату и время медосмотра (ДД.ММ.ГГГГ ЧЧ:ММ), чтобы зафиксировать в заявке:"
)
HR_MEDICAL_DATE_SET = "✅ Дата медосмотра зафиксирована: {dt}."

HR_GRANT_USAGE = "Использование: /grant_hr <telegram_id>"
HR_GRANT_SUCCESS = "✅ Пользователь {tg_id} получил роль HR."
HR_GRANT_NOT_FOUND = "Пользователь {tg_id} не найден. Он должен сначала написать /start боту."
HR_GRANT_FORBIDDEN = "❌ У вас нет прав суперадмина."

# Notifications
NOTIFY_NEW_DOCS = "📄 Кандидат {full_name} загрузил документы по заявке #{app_id}."
NOTIFY_STATUS_CHANGED = "Статус вашей заявки #{app_id} изменён: <b>{status}</b>."
NOTIFY_DOC_REJECTED = (
    "HR отклонил документ «{title}» по заявке #{app_id}.\n"
    "Причина: {reason}\n\n"
    "Пожалуйста, загрузите документ повторно."
)
NOTIFY_DOC_REQUESTED = "HR запросил дополнительный документ по заявке #{app_id}: <b>{title}</b>."
NOTIFY_HR_MESSAGE = "Сообщение от HR по заявке #{app_id}:\n\n{text}"
NOTIFY_CANDIDATE_MESSAGE = "Сообщение от кандидата {full_name} по заявке #{app_id}:\n\n{text}"
NOTIFY_MEDICAL_REFERRAL = (
    "📎 Направление на медосмотр по заявке #{app_id} сформировано. Файл прикреплён."
)
NOTIFY_MEDICAL_DATE = (
    "🏥 Дата медосмотра по заявке #{app_id}: <b>{dt}</b>."
)

FEEDBACK_ASK = "Введите ваше сообщение для HR:"
FEEDBACK_SENT = "✅ Сообщение отправлено HR."

# Errors
ERROR_GENERIC = "Произошла ошибка. Попробуйте позже или свяжитесь с HR."
ERROR_NO_ACTIVE_APPLICATION = "У вас нет активной заявки. Нажмите «Подать заявку»."

# HR — common short answers
HR_NO_ACCESS = "Нет доступа."
HR_APP_NOT_FOUND = "Заявка не найдена."
HR_DOC_NOT_FOUND = "Документ не найден."
HR_FILE_MISSING = "Файл не найден на диске."
HR_REQ_NOT_FOUND = "Требование не найдено."
HR_SESSION_EXPIRED = "Сессия устарела, повторите действие."
HR_APPLICATIONS_FOUND = "Найдено заявок: {count}"
HR_NO_APPLICATIONS_FOUND = "Заявки не найдены."
HR_EMPTY_QUERY = "Пустой запрос."

# HR — filter / search / menu
HR_FILTER_PROMPT = "Фильтр заявок:"
HR_SEARCH_PROMPT = "Введите ФИО, @username или телефон кандидата:"

# HR — slots
HR_SLOTS_HEADER = "Активные слоты:"
HR_SLOTS_EMPTY = "Нет активных слотов."
HR_SLOT_LINE = "{kind_label}: {dt} (мест: {free}/{capacity}) [#{slot_id}]"
HR_SLOT_CHOOSE_KIND = "Выберите тип слота:"
HR_SLOT_BAD_DATE = "Неверный формат. Введите дату и время в формате ДД.ММ.ГГГГ ЧЧ:ММ:"
HR_SLOT_BAD_MINUTES = "Введите положительное число минут:"
HR_SLOT_BAD_CAPACITY = "Введите положительное число:"
HR_SLOT_DEACTIVATED = "Слот #{slot_id} деактивирован."

# HR — catalog
HR_CATALOG_CHOOSE_GOAL = "Выберите цель для просмотра документов:"
HR_CATALOG_REQ_LABEL = "{title} ({mark})"
HR_CATALOG_REQUIRED_MARK = "обяз."
HR_CATALOG_OPTIONAL_MARK = "необяз."
HR_CATALOG_GOAL_HEADER = "Документы для цели (всего {count}):"
HR_CATALOG_ASK_TITLE = "Введите название документа:"
HR_CATALOG_ASK_CODE = "Введите код документа (латиница, без пробелов, напр. passport):"
HR_CATALOG_BAD_CODE = "Код должен содержать только латинские буквы и подчёркивание:"
HR_CATALOG_ASK_MIME = "Допустимые форматы (через запятую, напр. pdf,jpg,jpeg):"
HR_CATALOG_ASK_SIZE = "Максимальный размер в МБ (напр. 10):"
HR_CATALOG_BAD_SIZE = "Введите положительное число:"
HR_CATALOG_ADDED = "✅ Документ «{title}» добавлен в каталог."
HR_CATALOG_REQ_CARD = (
    "<b>{title}</b>\n"
    "Код: {code}\n"
    "Форматы: {allowed_mime}\n"
    "Макс. размер: {max_size} МБ\n"
    "Обязателен: {required}\n"
)
HR_CATALOG_YES = "да"
HR_CATALOG_NO = "нет"
HR_CATALOG_DELETED = "Требование удалено."

# HR — documents generation
HR_DOCGEN_LABELS = {
    "application_form": "Заявление",
    "medical_referral": "Направление на медосмотр",
    "practice_characteristic": "Характеристика",
}
HR_DOCGEN_ERROR = "Ошибка генерации документа: {error}"
HR_DOCGEN_BAD_DATETIME = "Неверный формат. Введите ДД.ММ.ГГГГ ЧЧ:ММ."
HR_DOCGEN_BAD_DATE = "Неверный формат. Введите дату ДД.ММ.ГГГГ:"
HR_DOCGEN_ASK_SUPERVISOR = "Введите ФИО руководителя практики/стажировки:"
HR_DOCGEN_ASK_TOPIC = "Введите тему практики/стажировки:"
HR_DOCGEN_ASK_PERIOD_FROM = "Введите дату начала (ДД.ММ.ГГГГ):"
HR_DOCGEN_ASK_PERIOD_TO = "Введите дату окончания (ДД.ММ.ГГГГ):"
HR_DOCGEN_PERIOD_INVALID = "Дата окончания должна быть не раньше даты начала."
HR_DOCGEN_CHAR_CAPTION = "Характеристика по заявке #{app_id}"
HR_DOCGEN_EMPTY = "Сгенерированных документов нет."
HR_DOCGEN_LIST_HEADER = "Сгенерированные документы по заявке #{app_id}:"

# HR — review
HR_REVIEW_NO_DOCS = "Документов нет."
HR_REVIEW_DOCS_HEADER = "Документы по заявке #{app_id}:"
HR_REVIEW_DOC_CARD = (
    "Документ: <b>{req_title}</b>\n"
    "Файл: {file_name}\n"
    "Размер: {size_kb} КБ\n"
    "Статус: {status}\n"
)
HR_REVIEW_REJECT_REASON_LINE = "Причина отклонения: {reason}\n"
HR_REVIEW_APP_APPROVED = "✅ Заявка #{app_id} одобрена."
HR_REVIEW_APP_REJECTED = "❌ Заявка #{app_id} отклонена."
HR_APP_CANCELLED = "🗑 Заявка #{app_id} отменена администратором."
HR_REVIEW_CHOOSE_DOC_REQ = "Выберите документ для запроса:"
HR_REVIEW_DOC_REQUEST_SENT = "✅ Запрос документа «{title}» отправлен кандидату по заявке #{app_id}."
HR_REVIEW_ASK_MESSAGE = "Введите сообщение кандидату:"
HR_REVIEW_MESSAGE_SENT = "✅ Сообщение отправлено кандидату."

# Reply buttons (cancel in FSM flows)
BTN_CANCEL_REPLY = "❌ Отмена"
USERNAME_NONE = "нет"
