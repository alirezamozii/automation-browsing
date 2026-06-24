# -*- coding: utf-8 -*-
"""
ماژول مدل‌ها و عملیات CRUD دیتابیس.

این ماژول شامل توابع غیرهمزمان برای ذخیره، خواندن، به‌روزرسانی
و حذف داده‌ها در جداول execution_logs، settings و workflow_state است.
"""

import json
import logging
from typing import Any

from storage.database import db_manager

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Execution Logs
# ─────────────────────────────────────────────

async def save_log(
    workflow: str,
    state: str,
    step: str,
    status: str,
    message: str,
    screenshot_path: str | None = None,
    error_traceback: str | None = None,
    session_id: str | None = None,
) -> int:
    """
    ذخیره یک رکورد لاگ اجرا در دیتابیس.

    Args:
        workflow: نام ورک‌فلو.
        state: وضعیت فعلی.
        step: نام مرحله.
        status: وضعیت اجرا ('success', 'error', 'info', 'warning').
        message: پیام لاگ.
        screenshot_path: مسیر اسکرین‌شات (اختیاری).
        error_traceback: متن خطای کامل (اختیاری).
        session_id: شناسه جلسه اجرا (اختیاری).

    Returns:
        شناسه رکورد ایجاد شده.
    """
    async with db_manager.get_connection() as db:
        cursor = await db.execute(
            """
            INSERT INTO execution_logs
                (workflow_name, state, step_name, status, message, screenshot_path, error_traceback, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (workflow, state, step, status, message, screenshot_path, error_traceback, session_id),
        )
        await db.commit()
        row_id: int = cursor.lastrowid  # type: ignore[assignment]
        logger.debug("لاگ ذخیره شد: id=%d, workflow=%s, step=%s, session_id=%s", row_id, workflow, step, session_id)
        return row_id


async def get_logs(
    workflow: str | None = None,
    status: str | None = None,
    session_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    دریافت لاگ‌های اجرا با فیلترهای اختیاری.

    Args:
        workflow: فیلتر بر اساس نام ورک‌فلو (اختیاری).
        status: فیلتر بر اساس وضعیت (اختیاری).
        session_id: فیلتر بر اساس شناسه جلسه اجرا (اختیاری).
        limit: حداکثر تعداد نتایج.
        offset: تعداد رکوردهای رد شده از ابتدا.

    Returns:
        لیستی از دیکشنری‌های حاوی اطلاعات لاگ.
    """
    query = "SELECT * FROM execution_logs WHERE 1=1"
    params: list[Any] = []

    if workflow is not None:
        query += " AND workflow_name = ?"
        params.append(workflow)
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    if session_id is not None:
        query += " AND session_id = ?"
        params.append(session_id)

    query += " ORDER BY id ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    async with db_manager.get_connection() as db:
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_log_count(
    workflow: str | None = None,
    status: str | None = None,
    session_id: str | None = None,
) -> int:
    """
    دریافت تعداد لاگ‌ها با فیلترهای اختیاری.

    Args:
        workflow: فیلتر بر اساس نام ورک‌فلو (اختیاری).
        status: فیلتر بر اساس وضعیت (اختیاری).
        session_id: فیلتر بر اساس شناسه جلسه (اختیاری).

    Returns:
        تعداد رکوردهای مطابق.
    """
    query = "SELECT COUNT(*) as cnt FROM execution_logs WHERE 1=1"
    params: list[Any] = []

    if workflow is not None:
        query += " AND workflow_name = ?"
        params.append(workflow)
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    if session_id is not None:
        query += " AND session_id = ?"
        params.append(session_id)

    async with db_manager.get_connection() as db:
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return row["cnt"] if row else 0  # type: ignore[index]


async def get_sessions(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """
    دریافت لیست جلسات (sessions) اجرا شده به همراه نام ورک‌فلو، زمان و وضعیت نهایی.
    """
    query = """
        SELECT 
            session_id,
            workflow_name,
            MIN(created_at) as started_at,
            MAX(created_at) as ended_at,
            CASE 
                WHEN SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) > 0 THEN 'error'
                ELSE 'success'
            END as final_status
        FROM execution_logs
        WHERE session_id IS NOT NULL AND session_id != 'system'
        GROUP BY session_id
        ORDER BY started_at DESC
        LIMIT ? OFFSET ?
    """
    async with db_manager.get_connection() as db:
        cursor = await db.execute(query, [limit, offset])
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_session_count() -> int:
    """
    دریافت تعداد کل جلسات اجرا شده.
    """
    query = "SELECT COUNT(DISTINCT session_id) as cnt FROM execution_logs WHERE session_id IS NOT NULL AND session_id != 'system'"
    async with db_manager.get_connection() as db:
        cursor = await db.execute(query)
        row = await cursor.fetchone()
        return row["cnt"] if row else 0


async def clear_logs(workflow: str | None = None) -> int:
    """
    حذف لاگ‌های اجرا.

    Args:
        workflow: در صورت ارائه فقط لاگ‌های این ورک‌فلو حذف می‌شوند.

    Returns:
        تعداد رکوردهای حذف شده.
    """
    if workflow is not None:
        query = "DELETE FROM execution_logs WHERE workflow_name = ?"
        params: tuple[Any, ...] = (workflow,)
    else:
        query = "DELETE FROM execution_logs"
        params = ()

    async with db_manager.get_connection() as db:
        cursor = await db.execute(query, params)
        await db.commit()
        deleted: int = cursor.rowcount  # type: ignore[assignment]
        logger.info("تعداد %d لاگ حذف شد.", deleted)
        return deleted


# ─────────────────────────────────────────────
#  Workflow State
# ─────────────────────────────────────────────

async def save_state(workflow: str, state_data: dict[str, Any]) -> None:
    """
    ذخیره یا به‌روزرسانی وضعیت ورک‌فلو.

    اگر رکوردی برای این ورک‌فلو وجود داشته باشد به‌روزرسانی می‌شود،
    در غیر این صورت رکورد جدید ایجاد می‌شود.

    Args:
        workflow: نام ورک‌فلو.
        state_data: دیکشنری داده‌های وضعیت (به JSON تبدیل می‌شود).
    """
    serialized: str = json.dumps(state_data, ensure_ascii=False)

    async with db_manager.get_connection() as db:
        # بررسی وجود رکورد قبلی
        cursor = await db.execute(
            "SELECT id FROM workflow_state WHERE workflow_name = ?",
            (workflow,),
        )
        existing = await cursor.fetchone()

        if existing:
            await db.execute(
                """
                UPDATE workflow_state
                SET state_data = ?, is_active = 1, updated_at = CURRENT_TIMESTAMP
                WHERE workflow_name = ?
                """,
                (serialized, workflow),
            )
            logger.debug("وضعیت ورک‌فلو '%s' به‌روزرسانی شد.", workflow)
        else:
            await db.execute(
                """
                INSERT INTO workflow_state (workflow_name, state_data, is_active)
                VALUES (?, ?, 1)
                """,
                (workflow, serialized),
            )
            logger.debug("وضعیت ورک‌فلو '%s' ذخیره شد.", workflow)

        await db.commit()


async def load_state(workflow: str) -> dict[str, Any] | None:
    """
    بارگذاری وضعیت ورک‌فلو از دیتابیس.

    Args:
        workflow: نام ورک‌فلو.

    Returns:
        دیکشنری داده‌های وضعیت یا None در صورت عدم وجود.
    """
    async with db_manager.get_connection() as db:
        cursor = await db.execute(
            "SELECT state_data FROM workflow_state WHERE workflow_name = ? ORDER BY updated_at DESC LIMIT 1",
            (workflow,),
        )
        row = await cursor.fetchone()

        if row is None:
            return None

        return json.loads(row["state_data"])  # type: ignore[index]


async def clear_state(workflow: str) -> None:
    """
    حذف وضعیت ورک‌فلو از دیتابیس.

    Args:
        workflow: نام ورک‌فلو.
    """
    async with db_manager.get_connection() as db:
        await db.execute(
            "DELETE FROM workflow_state WHERE workflow_name = ?",
            (workflow,),
        )
        await db.commit()
        logger.info("وضعیت ورک‌فلو '%s' حذف شد.", workflow)


# ─────────────────────────────────────────────
#  Settings
# ─────────────────────────────────────────────

async def save_setting(key: str, value: str) -> None:
    """
    ذخیره یا به‌روزرسانی یک تنظیم.

    Args:
        key: کلید تنظیم.
        value: مقدار تنظیم.
    """
    async with db_manager.get_connection() as db:
        await db.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        await db.commit()
        logger.debug("تنظیم '%s' ذخیره شد.", key)


async def get_setting(key: str, default: str | None = None) -> str | None:
    """
    دریافت مقدار یک تنظیم.

    Args:
        key: کلید تنظیم.
        default: مقدار پیش‌فرض در صورت عدم وجود.

    Returns:
        مقدار تنظیم یا مقدار پیش‌فرض.
    """
    async with db_manager.get_connection() as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        )
        row = await cursor.fetchone()

        if row is None:
            return default
        return row["value"]  # type: ignore[index]


async def get_all_settings() -> dict[str, str]:
    """
    دریافت تمام تنظیمات.

    Returns:
        دیکشنری از تمام تنظیمات (کلید: مقدار).
    """
    async with db_manager.get_connection() as db:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}  # type: ignore[index]


# ─────────────────────────────────────────────
#  Execution Stats
# ─────────────────────────────────────────────

async def get_execution_stats(workflow: str | None = None) -> dict[str, int]:
    """
    دریافت آمار اجرا شامل تعداد کل، موفق و خطا.

    Args:
        workflow: فیلتر بر اساس نام ورک‌فلو (اختیاری).

    Returns:
        دیکشنری شامل کلیدهای total, success, error.
    """
    base = "FROM execution_logs WHERE 1=1"
    params: list[Any] = []

    if workflow is not None:
        base += " AND workflow_name = ?"
        params.append(workflow)

    async with db_manager.get_connection() as db:
        # تعداد کل
        cursor = await db.execute(f"SELECT COUNT(*) as cnt {base}", params)
        total_row = await cursor.fetchone()
        total: int = total_row["cnt"] if total_row else 0  # type: ignore[index]

        # تعداد موفق
        cursor = await db.execute(
            f"SELECT COUNT(*) as cnt {base} AND status = 'success'", params
        )
        success_row = await cursor.fetchone()
        success: int = success_row["cnt"] if success_row else 0  # type: ignore[index]

        # تعداد خطا
        cursor = await db.execute(
            f"SELECT COUNT(*) as cnt {base} AND status = 'error'", params
        )
        error_row = await cursor.fetchone()
        error: int = error_row["cnt"] if error_row else 0  # type: ignore[index]

    return {
        "total": total,
        "success": success,
        "error": error,
    }


async def get_log_by_id(log_id: int) -> dict[str, Any] | None:
    """
    دریافت یک لاگ خاص با شناسه.

    Args:
        log_id: شناسه لاگ.

    Returns:
        دیکشنری حاوی اطلاعات لاگ یا None.
    """
    async with db_manager.get_connection() as db:
        cursor = await db.execute("SELECT * FROM execution_logs WHERE id = ?", (log_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_settings(settings: dict[str, str]) -> None:
    """
    بروزرسانی دسته‌ای تنظیمات.

    Args:
        settings: دیکشنری تنظیمات جدید (کلید: مقدار).
    """
    async with db_manager.get_connection() as db:
        for key, value in settings.items():
            await db.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )
        await db.commit()
        logger.info("تنظیمات با موفقیت بروزرسانی شدند.")

