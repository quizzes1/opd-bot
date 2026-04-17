from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from docxtpl import DocxTemplate

from opdbot.config import settings

if TYPE_CHECKING:
    from opdbot.db.models import Application


def _get_output_path(user_id: int, application_id: int, kind: str) -> tuple[Path, Path]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = Path(settings.storage_root).resolve()
    out_dir = root / str(user_id) / str(application_id) / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    absolute = out_dir / f"{kind}_{ts}.docx"
    return absolute, absolute.relative_to(root)


def _render_template(template_name: str, context: dict, output_path: Path) -> None:
    template_path = Path(settings.templates_root) / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    doc = DocxTemplate(template_path)
    doc.render(context)
    doc.save(output_path)


async def render_application(app: "Application") -> Path:
    context = {
        "full_name": app.user.full_name or "",
        "phone": app.user.phone or "",
        "goal_title": app.goal.title,
        "application_id": app.id,
        "date": datetime.now().strftime("%d.%m.%Y"),
    }
    absolute, relative = _get_output_path(app.user.id, app.id, "application_form")
    _render_template("application.docx", context, absolute)
    return relative


async def render_medical_referral(app: "Application") -> Path:
    context = {
        "full_name": app.user.full_name or "",
        "phone": app.user.phone or "",
        "goal_title": app.goal.title,
        "application_id": app.id,
        "date": datetime.now().strftime("%d.%m.%Y"),
    }
    absolute, relative = _get_output_path(app.user.id, app.id, "medical_referral")
    _render_template("medical_referral.docx", context, absolute)
    return relative


async def render_practice_characteristic(
    app: "Application",
    supervisor: str,
    topic: str,
    period_from: datetime,
    period_to: datetime,
) -> Path:
    context = {
        "full_name": app.user.full_name or "",
        "goal_title": app.goal.title,
        "supervisor": supervisor,
        "topic": topic,
        "period_from": period_from.strftime("%d.%m.%Y"),
        "period_to": period_to.strftime("%d.%m.%Y"),
        "date": datetime.now().strftime("%d.%m.%Y"),
    }
    absolute, relative = _get_output_path(app.user.id, app.id, "practice_characteristic")
    _render_template("practice_characteristic.docx", context, absolute)
    return relative
