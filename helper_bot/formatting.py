from __future__ import annotations

from datetime import datetime

from .content import MONTHS_RU
from .storage import DiaryEntry


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
