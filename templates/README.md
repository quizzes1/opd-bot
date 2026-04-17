# Шаблоны документов

Все шаблоны используют Jinja-теги (формат docxtpl).

## application.docx — Заявление на приём

Поля: `{{ full_name }}`, `{{ phone }}`, `{{ goal_title }}`, `{{ application_id }}`, `{{ date }}`

## medical_referral.docx — Направление на медосмотр

Поля: `{{ full_name }}`, `{{ phone }}`, `{{ goal_title }}`, `{{ application_id }}`, `{{ date }}`

## practice_characteristic.docx — Характеристика практики/стажировки

Поля: `{{ full_name }}`, `{{ goal_title }}`, `{{ supervisor }}`, `{{ topic }}`, `{{ period_from }}`, `{{ period_to }}`, `{{ date }}`

---

Шаблоны `.docx` необходимо создать в MS Word с указанными тегами и поместить в эту директорию.
