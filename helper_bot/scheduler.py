from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot

from .config import Settings
from .content import morning_digest
from .dacha6_service import Dacha6Service
from .horoscope_service import HoroscopeService
from .keyboards import main_menu
from .lunar_service import LunarService
from .storage import Storage

logger = logging.getLogger(__name__)


async def digest_loop(
    bot: Bot,
    storage: Storage,
    settings: Settings,
    horoscope_service: HoroscopeService,
    lunar_service: LunarService,
    dacha6_service: Dacha6Service,
) -> None:
    while True:
        now = datetime.now(settings.timezone)
        if now.hour == settings.digest_hour and now.minute == settings.digest_minute:
            await send_daily_digest(
                bot,
                storage,
                settings,
                horoscope_service,
                lunar_service,
                dacha6_service,
                now,
            )
            await asyncio.sleep(65)
        await asyncio.sleep(20)


async def backup_loop(storage: Storage, settings: Settings) -> None:
    while True:
        now = datetime.now(settings.timezone)
        if now.hour == 2 and now.minute == 15:
            try:
                backup_path = storage.backup(now)
                logger.info("Created backup: %s", backup_path)
            except Exception:
                logger.exception("Failed to create backup")
            await asyncio.sleep(65)
        await asyncio.sleep(30)


async def send_daily_digest(
    bot: Bot,
    storage: Storage,
    settings: Settings,
    horoscope_service: HoroscopeService,
    lunar_service: LunarService,
    dacha6_service: Dacha6Service,
    now: datetime,
) -> None:
    today = now.date()
    horoscope = await horoscope_service.get_daily(today)
    text = morning_digest(
        today,
        horoscope.text,
        settings.horoscope_sign,
        settings.recipient_name,
        lunar_service.daily_text(today),
        await dacha6_service.garden_text(today),
    )

    for user_id in settings.allowed_user_ids:
        if storage.was_digest_sent(today, user_id):
            continue
        try:
            await bot.send_message(
                user_id,
                text,
                reply_markup=main_menu(user_id in settings.admin_user_ids),
            )
            storage.mark_digest_sent(today, user_id, now)
        except Exception:
            logger.exception("Failed to send digest to %s", user_id)
