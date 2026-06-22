# -*- coding: utf-8 -*-
"""
سیستم رویداد (Event Bus) ناهمزمان

این ماژول یک سیستم انتشار/اشتراک (pub/sub) ناهمزمان برای ارتباط بین
اجزای مختلف پلتفرم فراهم می‌کند. تمام callback ها به صورت async اجرا می‌شوند.
"""

import asyncio
import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger("automation_platform.events")

# نوع callback: تابعی ناهمزمان که یک دیکشنری دریافت می‌کند
AsyncCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]

# رویدادهای استاندارد پلتفرم
STANDARD_EVENTS: list[str] = [
    "state_changed",
    "step_started",
    "step_completed",
    "error",
    "paused",
    "resumed",
    "workflow_done",
    "log_entry",
    "notification",
]


class EventBus:
    """
    گذرگاه رویداد ناهمزمان

    این کلاس مسئول مدیریت اشتراک و انتشار رویدادها بین اجزای مختلف
    سیستم است. هر رویداد می‌تواند چندین شنونده (listener) داشته باشد.
    """

    def __init__(self) -> None:
        """مقداردهی اولیه با لیست خالی شنوندگان."""
        self._listeners: dict[str, list[AsyncCallback]] = {}
        logger.debug("EventBus مقداردهی شد")

    def on(self, event_name: str, callback: AsyncCallback) -> None:
        """
        ثبت یک شنونده برای رویداد مشخص

        Args:
            event_name: نام رویداد (مثلاً 'state_changed')
            callback: تابع ناهمزمان که هنگام انتشار رویداد فراخوانی می‌شود
        """
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        if callback not in self._listeners[event_name]:
            self._listeners[event_name].append(callback)
            logger.debug("شنونده جدید برای رویداد '%s' ثبت شد", event_name)

    def off(self, event_name: str, callback: AsyncCallback) -> None:
        """
        حذف یک شنونده از رویداد مشخص

        Args:
            event_name: نام رویداد
            callback: تابع شنونده‌ای که باید حذف شود
        """
        if event_name in self._listeners:
            try:
                self._listeners[event_name].remove(callback)
                logger.debug("شنونده از رویداد '%s' حذف شد", event_name)
            except ValueError:
                logger.warning(
                    "شنونده برای رویداد '%s' یافت نشد", event_name
                )

    async def emit(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """
        انتشار یک رویداد و فراخوانی تمام شنوندگان ثبت‌شده

        تمام شنوندگان به صورت همزمان (concurrent) اجرا می‌شوند.
        خطا در یک شنونده مانع اجرای بقیه نمی‌شود.

        Args:
            event_name: نام رویداد
            data: داده‌های مربوط به رویداد
        """
        if data is None:
            data = {}

        data["event"] = event_name
        listeners = self._listeners.get(event_name, [])

        if not listeners:
            logger.debug("رویداد '%s' منتشر شد ولی شنونده‌ای ندارد", event_name)
            return

        logger.debug(
            "رویداد '%s' به %d شنونده ارسال می‌شود",
            event_name,
            len(listeners),
        )

        tasks = []
        for cb in listeners:
            tasks.append(self._safe_call(cb, event_name, data))

        await asyncio.gather(*tasks)

    @staticmethod
    async def _safe_call(
        callback: AsyncCallback,
        event_name: str,
        data: dict[str, Any],
    ) -> None:
        """
        فراخوانی امن یک شنونده با مدیریت خطا

        Args:
            callback: تابع شنونده
            event_name: نام رویداد (برای لاگ)
            data: داده‌های رویداد
        """
        try:
            await callback(data)
        except Exception:
            logger.exception(
                "خطا در شنونده رویداد '%s'", event_name
            )

    def clear(self, event_name: str | None = None) -> None:
        """
        پاک‌سازی شنوندگان

        Args:
            event_name: اگر مشخص شود فقط شنوندگان آن رویداد پاک می‌شوند.
                        اگر None باشد تمام شنوندگان پاک می‌شوند.
        """
        if event_name is None:
            self._listeners.clear()
            logger.debug("تمام شنوندگان پاک شدند")
        elif event_name in self._listeners:
            del self._listeners[event_name]
            logger.debug("شنوندگان رویداد '%s' پاک شدند", event_name)

    @property
    def registered_events(self) -> list[str]:
        """لیست رویدادهایی که حداقل یک شنونده دارند."""
        return list(self._listeners.keys())
