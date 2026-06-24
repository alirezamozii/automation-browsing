# -*- coding: utf-8 -*-
"""
کلاس پایه گردش کار و گام گردش کار

هر گردش کار سفارشی باید از BaseWorkflow ارث‌بری کند و
متد execute را پیاده‌سازی کند.

WorkflowStep اکنون از قابلیت‌های بیشتری پشتیبانی می‌کند:
  - timeout_override: تایم‌اوت اختصاصی برای این گام
  - skip_if: تابع async که اگر True برگرداند گام skip می‌شود
  - description: توضیح کوتاه قابل نمایش در UI
  - tags: برچسب‌ها برای فیلتر و گروه‌بندی
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from core.state_machine import WorkflowState

logger = logging.getLogger("automation_platform.workflows.base")

# امضای تابع action یک گام
StepAction = Callable[[Any, dict[str, Any]], Coroutine[Any, Any, None]]

# امضای تابع skip_if — browser و data می‌گیرد، bool برمی‌گرداند
SkipCondition = Callable[[Any, dict[str, Any]], Coroutine[Any, Any, bool]]


@dataclass
class WorkflowStep:
    """
    یک گام از گردش کار.

    Attributes:
        name           : نام یکتا (نمایش در لاگ و UI)
        state          : حالت ماشین حالت هنگام اجرای این گام
        action         : تابع async(browser, data) -> None
        retry_count    : تعداد تلاش مجدد در صورت خطا (پیش‌فرض ۳)
        timeout_override: اگر مشخص شود، scheduler از این timeout به جای پیش‌فرض استفاده می‌کند
        skip_if        : async(browser, data) -> bool — اگر True برگرداند گام skip می‌شود
        description    : توضیح کوتاه قابل نمایش در UI / لاگ
        tags           : برچسب‌ها برای دسته‌بندی (مثلاً ["login", "critical"])

    Examples:
        # گام ساده
        WorkflowStep(name="open_site", state=WorkflowState.NAVIGATING, action=self._open)

        # گام با skip_if — اگر کاربر لاگین باشد login را رد کن
        WorkflowStep(
            name="login",
            state=WorkflowState.LOGIN,
            action=self._login,
            skip_if=lambda b, d: b.is_visible("#user-menu"),
        )

        # گام با تایم‌اوت اختصاصی ۶۰ ثانیه
        WorkflowStep(
            name="heavy_export",
            state=WorkflowState.SAVING,
            action=self._export,
            timeout_override=60.0,
        )
    """

    name: str
    state: WorkflowState
    action: StepAction
    retry_count: int = 3
    timeout_override: float | None = None
    skip_if: SkipCondition | None = None
    description: str = ""
    tags: list[str] = field(default_factory=list)


class BaseWorkflow(ABC):
    """
    کلاس پایه انتزاعی برای تمام گردش‌کارها.

    زیرکلاس‌ها باید:
      1. در __init__ مقادیر _name، _description و _steps را تنظیم کنند.
      2. متد execute را پیاده‌سازی کنند.

    قابلیت‌های آماده:
      - get_current_step_index(url) — پرش هوشمند بر اساس URL
      - to_dict() — سریال‌سازی برای ذخیره / ارسال به UI
    """

    def __init__(self) -> None:
        self._name: str = "unnamed_workflow"
        self._description: str = ""
        self._steps: list[WorkflowStep] = []
        self._page_patterns: dict[str, str] = {}
        # داده‌های خروجی که workflow می‌تواند برای گام‌های بعدی ذخیره کند
        self._output: dict[str, Any] = {}

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def steps(self) -> list[WorkflowStep]:
        return self._steps

    @property
    def page_patterns(self) -> dict[str, str]:
        return self._page_patterns

    @property
    def output(self) -> dict[str, Any]:
        """داده‌هایی که workflow در طول اجرا جمع‌آوری کرده (مثلاً URL، عنوان، ...)."""
        return self._output

    # ── Abstract ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def execute(
        self,
        browser: Any,
        state: WorkflowState,
        data: dict[str, Any],
    ) -> None:
        """
        اجرای مستقیم workflow (بدون engine).
        Engine از steps استفاده می‌کند، این متد برای تست مستقیم است.
        """
        ...

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_current_step_index(self, detected_page: str) -> int:
        """
        تشخیص شماره گام مناسب بر اساس URL فعلی.
        Engine از این برای پرش هوشمند استفاده می‌کند.
        """
        for idx, step in enumerate(self._steps):
            pattern = self._page_patterns.get(step.name)
            if pattern and pattern in detected_page:
                logger.debug("URL '%s' → گام %d ('%s')", detected_page, idx, step.name)
                return idx
        return 0

    def get_steps_by_tag(self, tag: str) -> list[WorkflowStep]:
        """برگرداندن گام‌هایی که دارای tag مشخص هستند."""
        return [s for s in self._steps if tag in s.tags]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self._name,
            "description": self._description,
            "steps": [
                {
                    "name": s.name,
                    "state": s.state.value,
                    "retry_count": s.retry_count,
                    "description": s.description,
                    "tags": s.tags,
                    "has_skip_condition": s.skip_if is not None,
                    "timeout_override": s.timeout_override,
                }
                for s in self._steps
            ],
            "page_patterns": self._page_patterns,
        }
