from __future__ import annotations

from datetime import datetime

from .content import MONTHS_RU
from .storage import DiaryEntry


TELEGRAM_TEXT_LIMIT = 4096
LONG_ENTRY_WARNING_THRESHOLD = 3800


def format_entry(entry: DiaryEntry) -> str:
    date_text = entry.created_at.strftime("%d.%m.%Y")
    time_text = entry.created_at.strftime("%H:%M")
    photo_mark = " [фото]" if entry.photo_file_id else ""
    text = entry.text or "Без подписи"
    return f"{date_text} {time_text}{photo_mark}\n{text}"


def format_entries(entries: list[DiaryEntry], empty_text: str) -> str:
    if not entries:
        return empty_text
    return "\n\n".join(format_entry(entry) for entry in entries)


def format_saved_entry(entry: DiaryEntry) -> str:
    parts = [
        f"Записал:\n{entry.created_at:%d.%m.%Y %H:%M}\n{entry.text}",
        f"Длина записи: {len(entry.text)} символов.",
    ]
    warning = long_entry_warning(entry.text)
    if warning:
        parts.append(warning)
    return "\n\n".join(parts)


def long_entry_warning(text: str) -> str | None:
    stripped = text.rstrip()
    if len(text) >= LONG_ENTRY_WARNING_THRESHOLD:
        return (
            "Внимание: запись очень длинная. У Telegram есть ограничение около "
            f"{TELEGRAM_TEXT_LIMIT} символов на одно сообщение, поэтому лучше разбивать такие записи на несколько частей."
        )
    if stripped.endswith("…") or stripped.endswith("..."):
        return (
            "Внимание: запись заканчивается многоточием. Похоже, текст мог прийти уже обрезанным. "
            "Лучше отправить продолжение отдельной записью."
        )
    return None


def format_entries_export(entries: list[DiaryEntry]) -> str:
    if not entries:
        return "Дневник пока пуст.\n"

    lines = ["Дневник дел", "===========", ""]
    current_date = ""
    for entry in entries:
        date_text = entry.created_at.strftime("%d.%m.%Y")
        if date_text != current_date:
            current_date = date_text
            lines.extend([date_text, "-" * len(date_text)])

        time_text = entry.created_at.strftime("%H:%M")
        photo_mark = " [фото]" if entry.photo_file_id else ""
        text = entry.text or "Без подписи"
        lines.append(f"{time_text}{photo_mark} {text}")
        if entry.photo_local_path:
            lines.append(f"Фото: {entry.photo_local_path}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def parse_month_button(text: str) -> tuple[int, int] | None:
    parts = text.strip().split()
    if len(parts) != 2 or parts[1] != "2026":
        return None
    month_name = parts[0]
    for month, name in MONTHS_RU.items():
        if name == month_name:
            return 2026, month
    return None


def month_title(year: int, month: int) -> str:
    return f"{MONTHS_RU[month]} {year}"
