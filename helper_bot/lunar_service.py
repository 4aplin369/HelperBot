from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from math import floor

from .config import Settings

SYNODIC_MONTH_DAYS = 29.530588853
REFERENCE_NEW_MOON_UTC = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)


@dataclass(frozen=True)
class LunarDayInfo:
    date: date
    city: str
    region: str
    latitude: float
    longitude: float
    lunar_day: int
    moon_age: float
    illumination_percent: int
    phase_name: str
    general_text: str
    garden_text: str


class LunarService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def for_date(self, today: date) -> LunarDayInfo:
        # Local noon keeps the calculation tied to the selected region's date.
        local_noon = datetime.combine(today, time(12, 0), tzinfo=self.settings.timezone)
        days_since_new_moon = (
            local_noon.astimezone(timezone.utc) - REFERENCE_NEW_MOON_UTC
        ).total_seconds() / 86400
        moon_age = days_since_new_moon % SYNODIC_MONTH_DAYS
        lunar_day = min(30, floor(moon_age) + 1)
        illumination_percent = round(_illumination_fraction(moon_age) * 100)
        general_text = _general_lunar_text(lunar_day, moon_age)
        garden_text = _garden_recommendation(lunar_day, moon_age)

        return LunarDayInfo(
            date=today,
            city=self.settings.lunar_city,
            region=self.settings.lunar_region,
            latitude=self.settings.lunar_latitude,
            longitude=self.settings.lunar_longitude,
            lunar_day=lunar_day,
            moon_age=moon_age,
            illumination_percent=illumination_percent,
            phase_name=_phase_name(moon_age),
            general_text=general_text,
            garden_text=garden_text,
        )

    def daily_text(self, today: date) -> str:
        info = self.for_date(today)
        return (
            f"{info.city}, {info.region}: {info.lunar_day}-й лунный день, "
            f"{info.phase_name}, освещённость около {info.illumination_percent}%.\n"
            f"{info.general_text}"
        )

    def garden_text(self, today: date) -> str:
        info = self.for_date(today)
        return (
            f"По садоводческому лунному календарю для региона {info.city}, {info.region}:\n"
            f"{info.garden_text}"
        )


def _illumination_fraction(moon_age: float) -> float:
    if moon_age <= SYNODIC_MONTH_DAYS / 2:
        return moon_age / (SYNODIC_MONTH_DAYS / 2)
    return (SYNODIC_MONTH_DAYS - moon_age) / (SYNODIC_MONTH_DAYS / 2)


def _phase_name(moon_age: float) -> str:
    if moon_age < 1.5:
        return "новолуние"
    if moon_age < 7.4:
        return "растущая Луна"
    if moon_age < 8.9:
        return "первая четверть"
    if moon_age < 14.8:
        return "растущая Луна"
    if moon_age < 16.3:
        return "полнолуние"
    if moon_age < 22.1:
        return "убывающая Луна"
    if moon_age < 23.6:
        return "последняя четверть"
    return "убывающая Луна"


def _general_lunar_text(lunar_day: int, moon_age: float) -> str:
    if lunar_day in {1, 2, 29, 30}:
        return "День больше подходит для спокойного планирования, завершения мелких дел и отдыха от лишней суеты."
    if 3 <= lunar_day <= 7:
        return "День подходит для мягкого движения вперёд, небольших решений и дел, где важны внимание и спокойный темп."
    if 8 <= lunar_day <= 14:
        return "Энергии больше, но лучше не распыляться: выбрать одно главное дело и довести его до результата."
    if 15 <= lunar_day <= 16:
        return "Лучше избегать спешки, эмоциональных решений и лишних споров. Подходит наблюдение и наведение порядка."
    if 17 <= lunar_day <= 22:
        return "Хорошее время для практичных задач, разбора накопленного и аккуратного завершения начатого."
    return "День подходит для спокойной уборки, подведения итогов и подготовки к следующим делам."


def _garden_recommendation(lunar_day: int, moon_age: float) -> str:
    if lunar_day == 5:
        return "Посев, посадку, пересадку и активные работы с растениями сегодня лучше не делать. Можно планировать, осматривать участок, проверять инструмент и записывать наблюдения."
    if lunar_day in {1, 2, 29, 30}:
        return "Посадки, пересадку и сильную обрезку лучше отложить. Подойдут уборка, планирование и спокойный осмотр растений."
    if 3 <= lunar_day <= 7:
        return "Можно делать только мягкий уход: осмотр, лёгкую уборку, записи. Посев и посадку пока лучше сверять с отдельным садовым календарём."
    if 8 <= lunar_day <= 14:
        return "Подойдут аккуратный уход, подвязка, прополка и наблюдение. С посадками лучше не спешить без проверки по садоводческому календарю."
    if 15 <= lunar_day <= 16:
        return "Новые посадки и пересадки лучше не начинать. Можно заняться уборкой, прополкой и спокойным осмотром."
    if 17 <= lunar_day <= 22:
        return "Можно заниматься уборкой, прополкой, борьбой с вредителями и подготовкой почвы. С посадками лучше сверяться дополнительно."
    return "Подойдут уборка, подготовка грядок и записи в дневник. Посев и пересадку чувствительных растений лучше отложить."
