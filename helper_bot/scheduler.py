from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot

from .config import Settings
from .content import diary_reminder, morning_digest
from .dacha6_service import Dacha6Service
from .horoscope_service import HoroscopeService
from .keyboards import diary_reminder_actions, main_menu
from .lunar_service import LunarService
from .storage import Storage
from .weekly_review_service import (
    WeeklyReviewError,
    WeeklyReviewService,
    current_week_period,
    empty_weekly_review_text,
)

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


async def diary_reminder_loop(bot: Bot, storage: Storage, settings: Settings) -> None:
    while True:
        now = datetime.now(settings.timezone)
        if (
            now.hour == settings.diary_reminder_hour
            and now.minute == settings.diary_reminder_minute
        ):
            await send_diary_reminders(bot, storage, settings, now)
            await asyncio.sleep(65)
        await asyncio.sleep(20)


async def weekly_review_loop(
    bot: Bot,
    storage: Storage,
    settings: Settings,
    weekly_review_service: WeeklyReviewService,
) -> None:
    while True:
        if not settings.weekly_review_enabled:
            await asyncio.sleep(60)
            continue
        now = datetime.now(settings.timezone)
        if (
            now.weekday() == settings.weekly_review_weekday
            and now.hour == settings.weekly_review_hour
            and now.minute == settings.weekly_review_minute
        ):
            await send_weekly_reviews(bot, storage, settings, weekly_review_service, now)
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


async def send_diary_reminders(
    bot: Bot,
    storage: Storage,
    settings: Settings,
    now: datetime,
) -> None:
    today = now.date()
    for user_id in settings.allowed_user_ids:
        if storage.was_diary_reminder_sent(today, user_id):
            continue
        text = diary_reminder(storage.last_diary_reminder_text(user_id))
        try:
            await bot.send_message(
                user_id,
                text,
                reply_markup=diary_reminder_actions(),
            )
            storage.mark_diary_reminder_sent(today, user_id, text, now)
        except Exception:
            logger.exception("Failed to send diary reminder to %s", user_id)


async def send_weekly_reviews(
    bot: Bot,
    storage: Storage,
    settings: Settings,
    weekly_review_service: WeeklyReviewService,
    now: datetime,
) -> None:
    period_start, period_end = current_week_period(now)
    week_start = period_start.date()
    text = storage.get_weekly_review(week_start)
    if text is None:
        entries = storage.entries_between(period_start, period_end)
        if entries:
            try:
                text = await weekly_review_service.generate(entries, period_start, period_end)
            except WeeklyReviewError:
                logger.exception("Failed to prepare weekly review for %s", week_start)
                return
        else:
            text = empty_weekly_review_text(period_start, period_end)
        storage.save_weekly_review(week_start, period_end, text, now)

    for user_id in settings.allowed_user_ids:
        if storage.was_weekly_review_sent(week_start, user_id):
            continue
        try:
            await bot.send_message(
                user_id,
                text,
                reply_markup=main_menu(user_id in settings.admin_user_ids),
            )
            storage.mark_weekly_review_sent(week_start, user_id, now)
        except Exception:
            logger.exception("Failed to send weekly review to %s", user_id)
