from __future__ import annotations

from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .content import MONTHS_RU


BTN_DACHA = "Дача"
BTN_DIARY = "Дневник"
BTN_HOROSCOPE = "Гороскоп"
BTN_AI_CHAT = "🤖 Спросить ИИ"
BTN_AI_NEW_CHAT = "🧹 Новый разговор"
BTN_AI_EXIT = "↩️ Выйти из ИИ"
BTN_TEST = "Тест"
BTN_TEST_DIGEST = "Тест утреннего дайджеста"
BTN_TEST_DIARY_REMINDER = "Тест вечернего сообщения"
BTN_TEST_WEEKLY_REVIEW = "Тест итогов недели"
BTN_TEST_PROMPT = "✏️ Промт итогов недели"
BTN_PROMPT_SAVE = "💾 Сохранить"
BTN_PROMPT_RETRY = "🔁 Ещё правки"
BTN_CALENDAR = "Календарь"
BTN_SOWING_DAYS = "Дни для посева"
BTN_TODAY_TIP = "Что сделать?"
BTN_WRITE = "Записать"
BTN_FIND = "Найти"
BTN_PHOTO = "Фото"
BTN_RECORDS = "Записи"
BTN_DOWNLOAD = "Скачать"
BTN_BACK = "Назад"
BTN_CANCEL = "Отмена"
BTN_SKIP_CAPTION = "Без подписи"
CALLBACK_OPEN_DIARY = "open_diary"


def _available_2026_months(today: date) -> list[int]:
    start_month = 5
    test_end_month = 6
    if today.year < 2026:
        end_month = test_end_month
    elif today.year == 2026:
        end_month = min(12, max(test_end_month, today.month + 1))
    else:
        end_month = 12
    return list(range(start_month, end_month + 1))


def _keyboard(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in rows],
        resize_keyboard=True,
        input_field_placeholder="Выберите кнопку или напишите сообщение",
    )


def main_menu(is_admin: bool) -> ReplyKeyboardMarkup:
    rows = [[BTN_DACHA, BTN_DIARY], [BTN_HOROSCOPE, BTN_AI_CHAT]]
    if is_admin:
        rows.append([BTN_TEST])
    return _keyboard(rows)


def test_menu() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [BTN_TEST_DIGEST],
            [BTN_TEST_DIARY_REMINDER],
            [BTN_TEST_WEEKLY_REVIEW],
            [BTN_TEST_PROMPT],
            [BTN_BACK],
        ]
    )


def weekly_prompt_review_menu() -> ReplyKeyboardMarkup:
    return _keyboard([[BTN_PROMPT_SAVE], [BTN_PROMPT_RETRY], [BTN_CANCEL]])


def ai_chat_menu() -> ReplyKeyboardMarkup:
    return _keyboard([[BTN_AI_NEW_CHAT], [BTN_AI_EXIT]])


def diary_reminder_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📖 Открыть дневник", callback_data=CALLBACK_OPEN_DIARY)]
        ]
    )


def dacha_menu() -> ReplyKeyboardMarkup:
    return _keyboard([[BTN_CALENDAR, BTN_TODAY_TIP], [BTN_SOWING_DAYS], [BTN_BACK]])


def dacha_months_menu(action: str, today: date) -> ReplyKeyboardMarkup:
    rows = [[f"{action}: {MONTHS_RU[month]} 2026"] for month in reversed(_available_2026_months(today))]
    rows.append([BTN_BACK])
    return _keyboard(rows)


def diary_menu() -> ReplyKeyboardMarkup:
    return _keyboard([[BTN_WRITE, BTN_FIND], [BTN_PHOTO, BTN_RECORDS], [BTN_DOWNLOAD], [BTN_BACK]])


def records_months_menu(today: date) -> ReplyKeyboardMarkup:
    rows = [[f"{MONTHS_RU[month]} 2026"] for month in reversed(_available_2026_months(today))]
    rows.append([BTN_BACK])
    return _keyboard(rows)


def cancel_menu() -> ReplyKeyboardMarkup:
    return _keyboard([[BTN_CANCEL]])


def photo_caption_menu() -> ReplyKeyboardMarkup:
    return _keyboard([[BTN_SKIP_CAPTION], [BTN_CANCEL]])
