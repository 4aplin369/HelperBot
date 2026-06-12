# HelperBot

Семейный Telegram-бот для папы: утренний дайджест, садовые подсказки и общий дневник дел.

## Что умеет первая версия

- закрытый доступ только для Telegram ID из `ALLOWED_USER_IDS`;
- `/start` не очищает данные, а только показывает меню;
- главное меню: `Дача`, `Дневник`, `Гороскоп`, `Настройки`;
- дневник дел: записать действие, сохранить фото, найти записи по слову, посмотреть записи по месяцам 2026 года;
- утренний дайджест по расписанию;
- по средам и субботам в дайджест добавляется напоминание про полив цветов;
- лунный календарь считается для Барнаула, Алтайский край;
- в дайджесте лунный календарь разделён на обычный блок для человека и садовый блок `На даче сегодня`;
- садовый блок `На даче сегодня` берёт региональную оценку дня с dacha6 для Алтайского края;
- ежедневная резервная копия базы данных.

## Запуск

1. Создать виртуальное окружение и установить зависимости:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

2. Скопировать `.env.example` в `.env` и заполнить:

```powershell
Copy-Item .env.example .env
```

3. Запустить бота:

```powershell
.venv\Scripts\python -m helper_bot
```

## Настройки

- `BOT_TOKEN` - токен Telegram-бота от BotFather.
- `ALLOWED_USER_IDS` - Telegram ID папы и дочери через запятую.
- `ADMIN_USER_IDS` - Telegram ID дочери, которой доступны настройки.
- `TIMEZONE` - часовой пояс для расписания, сейчас `Asia/Barnaul`.
- `DIGEST_TIME` - время утреннего дайджеста в формате `HH:MM`.
- `DATA_DIR` - папка для базы, фото и резервных копий. На Railway должна совпадать с Mount Path volume, например `/app/data`.
- `HOROSCOPE_PROVIDER` - источник гороскопа: `mail_ru`, `astrology_api` или `freehoroscopeapi`.
- `HOROSCOPE_SIGN` - знак зодиака для гороскопа, сейчас `pisces`.
- `HOROSCOPE_LANGUAGE` - язык гороскопа, сейчас `ru`.
- `HOROSCOPE_API_URL` - endpoint ежедневного гороскопа. Для `mail_ru`: `https://horo.mail.ru/prediction/{sign}/today/`.
- `HOROSCOPE_API_KEY` - ключ Astrology API. Хранить только в `.env`.
- `LUNAR_REGION`, `LUNAR_CITY`, `LUNAR_LATITUDE`, `LUNAR_LONGITUDE` - регион для лунного календаря, сейчас Барнаул, Алтайский край.
- `DACHA6_CALENDAR_URL` - региональная страница садоводческого календаря dacha6.

## Важно

Данные дневника хранятся в SQLite-базе `helper_bot.sqlite3` внутри `DATA_DIR`. Фото сохраняются в Telegram как `file_id`, а также скачиваются локально в `DATA_DIR/photos/`, если Telegram отдал файл.

Для Railway нужен persistent volume: Mount Path volume и переменная `DATA_DIR` должны указывать на один и тот же путь, например `/app/data`. При старте бот пишет в логи `Data directory`, `Database path` и количество записей в базе.
