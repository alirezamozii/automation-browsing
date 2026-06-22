# -*- coding: utf-8 -*-
"""
ماژول مدیریت مهاجرت‌های دیتابیس (migrations).

این ماژول مسئول نسخه‌بندی و اجرای خودکار تغییرات ساختاری
دیتابیس در هنگام راه‌اندازی برنامه است.
"""

import logging
from typing import Callable, Awaitable

import aiosqlite

from storage.database import db_manager

logger = logging.getLogger(__name__)

# نوع تابع مهاجرت: یک تابع async که اتصال دیتابیس دریافت می‌کند
MigrationFunc = Callable[[aiosqlite.Connection], Awaitable[None]]


# ─────────────────────────────────────────────
#  Migration Functions
# ─────────────────────────────────────────────

async def migration_001_initial_tables(db: aiosqlite.Connection) -> None:
    """
    مهاجرت اولیه: ایجاد تمام جداول پایه.

    جداول ایجاد شده:
        - execution_logs: لاگ‌های اجرای ورک‌فلوها
        - settings: تنظیمات کلید-مقدار
        - workflow_state: وضعیت ذخیره شده ورک‌فلوها
    """
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS workflow_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_name TEXT NOT NULL,
            state_data TEXT NOT NULL,
            is_active INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    logger.info("مهاجرت 001: جداول پایه ایجاد شدند.")


# ─────────────────────────────────────────────
#  Migration Registry
# ─────────────────────────────────────────────

# لیست مهاجرت‌ها به ترتیب نسخه
# برای اضافه کردن مهاجرت جدید، یک تاپل (version, name, func) اضافه کنید
MIGRATIONS: list[tuple[int, str, MigrationFunc]] = [
    (1, "initial_tables", migration_001_initial_tables),
    # (2, "add_index_on_logs", migration_002_add_index_on_logs),
    # مهاجرت‌های آینده را اینجا اضافه کنید
]


class MigrationManager:
    """
    مدیر مهاجرت‌های دیتابیس.

    این کلاس نسخه‌های مهاجرت را در یک جدول متا (_migrations)
    پیگیری می‌کند و در هنگام راه‌اندازی، مهاجرت‌های اعمال‌نشده
    را به ترتیب اجرا می‌کند.
    """

    META_TABLE: str = "_migrations"

    async def _ensure_meta_table(self, db: aiosqlite.Connection) -> None:
        """
        ایجاد جدول متا برای پیگیری مهاجرت‌ها در صورت عدم وجود.

        Args:
            db: اتصال فعال به دیتابیس.
        """
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.META_TABLE} (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()

    async def _get_applied_versions(self, db: aiosqlite.Connection) -> set[int]:
        """
        دریافت لیست نسخه‌های مهاجرت اعمال‌شده.

        Args:
            db: اتصال فعال به دیتابیس.

        Returns:
            مجموعه‌ای از شماره نسخه‌های اعمال‌شده.
        """
        cursor = await db.execute(f"SELECT version FROM {self.META_TABLE}")
        rows = await cursor.fetchall()
        return {row[0] for row in rows}

    async def _record_migration(
        self, db: aiosqlite.Connection, version: int, name: str
    ) -> None:
        """
        ثبت یک مهاجرت اعمال‌شده در جدول متا.

        Args:
            db: اتصال فعال به دیتابیس.
            version: شماره نسخه مهاجرت.
            name: نام مهاجرت.
        """
        await db.execute(
            f"INSERT INTO {self.META_TABLE} (version, name) VALUES (?, ?)",
            (version, name),
        )

    async def run_pending(self) -> int:
        """
        اجرای تمام مهاجرت‌های اعمال‌نشده.

        این متد باید در هنگام راه‌اندازی برنامه فراخوانی شود.
        مهاجرت‌ها به ترتیب شماره نسخه اجرا می‌شوند.

        Returns:
            تعداد مهاجرت‌های اعمال‌شده.
        """
        applied_count: int = 0

        async with db_manager.get_connection() as db:
            await self._ensure_meta_table(db)
            applied_versions = await self._get_applied_versions(db)

            # مرتب‌سازی بر اساس نسخه
            sorted_migrations = sorted(MIGRATIONS, key=lambda m: m[0])

            for version, name, func in sorted_migrations:
                if version in applied_versions:
                    logger.debug("مهاجرت %d (%s) قبلاً اعمال شده.", version, name)
                    continue

                logger.info("در حال اجرای مهاجرت %d: %s ...", version, name)
                try:
                    await func(db)
                    await self._record_migration(db, version, name)
                    await db.commit()
                    applied_count += 1
                    logger.info("مهاجرت %d (%s) با موفقیت اعمال شد.", version, name)
                except Exception:
                    logger.exception(
                        "خطا در اجرای مهاجرت %d (%s). عملیات لغو شد.", version, name
                    )
                    raise

        if applied_count == 0:
            logger.info("تمام مهاجرت‌ها قبلاً اعمال شده‌اند.")
        else:
            logger.info("تعداد %d مهاجرت جدید اعمال شد.", applied_count)

        return applied_count

    async def get_current_version(self) -> int:
        """
        دریافت آخرین نسخه مهاجرت اعمال‌شده.

        Returns:
            شماره آخرین نسخه اعمال‌شده یا 0 در صورت عدم وجود مهاجرت.
        """
        async with db_manager.get_connection() as db:
            await self._ensure_meta_table(db)
            cursor = await db.execute(
                f"SELECT MAX(version) as max_ver FROM {self.META_TABLE}"
            )
            row = await cursor.fetchone()
            return row[0] if row and row[0] is not None else 0


# نمونه پیش‌فرض مدیر مهاجرت
migration_manager = MigrationManager()
