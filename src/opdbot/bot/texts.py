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
    "Шаг {current}/{total} — <b>{title}</b>\n"
    "Допустимые форматы: {allowed_mime}\n"
    "Максимальный размер: {max_size} МБ\n\n"
    "Пришлите файл или фото."
)
DOC_RECEIVED = "✅ Получено: <b>{title}</b> ({current}/{total})"
DOC_INVALID_MIME = "❌ Неверный формат файла. Допустимые: {allowed_mime}. Попробуйте ещё раз."
DOC_TOO_LARGE = "❌ Файл слишком большой. Максимальный размер: {max_size} МБ."
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

FEEDBACK_ASK = "Введите ваше сообщение для HR:"
FEEDBACK_SENT = "✅ Сообщение отправлено HR."

# Errors
ERROR_GENERIC = "Произошла ошибка. Попробуйте позже или свяжитесь с HR."
ERROR_NO_ACTIVE_APPLICATION = "У вас нет активной заявки. Нажмите «Подать заявку»."
