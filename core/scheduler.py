# -*- coding: utf-8 -*-
"""
زمان‌بند گام‌های گردش کار (Step Scheduler)

این ماژول مدیریت زمان‌بندی و تأخیر بین گام‌های مختلف یک گردش کار
را بر عهده دارد. از تأخیرهای قابل تنظیم و تصادفی برای شبیه‌سازی
رفتار طبیعی کاربر پشتیبانی می‌کند.
"""

import asyncio
import logging
import random
from typing import Any

logger = logging.getLogger("automation_platform.scheduler")


class StepScheduler:
    """
    زمان‌بند گام‌های گردش کار

    این کلاس تأخیر بین اجرای گام‌ها را مدیریت می‌کند و امکان
    شبیه‌سازی رفتار انسانی با تأخیرهای تصادفی را فراهم می‌سازد.
    """

    def __init__(
        self,
        base_delay: float = 1.0,
        jitter: float = 0.5,
        step_timeout: float = 30.0,
    ) -> None:
        """
        مقداردهی اولیه زمان‌بند

        Args:
            base_delay: تأخیر پایه بین گام‌ها (ثانیه)
            jitter: حداکثر تأخیر تصادفی اضافی (ثانیه)
            step_timeout: حداکثر زمان مجاز اجرای هر گام (ثانیه)
        """
        self.base_delay: float = base_delay
        self.jitter: float = jitter
        self.step_timeout: float = step_timeout
        self._paused: bool = False
        self._pause_event: asyncio.Event = asyncio.Event()
        self._pause_event.set()  # شروع در حالت غیرمتوقف
        logger.debug(
            "زمان‌بند ایجاد شد: base_delay=%.1fs, jitter=%.1fs, timeout=%.1fs",
            base_delay,
            jitter,
            step_timeout,
        )

    async def wait_between_steps(self) -> None:
        """
        انتظار بین اجرای دو گام متوالی

        اگر زمان‌بند متوقف شده باشد، تا زمان ادامه صبر می‌کند.
        سپس یک تأخیر تصادفی اعمال می‌شود.
        """
        # بررسی وضعیت توقف
        await self._pause_event.wait()

        delay = self.base_delay + random.uniform(0, self.jitter)
        logger.debug("انتظار بین گام‌ها: %.2f ثانیه", delay)
        await asyncio.sleep(delay)

    async def run_with_timeout(
        self,
        coro: Any,
        timeout: float | None = None,
    ) -> Any:
        """
        اجرای یک coroutine با محدودیت زمانی

        Args:
            coro: coroutine قابل اجرا
            timeout: زمان محدودیت (ثانیه). اگر None باشد از step_timeout استفاده می‌شود.

        Returns:
            نتیجه اجرای coroutine

        Raises:
            asyncio.TimeoutError: اگر اجرا بیش از حد مجاز طول بکشد
        """
        effective_timeout = timeout if timeout is not None else self.step_timeout
        logger.debug("اجرا با محدودیت زمانی %.1f ثانیه", effective_timeout)
        try:
            result = await asyncio.wait_for(coro, timeout=effective_timeout)
            return result
        except asyncio.TimeoutError:
            logger.error("اجرا از محدودیت زمانی %.1f ثانیه فراتر رفت", effective_timeout)
            raise

    def pause(self) -> None:
        """توقف زمان‌بند — گام‌های بعدی تا ادامه صبر می‌کنند."""
        self._paused = True
        self._pause_event.clear()
        logger.info("زمان‌بند متوقف شد")

    def resume(self) -> None:
        """ادامه زمان‌بند — گام‌های در انتظار آزاد می‌شوند."""
        self._paused = False
        self._pause_event.set()
        logger.info("زمان‌بند ادامه یافت")

    @property
    def is_paused(self) -> bool:
        """آیا زمان‌بند متوقف است؟"""
        return self._paused
