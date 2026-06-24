# -*- coding: utf-8 -*-
"""
کلاس پایه گردش کار و گام گردش کار

این ماژول کلاس‌های انتزاعی پایه برای تعریف گردش‌کارها و گام‌های آنها
را فراهم می‌کند. تمام گردش‌کارهای سفارشی باید از BaseWorkflow ارث‌بری کنند.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

from core.state_machine import WorkflowState

logger = logging.getLogger("automation_platform.workflows.base")

# نوع اکشن: تابع ناهمزمان که browser و data دریافت می‌کند
StepAction = Callable[[Any, dict[str, Any]], Coroutine[Any, Any, None]]


@dataclass
class WorkflowStep:
    """
    یک گام از گردش کار

    هر گام شامل نام، حالت مرتبط در ماشین حالت، تابع اجرایی
    و تعداد تلاش مجدد در صورت خطا است.

    Attributes:
        name: نام توصیفی گام
        state: حالت ماشین حالت مرتبط با این گام
        action: تابع ناهمزمان اجرایی — امضا: (browser, data) -> None
        retry_count: حداکثر تعداد تلاش مجدد (پیش‌فرض ۳)
    """

    name: str
    state: WorkflowState
    action: StepAction
    retry_count: int = 3


class BaseWorkflow(ABC):
    """
    کلاس پایه انتزاعی برای تمام گردش‌کارها

    هر گردش کار سفارشی باید از این کلاس ارث‌بری کرده و
    متد execute را پیاده‌سازی کند. لیست گام‌ها (steps) باید
    در __init__ مقداردهی شوند.
    """

    def __init__(self) -> None:
        """مقداردهی اولیه با مقادیر پیش‌فرض."""
        self._name: str = "unnamed_workflow"
        self._description: str = ""
        self._steps: list[WorkflowStep] = []
        self._page_patterns: dict[str, str] = {}

    # ──────────── خصوصیات ────────────

    @property
    def name(self) -> str:
        """نام یکتای گردش کار."""
        return self._name

    @property
    def description(self) -> str:
        """توضیحات گردش کار."""
        return self._description

    @property
    def steps(self) -> list[WorkflowStep]:
        """لیست گام‌های گردش کار به ترتیب اجرا."""
        return self._steps

    @property
    def page_patterns(self) -> dict[str, str]:
        """
        الگوهای URL صفحات مرتبط با گردش کار

        کلید: نام صفحه، مقدار: الگوی regex یا glob برای URL
        """
        return self._page_patterns

    # ──────────── متدهای انتزاعی ────────────

    @abstractmethod
    async def execute(
        self,
        browser: Any,
        state: WorkflowState,
        data: dict[str, Any],
    ) -> None:
        """
        اجرای کامل گردش کار

        این متد باید توسط کلاس‌های فرزند پیاده‌سازی شود.
        معمولاً موتور از لیست steps استفاده می‌کند، ولی این متد
        برای اجرای مستقیم هم قابل استفاده است.

        Args:
            browser: نمونه BrowserController
            state: حالت فعلی ماشین حالت
            data: داده‌های ورودی/خروجی گردش کار
        """
        ...

    # ──────────── متدهای کمکی ────────────

    def get_current_step_index(self, detected_page: str) -> int:
        """
        تشخیص شماره گام فعلی بر اساس صفحه شناسایی‌شده

        با مقایسه URL/عنوان صفحه با الگوهای ثبت‌شده، شماره گامی
        که باید از آن ادامه داد را بازمی‌گرداند.

        Args:
            detected_page: URL یا عنوان صفحه شناسایی‌شده

        Returns:
            شماره گام (0-indexed). اگر پیدا نشد 0 برمی‌گرداند.
        """
        for idx, step in enumerate(self._steps):
            pattern_key = step.name
            if pattern_key in self._page_patterns:
                pattern = self._page_patterns[pattern_key]
                if pattern in detected_page:
                    logger.debug(
                        "صفحه '%s' با گام %d ('%s') مطابقت دارد",
                        detected_page,
                        idx,
                        step.name,
                    )
                    return idx

        logger.debug("صفحه '%s' با هیچ گامی مطابقت ندارد، بازگشت به 0", detected_page)
        return 0

    def to_dict(self) -> dict[str, Any]:
        """
        تبدیل اطلاعات گردش کار به دیکشنری

        Returns:
            دیکشنری شامل نام، توضیحات و لیست گام‌ها
        """
        return {
            "name": self._name,
            "description": self._description,
            "steps": [
                {
                    "name": s.name,
                    "state": s.state.value,
                    "retry_count": s.retry_count,
                }
                for s in self._steps
            ],
            "page_patterns": self._page_patterns,
        }
