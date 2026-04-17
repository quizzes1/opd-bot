from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.bot import texts
from opdbot.bot.keyboards.main_menu import candidate_main_menu, hr_main_menu
from opdbot.bot.states.candidate import OnboardingStates
from opdbot.config import settings
from opdbot.db.models import UserRole
from opdbot.db.repo.applications import get_active_application
from opdbot.db.repo.users import get_or_create_user, set_user_role

router = Router(name="common")


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, role: UserRole) -> None:
    await state.clear()
    tg_user = message.from_user
    if tg_user is None:
        return

    user, created = await get_or_create_user(
        session,
        tg_id=tg_user.id,
        tg_username=tg_user.username,
        full_name=tg_user.full_name,
    )

    if tg_user.id in settings.superadmin_tg_ids and user.role != UserRole.admin:
        user.role = UserRole.admin
        await session.flush()
        role = UserRole.admin

    if role in (UserRole.hr, UserRole.admin):
        await message.answer(texts.HR_WELCOME, reply_markup=hr_main_menu())
        return

    if user.full_name and user.phone:
        has_active = await get_active_application(session, user.id) is not None
        await message.answer(
            texts.MAIN_MENU, reply_markup=candidate_main_menu(has_active)
        )
        return

    if not user.full_name:
        await state.set_state(OnboardingStates.waiting_full_name)
        await message.answer(texts.WELCOME)
    else:
        await state.set_state(OnboardingStates.waiting_phone)
        await message.answer(texts.ASK_PHONE)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP_TEXT)


@router.message(Command("cancel"))
async def cmd_cancel(
    message: Message, state: FSMContext, session: AsyncSession, role: UserRole
) -> None:
    await state.clear()
    if role in (UserRole.hr, UserRole.admin):
        kb = hr_main_menu()
    else:
        tg_user = message.from_user
        has_active = False
        if tg_user is not None:
            user, _ = await get_or_create_user(
                session,
                tg_id=tg_user.id,
                tg_username=tg_user.username,
                full_name=tg_user.full_name,
            )
            has_active = await get_active_application(session, user.id) is not None
        kb = candidate_main_menu(has_active)
    await message.answer(texts.CANCELLED, reply_markup=kb)


@router.message(Command("grant_hr"))
async def cmd_grant_hr(message: Message, session: AsyncSession) -> None:
    tg_user = message.from_user
    if tg_user is None or tg_user.id not in settings.superadmin_tg_ids:
        await message.answer(texts.HR_GRANT_FORBIDDEN)
        return

    args = message.text.split() if message.text else []
    if len(args) < 2:
        await message.answer(texts.HR_GRANT_USAGE)
        return

    try:
        target_tg_id = int(args[1])
    except ValueError:
        await message.answer(texts.HR_GRANT_USAGE)
        return

    user = await set_user_role(session, target_tg_id, UserRole.hr)
    if user:
        await message.answer(texts.HR_GRANT_SUCCESS.format(tg_id=target_tg_id))
    else:
        await message.answer(texts.HR_GRANT_NOT_FOUND.format(tg_id=target_tg_id))
