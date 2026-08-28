from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import date, datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from .ai_chat_service import AIChatError, AIChatService
from .config import Settings, load_settings
from .content import diary_reminder, garden_tip, horoscope, horoscope_title, morning_digest
from .dacha6_service import Dacha6Service
from .formatting import format_entries, format_entries_export, format_saved_entry, month_title, parse_month_button
from .horoscope_service import HoroscopeService
from .lunar_service import LunarService
from .keyboards import (
    BTN_AI_CHAT,
    BTN_AI_EXIT,
    BTN_AI_NEW_CHAT,
    BTN_BACK,
    BTN_CALENDAR,
    BTN_CANCEL,
    BTN_DACHA,
    BTN_DIARY,
    BTN_DOWNLOAD,
    BTN_FIND,
    BTN_HOROSCOPE,
    BTN_PHOTO,
    BTN_RECORDS,
    BTN_SOWING_DAYS,
    BTN_SKIP_CAPTION,
    BTN_PROMPT_RETRY,
    BTN_PROMPT_SAVE,
    BTN_TEST,
    BTN_TEST_DIGEST,
    BTN_TEST_DIARY_REMINDER,
    BTN_TEST_PROMPT,
    BTN_TEST_WEEKLY_REVIEW,
    BTN_TODAY_TIP,
    BTN_WRITE,
    CALLBACK_OPEN_DIARY,
    ai_chat_menu,
    cancel_menu,
    dacha_months_menu,
    dacha_menu,
    diary_menu,
    diary_reminder_actions,
    main_menu,
    photo_caption_menu,
    records_months_menu,
    test_menu,
    weekly_prompt_review_menu,
)
from .scheduler import backup_loop, diary_reminder_loop, digest_loop, weekly_review_loop
from .storage import Storage
from .weekly_review_service import (
    WeeklyReviewError,
    WeeklyReviewService,
    current_prompt_text,
    current_week_period,
    empty_weekly_review_text,
    save_custom_prompt,
)

logger = logging.getLogger(__name__)
router = Router()


class DiaryStates(StatesGroup):
    waiting_entry_text = State()
    waiting_search_query = State()
    waiting_photo = State()
    waiting_photo_caption = State()
    waiting_import_entry_text = State()
    waiting_weekly_prompt_instruction = State()
    waiting_weekly_prompt_confirmation = State()
    chatting_with_ai = State()


def _is_allowed(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and message.from_user.id in settings.allowed_user_ids)


def _is_admin(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and message.from_user.id in settings.admin_user_ids)


def _now(settings: Settings) -> datetime:
    return datetime.now(settings.timezone)


def _parse_prefixed_month_button(text: str, prefix: str) -> tuple[int, int] | None:
    expected_prefix = f"{prefix}: "
    if not text.startswith(expected_prefix):
        return None
    return parse_month_button(text.removeprefix(expected_prefix))


def parse_import_entry_command(text: str, timezone) -> tuple[datetime, str] | None:
    parts = text.strip().split(maxsplit=3)
    if len(parts) < 3:
        return None
    created_at = _parse_import_datetime(parts[1], parts[2], timezone)
    if created_at is None:
        return None
    entry_text = parts[3].strip() if len(parts) == 4 else ""
    return created_at, entry_text


def _parse_import_datetime(date_text: str, time_text: str, timezone) -> datetime | None:
    for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(f"{date_text} {time_text}", f"{date_format} %H:%M").replace(tzinfo=timezone)
        except ValueError:
            continue
    return None


async def _deny_if_needed(message: Message, settings: Settings) -> bool:
    if _is_allowed(message, settings):
        return False
    await message.answer("Извините, этот бот семейный и закрытый.")
    return True


async def _show_main(message: Message, settings: Settings, text: str = "Главное меню") -> None:
    await message.answer(text, reply_markup=main_menu(_is_admin(message, settings)))


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    await state.clear()
    await _show_main(
        message,
        settings,
        "Добро пожаловать. Данные дневника не очищаются: /start только показывает меню.",
    )


@router.message(F.text == BTN_DACHA)
async def dacha(message: Message, state: FSMContext, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    await state.clear()
    await message.answer("Раздел “Дача”", reply_markup=dacha_menu())


@router.message(F.text == BTN_DIARY)
async def diary(message: Message, state: FSMContext, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    await state.clear()
    await message.answer(
        "Дневник дел: можно записывать дачу, дом, гараж, ремонт и любые проекты.",
        reply_markup=diary_menu(),
    )


@router.message(F.text == BTN_BACK)
async def back(message: Message, state: FSMContext, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    await state.clear()
    await _show_main(message, settings)


@router.message(F.text == BTN_CANCEL)
async def cancel(message: Message, state: FSMContext, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    await state.clear()
    await message.answer("Отменено.", reply_markup=diary_menu())


@router.message(F.text == BTN_CALENDAR)
async def calendar(
    message: Message,
    settings: Settings,
    lunar_service: LunarService,
    dacha6_service: Dacha6Service,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    await message.answer("Выберите месяц.", reply_markup=dacha_months_menu(BTN_CALENDAR, _now(settings).date()))


@router.message(F.text.regexp(r"^Календарь: (Май|Июнь|Июль|Август|Сентябрь|Октябрь|Ноябрь|Декабрь) 2026$"))
async def calendar_month(
    message: Message,
    settings: Settings,
    lunar_service: LunarService,
    dacha6_service: Dacha6Service,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    assert message.text is not None
    parsed = _parse_prefixed_month_button(message.text, BTN_CALENDAR)
    if parsed is None:
        await message.answer("Не понял месяц.", reply_markup=dacha_menu())
        return
    year, month = parsed
    await message.answer(
        await dacha6_service.month_text(date(year, month, 1)),
        reply_markup=dacha_menu(),
    )


@router.message(F.text == BTN_TODAY_TIP)
async def today_tip(message: Message, settings: Settings, dacha6_service: Dacha6Service) -> None:
    if await _deny_if_needed(message, settings):
        return
    await message.answer(
        await dacha6_service.garden_text(_now(settings).date(), include_folk_signs=False),
        reply_markup=dacha_menu(),
    )


@router.message(F.text == BTN_SOWING_DAYS)
async def sowing_days(message: Message, settings: Settings, dacha6_service: Dacha6Service) -> None:
    if await _deny_if_needed(message, settings):
        return
    await message.answer("Выберите месяц.", reply_markup=dacha_months_menu(BTN_SOWING_DAYS, _now(settings).date()))


@router.message(F.text.regexp(r"^Дни для посева: (Май|Июнь|Июль|Август|Сентябрь|Октябрь|Ноябрь|Декабрь) 2026$"))
async def sowing_days_month(message: Message, settings: Settings, dacha6_service: Dacha6Service) -> None:
    if await _deny_if_needed(message, settings):
        return
    assert message.text is not None
    parsed = _parse_prefixed_month_button(message.text, BTN_SOWING_DAYS)
    if parsed is None:
        await message.answer("Не понял месяц.", reply_markup=dacha_menu())
        return
    year, month = parsed
    await message.answer(
        await dacha6_service.sowing_days_text(date(year, month, 1)),
        reply_markup=dacha_menu(),
    )


@router.message(F.text == BTN_HOROSCOPE)
async def horoscope_handler(
    message: Message,
    settings: Settings,
    horoscope_service: HoroscopeService,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    result = await horoscope_service.get_daily(_now(settings).date())
    today = _now(settings).date()
    await message.answer(
        f"✨ {horoscope_title(today, settings.horoscope_sign)}\n{result.text}",
        reply_markup=main_menu(_is_admin(message, settings)),
    )


@router.message(F.text == BTN_AI_CHAT)
async def ai_chat_start(
    message: Message,
    state: FSMContext,
    storage: Storage,
    settings: Settings,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    if not settings.amvera_api_token:
        await message.answer(
            "ИИ пока не подключён. Проверьте секрет AMVERA_API_TOKEN в Amvera.",
            reply_markup=main_menu(_is_admin(message, settings)),
        )
        return
    assert message.from_user is not None
    storage.get_or_start_ai_conversation(message.from_user.id, _now(settings))
    await state.set_state(DiaryStates.chatting_with_ai)
    await message.answer(
        "🤖 Задайте вопрос. Я помню предыдущие сообщения этого разговора.",
        reply_markup=ai_chat_menu(),
    )


@router.message(DiaryStates.chatting_with_ai, F.text == BTN_AI_NEW_CHAT)
async def ai_chat_new(
    message: Message,
    state: FSMContext,
    storage: Storage,
    settings: Settings,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    assert message.from_user is not None
    storage.start_ai_conversation(message.from_user.id, _now(settings))
    await state.set_state(DiaryStates.chatting_with_ai)
    await message.answer("Начали новый разговор. О чём хотите спросить?", reply_markup=ai_chat_menu())


@router.message(DiaryStates.chatting_with_ai, F.text == BTN_AI_EXIT)
async def ai_chat_exit(message: Message, state: FSMContext, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    await state.clear()
    await _show_main(message, settings, "Вышли из разговора с ИИ. История сохранена.")


@router.message(DiaryStates.chatting_with_ai, F.text)
async def ai_chat_question(
    message: Message,
    storage: Storage,
    settings: Settings,
    ai_chat_service: AIChatService,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    assert message.from_user is not None
    assert message.text is not None
    user_id = message.from_user.id
    conversation_id = storage.get_or_start_ai_conversation(user_id, _now(settings))
    history = storage.ai_chat_messages(conversation_id)
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        answer = await ai_chat_service.answer(history, message.text)
    except AIChatError:
        logger.exception("Failed to answer AI chat question for user %s", user_id)
        await message.answer(
            "Не получилось получить ответ от ИИ. Попробуйте ещё раз немного позже.",
            reply_markup=ai_chat_menu(),
        )
        return

    now = _now(settings)
    storage.add_ai_chat_message(conversation_id, user_id, "user", message.text, now)
    storage.add_ai_chat_message(conversation_id, user_id, "assistant", answer, now)
    await message.answer(answer, reply_markup=ai_chat_menu())


@router.message(F.text == BTN_TEST)
async def test_menu_handler(message: Message, state: FSMContext, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    if not _is_admin(message, settings):
        await message.answer("Тесты доступны только дочери.")
        return
    await state.clear()
    await message.answer("Что протестировать?", reply_markup=test_menu())


@router.message(F.text == BTN_TEST_DIGEST)
async def test_digest_handler(
    message: Message,
    settings: Settings,
    horoscope_service: HoroscopeService,
    lunar_service: LunarService,
    dacha6_service: Dacha6Service,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    if not _is_admin(message, settings):
        await message.answer("Тесты доступны только дочери.")
        return
    horoscope_result = await horoscope_service.get_daily(_now(settings).date())
    await message.answer(
        morning_digest(
            _now(settings).date(),
            horoscope_result.text,
            settings.horoscope_sign,
            settings.recipient_name,
            await dacha6_service.garden_text(_now(settings).date()),
        ),
        reply_markup=test_menu(),
    )


@router.message(F.text == BTN_TEST_DIARY_REMINDER)
async def test_diary_reminder_handler(message: Message, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    if not _is_admin(message, settings):
        await message.answer("Тесты доступны только дочери.")
        return
    await message.answer(diary_reminder(), reply_markup=diary_reminder_actions())


@router.message(F.text == BTN_TEST_WEEKLY_REVIEW)
async def test_weekly_review_handler(
    message: Message,
    settings: Settings,
    storage: Storage,
    weekly_review_service: WeeklyReviewService,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    if not _is_admin(message, settings):
        await message.answer("Тесты доступны только дочери.")
        return

    period_start, period_end = current_week_period(_now(settings))
    entries = storage.entries_between(period_start, period_end)
    if not entries:
        await message.answer(
            empty_weekly_review_text(period_start, period_end),
            reply_markup=test_menu(),
        )
        return
    if not settings.amvera_api_token:
        await message.answer(
            "Weekly review пока не подключён: добавьте секрет AMVERA_API_TOKEN в настройках Amvera.",
            reply_markup=test_menu(),
        )
        return

    await message.answer("Готовлю тестовые итоги недели…")
    try:
        text = await weekly_review_service.generate(
            entries, period_start, period_end, system_prompt=current_prompt_text(storage)
        )
    except WeeklyReviewError:
        logger.exception("Failed to generate test weekly review")
        await message.answer(
            "Не получилось получить ответ от Amvera LLM. Проверьте токен, модель и логи.",
            reply_markup=test_menu(),
        )
        return
    await message.answer(text, reply_markup=test_menu())


@router.message(F.text == BTN_TEST_PROMPT)
async def weekly_prompt_start(
    message: Message,
    state: FSMContext,
    storage: Storage,
    settings: Settings,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    if not _is_admin(message, settings):
        await message.answer("Тесты доступны только дочери.")
        return
    current = current_prompt_text(storage)
    await state.set_state(DiaryStates.waiting_weekly_prompt_instruction)
    await state.update_data(weekly_prompt_base=current)
    await message.answer(
        "Текущий промт для итогов недели:\n\n" + current
        + "\n\nНапишите, что изменить (например: «сделай короче» или «добавь больше тепла»).",
        reply_markup=cancel_menu(),
    )


@router.message(DiaryStates.waiting_weekly_prompt_instruction, F.text)
async def weekly_prompt_revise(
    message: Message,
    state: FSMContext,
    storage: Storage,
    settings: Settings,
    weekly_review_service: WeeklyReviewService,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    if not _is_admin(message, settings):
        await state.clear()
        await message.answer("Тесты доступны только дочери.", reply_markup=test_menu())
        return
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=test_menu())
        return

    data = await state.get_data()
    base_prompt = str(data.get("weekly_prompt_base") or current_prompt_text(storage))
    await message.answer("Переписываю промт…")
    try:
        draft = await weekly_review_service.revise_prompt(base_prompt, message.text or "")
    except WeeklyReviewError:
        logger.exception("Failed to revise weekly review prompt")
        await state.clear()
        await message.answer(
            "Не получилось получить ответ от Amvera LLM. Проверьте токен, модель и логи.",
            reply_markup=test_menu(),
        )
        return

    await state.set_state(DiaryStates.waiting_weekly_prompt_confirmation)
    await state.update_data(weekly_prompt_draft=draft)
    await message.answer(
        "Черновик нового промта:\n\n" + draft,
        reply_markup=weekly_prompt_review_menu(),
    )


@router.message(DiaryStates.waiting_weekly_prompt_confirmation, F.text == BTN_PROMPT_SAVE)
async def weekly_prompt_save(
    message: Message,
    state: FSMContext,
    storage: Storage,
    settings: Settings,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    if not _is_admin(message, settings):
        await state.clear()
        await message.answer("Тесты доступны только дочери.", reply_markup=test_menu())
        return
    data = await state.get_data()
    draft = str(data.get("weekly_prompt_draft") or "")
    if not draft:
        await state.clear()
        await message.answer("Не нашёл черновик, начните заново.", reply_markup=test_menu())
        return
    save_custom_prompt(storage, draft, _now(settings))
    await state.clear()
    await message.answer(
        "Сохранено. Новый промт будет использоваться и в тестовых, и в настоящих воскресных итогах недели.",
        reply_markup=test_menu(),
    )


@router.message(DiaryStates.waiting_weekly_prompt_confirmation, F.text == BTN_PROMPT_RETRY)
async def weekly_prompt_retry(message: Message, state: FSMContext, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    if not _is_admin(message, settings):
        await state.clear()
        await message.answer("Тесты доступны только дочери.", reply_markup=test_menu())
        return
    data = await state.get_data()
    draft = str(data.get("weekly_prompt_draft") or "")
    await state.set_state(DiaryStates.waiting_weekly_prompt_instruction)
    await state.update_data(weekly_prompt_base=draft)
    await message.answer("Что ещё поправить в промте?", reply_markup=cancel_menu())


@router.message(DiaryStates.waiting_weekly_prompt_confirmation, F.text == BTN_CANCEL)
async def weekly_prompt_cancel(message: Message, state: FSMContext, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    await state.clear()
    await message.answer("Отменено.", reply_markup=test_menu())


@router.callback_query(F.data == CALLBACK_OPEN_DIARY)
async def open_diary_from_reminder(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
) -> None:
    if callback.from_user.id not in settings.allowed_user_ids:
        await callback.answer("Этот бот семейный и закрытый.", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Дневник дел: можно записывать дачу, дом, гараж, ремонт и любые проекты.",
            reply_markup=diary_menu(),
        )


@router.message(Command("import_entry"))
async def import_entry_command(message: Message, state: FSMContext, storage: Storage, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    if not _is_admin(message, settings):
        await message.answer("Импорт старых записей доступен только дочери.")
        return
    parsed = parse_import_entry_command(message.text or "", settings.timezone)
    if parsed is None:
        await message.answer(
            "Формат:\n/import_entry 2026-06-03 14:30 текст записи\n"
            "или:\n/import_entry 03.06.2026 14:30 текст записи\n\n"
            "Можно без текста: /import_entry 03.06.2026 14:30, а запись отправить следующим сообщением.",
            reply_markup=diary_menu(),
        )
        return

    created_at, entry_text = parsed
    if entry_text:
        assert message.from_user is not None
        entry = storage.add_entry(message.from_user.id, entry_text, created_at)
        await state.clear()
        await message.answer("Импортировал старую запись.\n\n" + format_saved_entry(entry), reply_markup=diary_menu())
        return

    await state.set_state(DiaryStates.waiting_import_entry_text)
    await state.update_data(import_created_at=created_at.isoformat())
    await message.answer(
        f"Дата для старой записи: {created_at:%d.%m.%Y %H:%M}\nТеперь отправьте текст записи.",
        reply_markup=cancel_menu(),
    )


@router.message(DiaryStates.waiting_import_entry_text, F.text)
async def save_imported_entry_text(
    message: Message,
    state: FSMContext,
    storage: Storage,
    settings: Settings,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    if not _is_admin(message, settings):
        await state.clear()
        await message.answer("Импорт старых записей доступен только дочери.", reply_markup=diary_menu())
        return
    text = message.text or ""
    if text == BTN_CANCEL:
        await cancel(message, state, settings)
        return
    data = await state.get_data()
    created_at = datetime.fromisoformat(str(data["import_created_at"]))
    assert message.from_user is not None
    entry = storage.add_entry(message.from_user.id, text, created_at)
    await state.clear()
    await message.answer("Импортировал старую запись.\n\n" + format_saved_entry(entry), reply_markup=diary_menu())


@router.message(F.text == BTN_WRITE)
async def write_entry(message: Message, state: FSMContext, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    await state.set_state(DiaryStates.waiting_entry_text)
    await message.answer("Что записать?", reply_markup=cancel_menu())


@router.message(DiaryStates.waiting_entry_text, F.text)
async def save_entry_text(message: Message, state: FSMContext, storage: Storage, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    assert message.from_user is not None
    text = message.text or ""
    if text == BTN_CANCEL:
        await cancel(message, state, settings)
        return
    entry = storage.add_entry(message.from_user.id, text, _now(settings))
    await state.clear()
    await message.answer(
        format_saved_entry(entry),
        reply_markup=diary_menu(),
    )


@router.message(F.text == BTN_FIND)
async def find_entry(message: Message, state: FSMContext, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    await state.set_state(DiaryStates.waiting_search_query)
    await message.answer("Что ищем среди записей?", reply_markup=cancel_menu())


@router.message(DiaryStates.waiting_search_query, F.text)
async def search_entries(message: Message, state: FSMContext, storage: Storage, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    query = message.text or ""
    if query == BTN_CANCEL:
        await cancel(message, state, settings)
        return
    entries = storage.search_entries(query)
    await state.clear()
    await message.answer(
        format_entries(entries, f"По запросу “{query}” ничего не нашлось."),
        reply_markup=diary_menu(),
    )


@router.message(F.text == BTN_RECORDS)
async def records(message: Message, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    await message.answer("Выберите месяц.", reply_markup=records_months_menu(_now(settings).date()))


@router.message(F.text == BTN_DOWNLOAD)
async def download_entries(message: Message, storage: Storage, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    exports_dir = settings.data_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    export_path = exports_dir / f"diary_{_now(settings):%Y%m%d_%H%M%S}.txt"
    export_path.write_text(format_entries_export(storage.all_entries()), encoding="utf-8")
    await message.answer_document(
        FSInputFile(export_path, filename="diary.txt"),
        caption="Выгрузка дневника.",
        reply_markup=diary_menu(),
    )


@router.message(F.text.regexp(r"^(Май|Июнь|Июль|Август|Сентябрь|Октябрь|Ноябрь|Декабрь) 2026$"))
async def records_month(message: Message, storage: Storage, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    assert message.text is not None
    parsed = parse_month_button(message.text)
    if parsed is None:
        await message.answer("Не понял месяц.", reply_markup=diary_menu())
        return
    year, month = parsed
    entries = storage.entries_for_month(year, month)
    await message.answer(
        format_entries(entries, f"За {month_title(year, month).lower()} записей пока нет."),
        reply_markup=records_months_menu(_now(settings).date()),
    )


@router.message(F.text == BTN_PHOTO)
async def photo_prompt(message: Message, state: FSMContext, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    await state.set_state(DiaryStates.waiting_photo)
    await message.answer("Пришлите фото для дневника.", reply_markup=cancel_menu())


@router.message(DiaryStates.waiting_photo, F.photo)
async def photo_from_prompt(message: Message, state: FSMContext, bot: Bot, storage: Storage, settings: Settings) -> None:
    await _prepare_photo_caption(message, state, bot, storage, settings)


@router.message(F.photo)
async def photo_anytime(message: Message, state: FSMContext, bot: Bot, storage: Storage, settings: Settings) -> None:
    await _prepare_photo_caption(message, state, bot, storage, settings)


async def _prepare_photo_caption(
    message: Message,
    state: FSMContext,
    bot: Bot,
    storage: Storage,
    settings: Settings,
) -> None:
    if await _deny_if_needed(message, settings):
        return
    assert message.photo is not None
    file_id = message.photo[-1].file_id
    local_path = await _download_photo(bot, storage, file_id)
    caption = (message.caption or "").strip()
    if caption:
        assert message.from_user is not None
        storage.add_entry(
            message.from_user.id,
            caption,
            _now(settings),
            photo_file_id=file_id,
            photo_local_path=str(local_path) if local_path else None,
        )
        await state.clear()
        await message.answer("Фото сохранил в дневник.", reply_markup=diary_menu())
        return

    await state.set_state(DiaryStates.waiting_photo_caption)
    await state.update_data(photo_file_id=file_id, photo_local_path=str(local_path) if local_path else None)
    await message.answer("Фото получил. Добавить подпись?", reply_markup=photo_caption_menu())


@router.message(DiaryStates.waiting_photo_caption, F.text)
async def save_photo_caption(message: Message, state: FSMContext, storage: Storage, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    text = message.text or ""
    if text == BTN_CANCEL:
        await state.clear()
        await message.answer("Фото не сохранил.", reply_markup=diary_menu())
        return
    data = await state.get_data()
    caption = "" if text == BTN_SKIP_CAPTION else text
    assert message.from_user is not None
    storage.add_entry(
        message.from_user.id,
        caption,
        _now(settings),
        photo_file_id=data.get("photo_file_id"),
        photo_local_path=data.get("photo_local_path"),
    )
    await state.clear()
    await message.answer("Фото сохранил в дневник.", reply_markup=diary_menu())


async def _download_photo(bot: Bot, storage: Storage, file_id: str) -> Path | None:
    try:
        storage.photos_dir.mkdir(parents=True, exist_ok=True)
        safe_name = hashlib.sha256(file_id.encode("utf-8")).hexdigest()
        target = storage.photos_dir / f"{safe_name}.jpg"
        await bot.download(file_id, destination=target)
        return target
    except Exception:
        logger.exception("Failed to download photo %s", file_id)
        return None


@router.message()
async def fallback(message: Message, settings: Settings) -> None:
    if await _deny_if_needed(message, settings):
        return
    await message.answer(
        "Выберите кнопку в меню. Чтобы сохранить дело, откройте Дневник -> Записать.",
        reply_markup=main_menu(_is_admin(message, settings)),
    )


async def run_bot() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    storage = Storage(settings.database_path, settings.photos_dir, settings.backups_dir)
    storage.init()
    logger.info("Data directory: %s", settings.data_dir)
    logger.info(
        "Database path: %s; diary entries: %s",
        settings.database_path,
        len(storage.all_entries()),
    )
    horoscope_service = HoroscopeService(storage, settings)
    lunar_service = LunarService(settings)
    dacha6_service = Dacha6Service(settings, lunar_service, storage)
    weekly_review_service = WeeklyReviewService(settings)
    ai_chat_service = AIChatService(settings)
    logger.info(
        "Weekly review: %s; weekday=%s; time=%02d:%02d; model=%s",
        "enabled" if settings.weekly_review_enabled else "disabled",
        settings.weekly_review_weekday,
        settings.weekly_review_hour,
        settings.weekly_review_minute,
        settings.amvera_llm_model,
    )
    if settings.weekly_review_enabled and not settings.amvera_api_token:
        logger.warning("Weekly review is enabled, but AMVERA_API_TOKEN is empty")

    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    dp["settings"] = settings
    dp["storage"] = storage
    dp["horoscope_service"] = horoscope_service
    dp["lunar_service"] = lunar_service
    dp["dacha6_service"] = dacha6_service
    dp["weekly_review_service"] = weekly_review_service
    dp["ai_chat_service"] = ai_chat_service

    asyncio.create_task(digest_loop(bot, storage, settings, horoscope_service, lunar_service, dacha6_service))
    asyncio.create_task(diary_reminder_loop(bot, storage, settings))
    asyncio.create_task(weekly_review_loop(bot, storage, settings, weekly_review_service))
    asyncio.create_task(backup_loop(storage, settings))

    logger.info("HelperBot started")
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(run_bot())
