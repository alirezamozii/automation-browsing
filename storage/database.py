# -*- coding: utf-8 -*-
"""
ماژول مدیریت دیتابیس SQLite با استفاده از aiosqlite.

این ماژول مسئول ایجاد و مدیریت اتصالات به دیتابیس SQLite
با پشتیبانی از عملیات غیرهمزمان (async) است.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    مدیر دیتابیس SQLite.

    این کلاس مسئول ایجاد جداول، مدیریت اتصالات و تنظیمات
    دیتابیس شامل حالت WAL برای خوانش همزمان بهتر است.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """
        مقداردهی اولیه مدیر دیتابیس.

        Args:
            db_path: مسیر فایل دیتابیس. در صورت عدم ارائه از config.DB_PATH استفاده می‌شود.
        """
        self.db_path: Path = Path(db_path) if db_path else Path(DB_PATH)
        logger.info("مسیر دیتابیس: %s", self.db_path)

    def _ensure_directory(self) -> None:
        """اطمینان از وجود دایرکتوری والد فایل دیتابیس."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self) -> None:
        """
        ایجاد جداول در صورت عدم وجود و تنظیم حالت WAL.

        این متد باید در ابتدای اجرای برنامه فراخوانی شود تا
        جداول مورد نیاز ایجاد و دیتابیس آماده استفاده شود.
        """
        self._ensure_directory()
        logger.info("در حال مقداردهی اولیه دیتابیس...")

        async with self.get_connection() as db:
            # فعال‌سازی حالت WAL برای خوانش همزمان بهتر
            await db.execute("PRAGMA journal_mode=WAL;")
            logger.info("حالت WAL فعال شد.")

            # ایجاد جدول لاگ‌های اجرا
            await db.execute("""
                CREATE TABLE IF NOT EXISTS execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_name TEXT NOT NULL,
                    state TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('success', 'error', 'info', 'warning')),
                    message TEXT NOT NULL,
                    screenshot_path TEXT NULL,
                    error_traceback TEXT NULL,
                    session_id TEXT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # ایجاد جدول تنظیمات
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # ایجاد جدول وضعیت ورک‌فلو
            await db.execute("""
                CREATE TABLE IF NOT EXISTS workflow_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_name TEXT NOT NULL,
                    state_data TEXT NOT NULL,
                    is_active INTEGER DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

            await db.commit()
            logger.info("جداول دیتابیس با موفقیت ایجاد شدند.")

    @asynccontextmanager
    async def get_connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """
        ارائه یک اتصال به دیتابیس به صورت context manager.

        این متد یک اتصال غیرهمزمان به دیتابیس SQLite باز می‌کند
        و پس از اتمام کار آن را می‌بندد.

        Yields:
            اتصال aiosqlite به دیتابیس.
        """
        self._ensure_directory()
        db: aiosqlite.Connection | None = None
        try:
            db = await aiosqlite.connect(str(self.db_path))
            db.row_factory = aiosqlite.Row
            # فعال‌سازی کلیدهای خارجی
            await db.execute("PRAGMA foreign_keys=ON;")
            yield db
        except aiosqlite.Error as e:
            logger.error("خطا در اتصال به دیتابیس: %s", e)
            raise
        finally:
            if db is not None:
                await db.close()


# نمونه پیش‌فرض مدیر دیتابیس
db_manager = DatabaseManager()
