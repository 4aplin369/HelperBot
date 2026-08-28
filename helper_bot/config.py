from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    allowed_user_ids: frozenset[int]
    admin_user_ids: frozenset[int]
    timezone: ZoneInfo
    digest_hour: int
    digest_minute: int
    diary_reminder_hour: int
    diary_reminder_minute: int
    weekly_review_enabled: bool
    weekly_review_weekday: int
    weekly_review_hour: int
    weekly_review_minute: int
    amvera_api_token: str
    amvera_llm_base_url: str
    amvera_llm_model: str
    data_dir: Path
    horoscope_provider: str
    horoscope_sign: str
    horoscope_api_url: str
    horoscope_api_key: str
    horoscope_language: str
    recipient_name: str
    lunar_region: str
    lunar_city: str
    lunar_latitude: float
    lunar_longitude: float
    dacha6_calendar_url: str

    @property
    def database_path(self) -> Path:
        return self.data_dir / "helper_bot.sqlite3"

    @property
    def photos_dir(self) -> Path:
        return self.data_dir / "photos"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"


def _parse_ids(value: str) -> frozenset[int]:
    ids: set[int] = set()
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        ids.add(int(part))
    return frozenset(ids)


def _parse_time(value: str, variable_name: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as exc:
        raise ValueError(f"{variable_name} must be in HH:MM format") from exc

    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"{variable_name} must be a valid 24-hour time")
    return hour, minute


def _parse_bool(value: str, variable_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"{variable_name} must be true or false")


def _parse_weekday(value: str) -> int:
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    normalized = value.strip().lower()
    if normalized in weekdays:
        return weekdays[normalized]
    try:
        weekday = int(normalized)
    except ValueError as exc:
        raise ValueError("WEEKLY_REVIEW_DAY must be a weekday name or a number from 0 to 6") from exc
    if not 0 <= weekday <= 6:
        raise ValueError("WEEKLY_REVIEW_DAY must be a weekday name or a number from 0 to 6")
    return weekday


def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    allowed_user_ids = _parse_ids(os.getenv("ALLOWED_USER_IDS", ""))
    if not allowed_user_ids:
        raise RuntimeError("ALLOWED_USER_IDS must contain at least one Telegram user ID")

    admin_user_ids = _parse_ids(os.getenv("ADMIN_USER_IDS", ""))
    if not admin_user_ids:
        admin_user_ids = allowed_user_ids

    digest_hour, digest_minute = _parse_time(os.getenv("DIGEST_TIME", "08:00"), "DIGEST_TIME")
    diary_reminder_hour, diary_reminder_minute = _parse_time(
        os.getenv("DIARY_REMINDER_TIME", "18:00"),
        "DIARY_REMINDER_TIME",
    )
    weekly_review_hour, weekly_review_minute = _parse_time(
        os.getenv("WEEKLY_REVIEW_TIME", "19:00"),
        "WEEKLY_REVIEW_TIME",
    )
    data_dir_value = os.getenv("DATA_DIR", "").strip()
    railway_volume_dir = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if railway_volume_dir and (not data_dir_value or data_dir_value == "data"):
        data_dir_value = railway_volume_dir
    if not data_dir_value:
        data_dir_value = "data"
    data_dir = Path(data_dir_value).resolve()

    return Settings(
        bot_token=bot_token,
        allowed_user_ids=allowed_user_ids,
        admin_user_ids=admin_user_ids,
        timezone=ZoneInfo(os.getenv("TIMEZONE", "Asia/Barnaul")),
        digest_hour=digest_hour,
        digest_minute=digest_minute,
        diary_reminder_hour=diary_reminder_hour,
        diary_reminder_minute=diary_reminder_minute,
        weekly_review_enabled=_parse_bool(
            os.getenv("WEEKLY_REVIEW_ENABLED", "false"),
            "WEEKLY_REVIEW_ENABLED",
        ),
        weekly_review_weekday=_parse_weekday(os.getenv("WEEKLY_REVIEW_DAY", "sunday")),
        weekly_review_hour=weekly_review_hour,
        weekly_review_minute=weekly_review_minute,
        amvera_api_token=os.getenv("AMVERA_API_TOKEN", "").strip(),
        amvera_llm_base_url=os.getenv(
            "AMVERA_LLM_BASE_URL",
            "https://inference.waw0.amvera.ru/v1",
        ).strip(),
        amvera_llm_model=os.getenv("AMVERA_LLM_MODEL", "gpt-4.1").strip(),
        data_dir=data_dir,
        horoscope_provider=os.getenv("HOROSCOPE_PROVIDER", "mail_ru").strip().lower(),
        horoscope_sign=os.getenv("HOROSCOPE_SIGN", "pisces").strip().lower(),
        horoscope_api_url=os.getenv(
            "HOROSCOPE_API_URL",
            "https://horo.mail.ru/prediction/{sign}/today/",
        ).strip(),
        horoscope_api_key=os.getenv("HOROSCOPE_API_KEY", "").strip(),
        horoscope_language=os.getenv("HOROSCOPE_LANGUAGE", "ru").strip().lower(),
        recipient_name=os.getenv("RECIPIENT_NAME", "Павел Николаевич").strip(),
        lunar_region=os.getenv("LUNAR_REGION", "Алтайский край").strip(),
        lunar_city=os.getenv("LUNAR_CITY", "Барнаул").strip(),
        lunar_latitude=float(os.getenv("LUNAR_LATITUDE", "53.3606")),
        lunar_longitude=float(os.getenv("LUNAR_LONGITUDE", "83.7636")),
        dacha6_calendar_url=os.getenv(
            "DACHA6_CALENDAR_URL",
            "https://www.dacha6.ru/lunnyi-kalendar-dachnika/altayskiy-kray/",
        ).strip(),
    )
