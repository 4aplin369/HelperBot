from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class DiaryEntry:
    id: int
    user_id: int
    text: str
    photo_file_id: str | None
    photo_local_path: str | None
    created_at: datetime


class Storage:
    def __init__(self, database_path: Path, photos_dir: Path, backups_dir: Path) -> None:
        self.database_path = database_path
        self.photos_dir = photos_dir
        self.backups_dir = backups_dir

    def init(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS diary_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    text TEXT NOT NULL DEFAULT '',
                    photo_file_id TEXT,
                    photo_local_path TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_diary_entries_created_at
                    ON diary_entries(created_at);

                CREATE INDEX IF NOT EXISTS idx_diary_entries_user_id
                    ON diary_entries(user_id);

                CREATE TABLE IF NOT EXISTS sent_digests (
                    digest_date TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    sent_at TEXT NOT NULL,
                    PRIMARY KEY (digest_date, user_id)
                );

                CREATE TABLE IF NOT EXISTS daily_horoscopes (
                    horoscope_date TEXT NOT NULL,
                    sign TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (horoscope_date, sign)
                );
                """
            )

    def add_entry(
        self,
        user_id: int,
        text: str,
        created_at: datetime,
        photo_file_id: str | None = None,
        photo_local_path: str | None = None,
    ) -> DiaryEntry:
        clean_text = text.strip()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO diary_entries(user_id, text, photo_file_id, photo_local_path, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, clean_text, photo_file_id, photo_local_path, created_at.isoformat()),
            )
            entry_id = int(cursor.lastrowid)
        return DiaryEntry(entry_id, user_id, clean_text, photo_file_id, photo_local_path, created_at)

    def search_entries(self, query: str, limit: int = 10) -> list[DiaryEntry]:
        needle = query.strip().casefold()
        if not needle:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, text, photo_file_id, photo_local_path, created_at
                FROM diary_entries
                ORDER BY created_at DESC, id DESC
                """,
            ).fetchall()
        entries = [self._entry_from_row(row) for row in rows]
        return [entry for entry in entries if needle in entry.text.casefold()][:limit]

    def entries_for_month(self, year: int, month: int, limit: int = 50) -> list[DiaryEntry]:
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, text, photo_file_id, photo_local_path, created_at
                FROM diary_entries
                WHERE created_at >= ? AND created_at < ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (start.isoformat(), end.isoformat(), limit),
            ).fetchall()
        return [self._entry_from_row(row) for row in rows]

    def all_entries(self) -> list[DiaryEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, text, photo_file_id, photo_local_path, created_at
                FROM diary_entries
                ORDER BY created_at ASC, id ASC
                """,
            ).fetchall()
        return [self._entry_from_row(row) for row in rows]

    def was_digest_sent(self, digest_date: date, user_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM sent_digests WHERE digest_date = ? AND user_id = ?",
                (digest_date.isoformat(), user_id),
            ).fetchone()
        return row is not None

    def mark_digest_sent(self, digest_date: date, user_id: int, sent_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sent_digests(digest_date, user_id, sent_at)
                VALUES (?, ?, ?)
                """,
                (digest_date.isoformat(), user_id, sent_at.isoformat()),
            )

    def backup(self, now: datetime) -> Path:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        backup_path = self.backups_dir / f"helper_bot_{now:%Y%m%d_%H%M%S}.sqlite3"
        with self._connect() as source, sqlite3.connect(backup_path) as target:
            source.backup(target)

        photos_backup = self.backups_dir / f"photos_{now:%Y%m%d_%H%M%S}"
        if self.photos_dir.exists():
            shutil.copytree(self.photos_dir, photos_backup, dirs_exist_ok=True)
        return backup_path

    def get_horoscope(self, horoscope_date: date, sign: str) -> tuple[str, str] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT text, source
                FROM daily_horoscopes
                WHERE horoscope_date = ? AND sign = ?
                """,
                (horoscope_date.isoformat(), sign),
            ).fetchone()
        if row is None:
            return None
        return str(row["text"]), str(row["source"])

    def save_horoscope(
        self,
        horoscope_date: date,
        sign: str,
        text: str,
        source: str,
        fetched_at: datetime,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_horoscopes(horoscope_date, sign, text, source, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(horoscope_date, sign)
                DO UPDATE SET text = excluded.text, source = excluded.source, fetched_at = excluded.fetched_at
                """,
                (horoscope_date.isoformat(), sign, text.strip(), source, fetched_at.isoformat()),
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _entry_from_row(row: sqlite3.Row) -> DiaryEntry:
        return DiaryEntry(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            text=str(row["text"]),
            photo_file_id=row["photo_file_id"],
            photo_local_path=row["photo_local_path"],
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )
