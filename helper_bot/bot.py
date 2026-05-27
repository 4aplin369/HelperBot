from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message

from .config import Settings, load_settings
from .content import garden_tip, horoscope, horoscope_title, morning_digest
from .dacha6_service import Dacha6Service
from .formatting import format_entries, format_entries_export, month_title, parse_month_button
from .horoscope_service import HoroscopeService
from .lunar_service import LunarService
from .keyboards import (
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
    BTN_TEST_DIGEST,
    BTN_TODAY_TIP,
    BTN_WRITE,
    cancel_menu,
    dacha_menu,
    diary_menu,
    main_menu,
    photo_caption_menu,
    records_months_menu,
)
from .scheduler import backup_loop, digest_loop
from .storage import Storage

logger = logging.getLogger(__name__)
router = Router()


class DiaryStates(StatesGroup):
    waiting_entry_text = State()
    waiting_search_query = State()
    waiting_photo = State()
    waiting_photo_caption = State()


def _is_allowed(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and message.from_user.id in settings.allowed_user_ids)


def _is_admin(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and message.from_user.id in settings.admin_user_ids)


def _now(settings: Settings) -> datetime:
    return datetime.now(settings.timezone)


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
    today = _now(settings).date()
    await message.answer(
        await dacha6_service.month_text(today),
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
    await message.answer(
        await dacha6_service.sowing_days_text(),
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
        await message.answer("Тест дайджеста доступен только дочери.")
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
        reply_markup=main_menu(True),
    )


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
        f"Записал:\n{entry.created_at:%d.%m.%Y %H:%M}\n{entry.text}",
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
    horoscope_service = HoroscopeService(storage, settings)
    lunar_service = LunarService(settings)
    dacha6_service = Dacha6Service(settings, lunar_service)

    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    dp["settings"] = settings
    dp["storage"] = storage
    dp["horoscope_service"] = horoscope_service
    dp["lunar_service"] = lunar_service
    dp["dacha6_service"] = dacha6_service

    asyncio.create_task(digest_loop(bot, storage, settings, horoscope_service, lunar_service, dacha6_service))
    asyncio.create_task(backup_loop(storage, settings))

    logger.info("HelperBot started")
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(run_bot())
