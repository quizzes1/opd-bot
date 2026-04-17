from datetime import datetime
from pathlib import Path

from loguru import logger

from opdbot.config import settings

try:
    from docxtpl import DocxTemplate
    DOCXTPL_AVAILABLE = True
except ImportError:
    DOCXTPL_AVAILABLE = False
    logger.warning("docxtpl not installed — document generation disabled")


def _get_output_path(user_id: int, application_id: int, kind: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(settings.storage_root) / str(user_id) / str(application_id) / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{kind}_{ts}.docx"


def _render_template(template_name: str, context: dict, output_path: Path) -> Path:
    if not DOCXTPL_AVAILABLE:
        raise RuntimeError("docxtpl is not installed")

    template_path = Path(settings.templates_root) / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    doc = DocxTemplate(template_path)
    doc.render(context)
    doc.save(output_path)
    return output_path


async def render_application(app: object) -> Path:
    user = getattr(app, "user", None)
    goal = getattr(app, "goal", None)

    context = {
        "full_name": getattr(user, "full_name", "") or "",
        "phone": getattr(user, "phone", "") or "",
        "goal_title": getattr(goal, "title", "") if goal else "",
        "application_id": getattr(app, "id", ""),
        "date": datetime.now().strftime("%d.%m.%Y"),
    }

    output_path = _get_output_path(
        getattr(user, "id", 0) if user else 0,
        getattr(app, "id", 0),
        "application_form",
    )
    return _render_template("application.docx", context, output_path)


async def render_medical_referral(app: object) -> Path:
    user = getattr(app, "user", None)
    goal = getattr(app, "goal", None)

    context = {
        "full_name": getattr(user, "full_name", "") or "",
        "phone": getattr(user, "phone", "") or "",
        "goal_title": getattr(goal, "title", "") if goal else "",
        "application_id": getattr(app, "id", ""),
        "date": datetime.now().strftime("%d.%m.%Y"),
    }

    output_path = _get_output_path(
        getattr(user, "id", 0) if user else 0,
        getattr(app, "id", 0),
        "medical_referral",
    )
    return _render_template("medical_referral.docx", context, output_path)


async def render_practice_characteristic(
    app: object,
    supervisor: str,
    topic: str,
    period_from: datetime,
    period_to: datetime,
) -> Path:
    user = getattr(app, "user", None)
    goal = getattr(app, "goal", None)

    context = {
        "full_name": getattr(user, "full_name", "") or "",
        "goal_title": getattr(goal, "title", "") if goal else "",
        "supervisor": supervisor,
        "topic": topic,
        "period_from": period_from.strftime("%d.%m.%Y"),
        "period_to": period_to.strftime("%d.%m.%Y"),
        "date": datetime.now().strftime("%d.%m.%Y"),
    }

    output_path = _get_output_path(
        getattr(user, "id", 0) if user else 0,
        getattr(app, "id", 0),
        "practice_characteristic",
    )
    return _render_template("practice_characteristic.docx", context, output_path)
