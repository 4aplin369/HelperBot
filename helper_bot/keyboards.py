from __future__ import annotations

from datetime import date

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from .content import MONTHS_RU


BTN_DACHA = "Дача"
BTN_DIARY = "Дневник"
BTN_HOROSCOPE = "Гороскоп"
BTN_TEST_DIGEST = "Тест дайджеста"
BTN_CALENDAR = "Календарь"
BTN_SOWING_DAYS = "Дни для посева"
BTN_TODAY_TIP = "Что сделать?"
BTN_WRITE = "Записать"
BTN_FIND = "Найти"
BTN_PHOTO = "Фото"
BTN_RECORDS = "Записи"
BTN_BACK = "Назад"
BTN_CANCEL = "Отмена"
BTN_SKIP_CAPTION = "Без подписи"


def _keyboard(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in rows],
        resize_keyboard=True,
        input_field_placeholder="Выберите кнопку или напишите сообщение",
    )


def main_menu(is_admin: bool) -> ReplyKeyboardMarkup:
    rows = [[BTN_DACHA, BTN_DIARY], [BTN_HOROSCOPE]]
    if is_admin:
        rows.append([BTN_TEST_DIGEST])
    return _keyboard(rows)


def dacha_menu() -> ReplyKeyboardMarkup:
    return _keyboard([[BTN_CALENDAR, BTN_TODAY_TIP], [BTN_SOWING_DAYS], [BTN_BACK]])


def diary_menu() -> ReplyKeyboardMarkup:
    return _keyboard([[BTN_WRITE, BTN_FIND], [BTN_PHOTO, BTN_RECORDS], [BTN_BACK]])


def records_months_menu(today: date) -> ReplyKeyboardMarkup:
    start_month = 5
    if today.year < 2026:
        months: list[int] = []
    elif today.year == 2026:
        months = list(range(start_month, max(start_month, today.month) + 1))
    else:
        months = list(range(start_month, 13))

    rows = [[f"{MONTHS_RU[month]} 2026"] for month in reversed(months)]
    rows.append([BTN_BACK])
    return _keyboard(rows)


def cancel_menu() -> ReplyKeyboardMarkup:
    return _keyboard([[BTN_CANCEL]])


def photo_caption_menu() -> ReplyKeyboardMarkup:
    return _keyboard([[BTN_SKIP_CAPTION], [BTN_CANCEL]])
