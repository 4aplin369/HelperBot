from __future__ import annotations

import html
import logging
import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime

import aiohttp

from .config import Settings
from .content import MONTHS_GENITIVE_RU, MONTHS_RU
from .lunar_service import LunarService
from .storage import Storage

logger = logging.getLogger(__name__)
ZODIAC_SYMBOLS_RE = re.compile(r"\s*[♈♉♊♋♌♍♎♏♐♑♒♓]")


@dataclass(frozen=True)
class GardenDayInfo:
    date: date
    category: str
    moon_info: str
    zodiac_info: str
    source_url: str


@dataclass(frozen=True)
class DailyGardenDetails:
    good: tuple[str, ...]
    medium: tuple[str, ...]
    bad: tuple[str, ...]
    folk_signs: tuple[str, ...]


class Dacha6Service:
    def __init__(self, settings: Settings, lunar_service: LunarService, storage: Storage | None = None) -> None:
        self.settings = settings
        self.lunar_service = lunar_service
        self.storage = storage

    async def garden_text(self, today: date, include_folk_signs: bool = True) -> str:
        cache_key = f"dacha6:garden:{today.isoformat()}:folk={int(include_folk_signs)}"
        cached = self._get_cached_text(cache_key)
        if cached is not None:
            return cached

        info = await self.get_day(today)
        if info is None:
            text = _with_today_title(today, self.lunar_service.garden_text(today))
            self._save_cached_text(cache_key, text, "fallback")
            return text

        details = await self.get_daily_details(today)
        if details is not None:
            text = _with_today_title(
                today,
                _format_daily_details(
                    settings=self.settings,
                    info=info,
                    details=details,
                    include_folk_signs=include_folk_signs,
                ),
            )
            self._save_cached_text(cache_key, text, "dacha6")
            return text

        text = _with_today_title(
            today,
            _remove_zodiac_symbols(
                f"По календарю dacha6 для региона {self.settings.lunar_city}, {self.settings.lunar_region}: "
                f"{info.category.lower()}.\n"
                f"{self._advice_for_category(info.category)}\n"
                f"{info.moon_info}"
            ),
        )
        self._save_cached_text(cache_key, text, "dacha6")
        return text

    async def get_daily_details(self, today: date) -> DailyGardenDetails | None:
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.settings.dacha6_calendar_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    response.raise_for_status()

                day_url = f"https://www.dacha6.ru/lunnyi-kalendar-dachnika/{today.year}/{today.month}/{today.day}/"
                async with session.get(day_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    response.raise_for_status()
                    page = await response.text()
        except aiohttp.ClientResponseError as exc:
            logger.warning("Failed to fetch dacha6 daily details: HTTP %s %s", exc.status, exc.request_info.real_url)
            return None
        except Exception as exc:
            logger.warning("Failed to fetch dacha6 daily details: %s", exc)
            return None

        if self.settings.lunar_city not in page and self.settings.lunar_region not in page:
            logger.warning("dacha6 daily page did not keep selected region")
            return None

        return _parse_daily_details(page)

    async def month_text(self, today: date) -> str:
        cache_key = f"dacha6:month:{today.year:04d}-{today.month:02d}"
        cached = self._get_cached_text(cache_key)
        if cached is not None:
            return cached

        page = await self._fetch_month_page(today.year, today.month)
        if page is None:
            return "Не получилось загрузить календарь dacha6. Попробуйте позже."

        summary = _month_summary_text(page)
        days = _month_days_text(page, today)
        if not summary and not days:
            return "Не получилось разобрать календарь dacha6. Сайт мог изменить разметку."

        parts = [
            f"Садоводческий календарь dacha6: {MONTHS_RU[today.month]} {today.year}, "
            f"{self.settings.lunar_city}, {self.settings.lunar_region}"
        ]
        if summary:
            parts.append(summary)
        if days:
            parts.append(days)
        text = _remove_zodiac_symbols("\n\n".join(parts))
        self._save_cached_text(cache_key, text, "dacha6")
        return text

    async def sowing_days_text(self, target_month: date | None = None) -> str:
        if target_month is None:
            target_month = date.today()
        cache_key = f"dacha6:sowing:{target_month.year:04d}-{target_month.month:02d}"
        cached = self._get_cached_text(cache_key)
        if cached is not None:
            return cached

        page = await self._fetch_month_page(target_month.year, target_month.month)
        if page is None:
            return "Не получилось загрузить таблицу дней для посева. Попробуйте позже."

        rows = _parse_sowing_days(page)
        if not rows:
            return "Не получилось разобрать таблицу дней для посева. Сайт мог изменить разметку."

        lines = [
            f"Дни для посева dacha6: {MONTHS_RU[target_month.month]} {target_month.year}, "
            f"{self.settings.lunar_city}, {self.settings.lunar_region}"
        ]
        for culture, days in rows:
            lines.append(f"{culture}: {days}")
        text = "\n".join(lines)
        self._save_cached_text(cache_key, text, "dacha6")
        return text

    async def get_day(self, today: date) -> GardenDayInfo | None:
        page = await self._fetch_month_page(today.year, today.month)
        if page is None:
            return None
        return _parse_day(page, today, self.settings.dacha6_calendar_url)

    async def _fetch_page(self) -> str | None:
        return await self._fetch_month_page(date.today().year, date.today().month)

    async def _fetch_month_page(self, year: int, month: int) -> str | None:
        month_url = f"https://www.dacha6.ru/lunnyi-kalendar-dachnika/{year}/{month}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.settings.dacha6_calendar_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    response.raise_for_status()
                    await response.read()

                async with session.get(
                    month_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    response.raise_for_status()
                    return await response.text()
        except aiohttp.ClientResponseError as exc:
            logger.warning("Failed to fetch dacha6 calendar: HTTP %s %s", exc.status, exc.request_info.real_url)
            return None
        except Exception as exc:
            logger.warning("Failed to fetch dacha6 calendar: %s", exc)
            return None

    def _get_cached_text(self, cache_key: str) -> str | None:
        if self.storage is None:
            return None
        cached = self.storage.get_cached_text(cache_key)
        if cached is None:
            return None
        text, source = cached
        logger.info("Using cached content %s from %s", cache_key, source)
        return text

    def _save_cached_text(self, cache_key: str, text: str, source: str) -> None:
        if self.storage is None:
            return
        self.storage.save_cached_text(cache_key, text, source, datetime.now(self.settings.timezone))

    @staticmethod
    def _advice_for_category(category: str) -> str:
        normalized = category.casefold()
        if "запрещ" in normalized or "неблагоприят" in normalized:
            return "Посев, посадку, пересадку и активные работы с растениями лучше не делать. Подойдут уборка, планирование и записи в дневник."
        if "нежелатель" in normalized:
            return "Посев, посадку, пересадку и активные работы с растениями сегодня лучше не делать. Можно осмотреть участок, прибраться и записать наблюдения."
        if "нейтраль" in normalized:
            return "День нейтральный: лучше выбирать лёгкие хозяйственные дела, осмотр и аккуратный уход без важных посадок."
        if "самые благоприят" in normalized:
            return "День считается очень удачным для садовых дел. Можно планировать основные работы с растениями, если позволяет погода и силы."
        if "благоприят" in normalized:
            return "День подходит для садовых дел и ухода за растениями. Важные работы всё равно лучше делать спокойно и без спешки."
        return "Садовые работы лучше выбирать осторожно и сверять с самочувствием, погодой и текущими задачами."


def _parse_day(page: str, today: date, source_url: str) -> GardenDayInfo | None:
    category = _category_for_day(page, today.day)
    row_text = _day_row_text(page, today)
    if category is None and row_text is None:
        return None

    return GardenDayInfo(
        date=today,
        category=category or "День без оценки",
        moon_info=_compact_moon_info(row_text or ""),
        zodiac_info=row_text or "",
        source_url=source_url,
    )


def _category_for_day(page: str, day: int) -> str | None:
    categories = [
        "Самые благоприятные дни",
        "Благоприятные дни",
        "Нейтральные дни",
        "Нежелательные дни",
        "Самые неблагоприятные (запрещенные) дни",
    ]
    for category in categories:
        match = re.search(rf"{re.escape(category)}\s*[–-]\s*([^<]+)", page)
        if not match:
            continue
        days = {int(value) for value in re.findall(r"\d+", match.group(1))}
        if day in days:
            return category
    return None


def _month_summary_text(page: str) -> str:
    labels = [
        "Самые благоприятные дни",
        "Благоприятные дни",
        "Нейтральные дни",
        "Нежелательные дни",
        "Самые неблагоприятные (запрещенные) дни",
    ]
    lines = []
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*[–-]\s*([^<]+)", page)
        if match:
            lines.append(f"{label}: {html.unescape(match.group(1)).strip()}")
    return "\n".join(lines)


def _month_days_text(page: str, today: date) -> str:
    rows = []
    for day in range(1, monthrange(today.year, today.month)[1] + 1):
        row = _day_row_text(page, date(today.year, today.month, day))
        if row is None:
            continue
        category = _category_for_day(page, day) or "без оценки"
        compact = _compact_moon_info(row).splitlines()
        moon_day = next((line for line in compact if "лунный день" in line), "")
        phase = next((line for line in compact if "луна" in line.casefold() and "Луна в знаке" not in line), "")
        sign_lines = [
            line
            for line in compact
            if any(symbol in line for symbol in "♈♉♊♋♌♍♎♏♐♑♒♓")
        ]
        sign = ", ".join(sign_lines)
        details = "; ".join(part for part in (moon_day, phase, sign) if part)
        rows.append(f"{day:02d}: {category.lower()}; {details}")
    if not rows:
        return ""
    return "По дням:\n" + "\n".join(rows)


def _day_row_text(page: str, today: date) -> str | None:
    month_name = MONTHS_GENITIVE_RU[today.month]
    pattern = (
        rf"<tr[^>]*>\s*<td>{today.day}\s+{re.escape(month_name)}\s+{today.year}<br>.*?</tr>"
    )
    match = re.search(pattern, page, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    text = match.group(0)
    text = re.sub(r"</td>\s*<td[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</span>\s*", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _compact_moon_info(row_text: str) -> str:
    useful_lines = []
    for line in row_text.splitlines():
        if (
            "Луна в знаке" in line
            or "лунный день" in line
            or "луна" in line.casefold()
            or "Дни " in line
            or "Стихия:" in line
            or any(symbol in line for symbol in "♈♉♊♋♌♍♎♏♐♑♒♓")
        ):
            useful_lines.append(line)
    return "\n".join(useful_lines[:8])


def _parse_daily_details(page: str) -> DailyGardenDetails | None:
    table_match = re.search(
        r"<h2>Таблица работ дачника.*?</h2>\s*<table[^>]*>(.*?)</table>",
        page,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not table_match:
        return None

    good: list[str] = []
    medium: list[str] = []
    bad: list[str] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), flags=re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.DOTALL | re.IGNORECASE)
        if len(cells) != 4:
            continue
        action = _clean_html(cells[0])
        if not action or action == "Огородные дела":
            continue
        if "&#11044;" in cells[1] or "●" in cells[1]:
            good.append(action)
        elif "&#11044;" in cells[2] or "●" in cells[2]:
            medium.append(action)
        elif "&#11044;" in cells[3] or "●" in cells[3]:
            bad.append(action)

    folk_signs = _parse_folk_signs(page)
    return DailyGardenDetails(
        good=tuple(good),
        medium=tuple(medium),
        bad=tuple(bad),
        folk_signs=tuple(folk_signs),
    )


def _parse_sowing_days(page: str) -> list[tuple[str, str]]:
    table_match = re.search(
        r"<table class=\"tb2_1\">(.*?)</table>",
        page,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not table_match:
        return []

    rows: list[tuple[str, str]] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), flags=re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.DOTALL | re.IGNORECASE)
        if len(cells) != 2:
            continue
        culture = _clean_html(cells[0])
        days = _clean_html(cells[1])
        if not culture or culture == "Культура":
            continue
        rows.append((culture, days))
    return rows


def _parse_folk_signs(page: str) -> list[str]:
    match = re.search(
        r"<h2>Народные приметы.*?</h2>\s*<ol>(.*?)</ol>",
        page,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return []
    return [_clean_html(item) for item in re.findall(r"<li[^>]*>(.*?)</li>", match.group(1), flags=re.DOTALL)]


def _clean_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = ZODIAC_SYMBOLS_RE.sub("", value)
    return re.sub(r"\s+", " ", value).strip()


def _remove_zodiac_symbols(value: str) -> str:
    return ZODIAC_SYMBOLS_RE.sub("", value)


def _with_today_title(today: date, text: str) -> str:
    return f"Что сделать на даче: {today.day} {MONTHS_GENITIVE_RU[today.month]} {today.year}\n\n{text}"


def _format_daily_details(
    settings: Settings,
    info: GardenDayInfo,
    details: DailyGardenDetails,
    include_folk_signs: bool,
) -> str:
    parts = [
        f"По календарю dacha6 для региона {settings.lunar_city}, {settings.lunar_region}: {info.category.lower()}.",
        info.moon_info,
    ]
    if details.good:
        parts.append("Хорошо:\n" + _bullet_list(details.good))
    if details.medium:
        parts.append("Средне:\n" + _bullet_list(details.medium))
    if details.bad:
        parts.append("Лучше не делать:\n" + _bullet_list(details.bad))
    if include_folk_signs and details.folk_signs:
        parts.append("Народные приметы:\n" + _bullet_list(details.folk_signs))
    return _remove_zodiac_symbols("\n\n".join(parts))


def _bullet_list(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items)
