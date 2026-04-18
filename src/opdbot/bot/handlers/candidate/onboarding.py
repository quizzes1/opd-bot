from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.goals import goals_keyboard
from opdbot.bot.keyboards.main_menu import candidate_main_menu, cancel_reply_keyboard
from opdbot.bot.states.candidate import OnboardingStates
from opdbot.db.models import Goal
from opdbot.db.repo.applications import create_application, get_active_application
from opdbot.db.repo.users import get_user_by_tg_id, update_user
from opdbot.utils.validators import validate_phone

router = Router(name="onboarding")


@router.message(OnboardingStates.waiting_full_name)
async def handle_full_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if len(text.split()) < 2:
        await message.answer("Пожалуйста, введите полное ФИО (минимум имя и фамилия).")
        return

    tg_user = message.from_user
    if tg_user is None:
        return
    user = await get_user_by_tg_id(session, tg_user.id)
    if user:
        await update_user(session, user, full_name=text)

    await state.update_data(full_name=text)
    await state.set_state(OnboardingStates.waiting_phone)
    await message.answer(texts.ASK_PHONE, reply_markup=cancel_reply_keyboard())


@router.message(OnboardingStates.waiting_phone)
async def handle_phone(message: Message, state: FSMContext, session: AsyncSession) -> None:
    phone = validate_phone(message.text or "")
    if phone is None:
        await message.answer("Неверный формат номера. Попробуйте ещё раз (например: +79001234567).")
        return

    tg_user = message.from_user
    if tg_user is None:
        return
    user = await get_user_by_tg_id(session, tg_user.id)
    if user:
        await update_user(session, user, phone=phone)

    result = await session.execute(select(Goal).where(Goal.is_active.is_(True)))
    goals = list(result.scalars().all())

    await state.set_state(OnboardingStates.waiting_goal)
    await message.answer(texts.ASK_GOAL, reply_markup=goals_keyboard(goals))


@router.callback_query(OnboardingStates.waiting_goal, F.data.startswith("goal:"))
async def handle_goal_selected(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    goal_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]

    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("Пользователь не найден.")
        return

    existing = await get_active_application(session, user.id)
    if existing is not None:
        await state.clear()
        await callback.message.edit_text(  # type: ignore[union-attr]
            texts.ACTIVE_APPLICATION_EXISTS.format(app_id=existing.id),
        )
        await callback.message.answer(texts.MAIN_MENU, reply_markup=candidate_main_menu(True))  # type: ignore[union-attr]
        await callback.answer()
        return

    result = await session.execute(select(Goal).where(Goal.id == goal_id))
    goal = result.scalar_one_or_none()
    if not goal:
        await callback.answer("Цель не найдена.")
        return

    application = await create_application(session, user_id=user.id, goal_id=goal_id)

    await state.clear()
    await state.update_data(application_id=application.id)

    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.GOAL_SELECTED.format(goal=goal.title),
        parse_mode="HTML",
    )
    await callback.message.answer(texts.MAIN_MENU, reply_markup=candidate_main_menu(True))  # type: ignore[union-attr]
    await callback.answer()
