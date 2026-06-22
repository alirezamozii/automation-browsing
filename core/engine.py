# -*- coding: utf-8 -*-
"""
موتور اجرای گردش کار (Workflow Engine)

این ماژول موتور اصلی اجرای گردش کارها را پیاده‌سازی می‌کند.
موتور از ماشین حالت، سیستم رویداد و زمان‌بند برای اجرای ترتیبی
گام‌های گردش کار استفاده می‌کند.
"""

import asyncio
import logging
import traceback
from datetime import datetime, timezone
from typing import Any

from config import MAX_RETRIES, SCREENSHOTS_DIR
from core.state_machine import StateMachine, WorkflowState
from core.events import EventBus
from core.scheduler import StepScheduler

logger = logging.getLogger("automation_platform.engine")


class WorkflowEngine:
    """
    موتور اجرای گردش کار

    این کلاس مسئول اجرای کامل یک گردش کار شامل مدیریت مراحل،
    تلاش مجدد در صورت خطا، توقف/ادامه و ارسال رویدادها است.
    """

    def __init__(
        self,
        browser_controller: Any | None = None,
        event_bus: EventBus | None = None,
        scheduler: StepScheduler | None = None,
    ) -> None:
        """
        مقداردهی اولیه موتور

        Args:
            browser_controller: نمونه BrowserController (توسط عامل دیگر ساخته می‌شود)
            event_bus: سیستم رویداد. اگر None باشد یک نمونه جدید ساخته می‌شود.
            scheduler: زمان‌بند گام‌ها. اگر None باشد با مقادیر پیش‌فرض ساخته می‌شود.
        """
        self.browser = browser_controller
        self.state_machine = StateMachine()
        self.event_bus = event_bus or EventBus()
        self.scheduler = scheduler or StepScheduler()

        self._current_workflow: Any | None = None
        self._current_step_index: int = 0
        self._input_data: dict[str, Any] = {}
        self._is_running: bool = False
        self._task: asyncio.Task[None] | None = None

        logger.info("موتور گردش کار مقداردهی شد")

    # ──────────────────────────────────────────────
    #  شروع / توقف / ادامه
    # ──────────────────────────────────────────────

    async def start(
        self,
        workflow: Any,
        input_data: dict[str, Any] | None = None,
    ) -> None:
        """
        شروع اجرای یک گردش کار

        Args:
            workflow: نمونه‌ای از BaseWorkflow
            input_data: داده‌های ورودی اختیاری
        """
        if self._is_running:
            logger.warning("گردش کار در حال اجراست، نمی‌توان شروع جدید کرد")
            return

        self._current_workflow = workflow
        self._input_data = input_data or {}
        self._current_step_index = 0
        self._is_running = True

        self.state_machine = StateMachine()  # بازنشانی حالت
        self.state_machine.transition(WorkflowState.STARTING)

        await self.event_bus.emit("state_changed", {
            "old_state": WorkflowState.IDLE.value,
            "new_state": WorkflowState.STARTING.value,
            "workflow": workflow.name,
        })

        logger.info("شروع گردش کار: '%s'", workflow.name)
        self._task = asyncio.create_task(self._run_workflow())

    async def pause(self) -> None:
        """توقف موقت اجرای گردش کار."""
        if not self._is_running:
            logger.warning("گردش کاری در حال اجرا نیست")
            return

        self.state_machine.pause()
        self.scheduler.pause()

        await self.event_bus.emit("paused", {
            "state": self.state_machine.current_state.value,
            "step_index": self._current_step_index,
        })
        logger.info("گردش کار متوقف شد")

    async def resume(self) -> None:
        """ادامه اجرای گردش کار پس از توقف."""
        if self.state_machine.current_state != WorkflowState.PAUSED:
            logger.warning("گردش کار در حالت توقف نیست")
            return

        self.state_machine.resume()
        self.scheduler.resume()

        await self.event_bus.emit("resumed", {
            "state": self.state_machine.current_state.value,
            "step_index": self._current_step_index,
        })
        logger.info("گردش کار ادامه یافت")

    async def stop(self) -> None:
        """توقف کامل اجرای گردش کار."""
        self._is_running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # بازنشانی به IDLE
        try:
            if self.state_machine.current_state != WorkflowState.IDLE:
                if self.state_machine.current_state == WorkflowState.PAUSED:
                    self.state_machine.resume()
                # حرکت به DONE سپس IDLE اگر ممکن باشد
                if self.state_machine.can_transition(
                    self.state_machine.current_state, WorkflowState.DONE
                ):
                    self.state_machine.transition(WorkflowState.DONE)
                    self.state_machine.transition(WorkflowState.IDLE)
                elif self.state_machine.can_transition(
                    self.state_machine.current_state, WorkflowState.ERROR
                ):
                    self.state_machine.transition(WorkflowState.ERROR)
                    self.state_machine.transition(WorkflowState.IDLE)
        except ValueError:
            pass  # اگر انتقال ممکن نبود نادیده بگیر

        self.scheduler.resume()  # آزادسازی هر انتظار باقی‌مانده
        self._current_workflow = None
        logger.info("گردش کار متوقف شد")

    # ──────────────────────────────────────────────
    #  حلقه اصلی اجرا
    # ──────────────────────────────────────────────

    async def _run_workflow(self) -> None:
        """حلقه اصلی اجرای ترتیبی گام‌های گردش کار."""
        workflow = self._current_workflow
        if workflow is None:
            return

        try:
            steps = workflow.steps
            for idx, step in enumerate(steps):
                if not self._is_running:
                    break

                self._current_step_index = idx

                await self.event_bus.emit("step_started", {
                    "step_name": step.name,
                    "step_index": idx,
                    "total_steps": len(steps),
                })

                # تغییر حالت ماشین به حالت مرتبط با این گام
                if self.state_machine.can_transition(
                    self.state_machine.current_state, step.state
                ):
                    old = self.state_machine.current_state
                    self.state_machine.transition(step.state)
                    await self.event_bus.emit("state_changed", {
                        "old_state": old.value,
                        "new_state": step.state.value,
                    })

                # اجرای گام با منطق تلاش مجدد
                await self._execute_step(step)

                await self.event_bus.emit("step_completed", {
                    "step_name": step.name,
                    "step_index": idx,
                })

                # تأخیر بین گام‌ها
                if idx < len(steps) - 1:
                    await self.scheduler.wait_between_steps()

            # اتمام موفق
            if self._is_running:
                if self.state_machine.can_transition(
                    self.state_machine.current_state, WorkflowState.DONE
                ):
                    self.state_machine.transition(WorkflowState.DONE)
                await self.event_bus.emit("workflow_done", {
                    "workflow": workflow.name,
                    "steps_completed": len(steps),
                })
                logger.info("گردش کار '%s' با موفقیت تکمیل شد", workflow.name)

        except asyncio.CancelledError:
            logger.info("گردش کار لغو شد")
            raise
        except Exception as exc:
            await self._on_error(exc, step=steps[self._current_step_index] if steps else None)
        finally:
            self._is_running = False

    # ──────────────────────────────────────────────
    #  اجرای تک‌گام با تلاش مجدد
    # ──────────────────────────────────────────────

    async def _execute_step(self, step: Any) -> None:
        """
        اجرای یک گام از گردش کار با پشتیبانی از تلاش مجدد

        Args:
            step: شیء WorkflowStep
        """
        max_retries = step.retry_count if hasattr(step, "retry_count") else MAX_RETRIES
        await self._retry_step(step, max_retries=max_retries)

    async def _retry_step(self, step: Any, max_retries: int = MAX_RETRIES) -> None:
        """
        اجرای یک گام با منطق تلاش مجدد

        Args:
            step: شیء WorkflowStep
            max_retries: حداکثر تعداد تلاش مجدد

        Raises:
            Exception: اگر تمام تلاش‌ها ناموفق باشند
        """
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(
                    "اجرای گام '%s' — تلاش %d/%d",
                    step.name,
                    attempt,
                    max_retries,
                )
                await self.scheduler.run_with_timeout(
                    step.action(self.browser, self._input_data)
                )
                return  # موفقیت‌آمیز
            except asyncio.TimeoutError:
                last_error = asyncio.TimeoutError(
                    f"گام '{step.name}' از محدودیت زمانی فراتر رفت"
                )
                logger.warning(
                    "تایم‌اوت گام '%s' — تلاش %d/%d",
                    step.name,
                    attempt,
                    max_retries,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "خطا در گام '%s' — تلاش %d/%d: %s",
                    step.name,
                    attempt,
                    max_retries,
                    str(exc),
                )

            # تأخیر نمایی بین تلاش‌ها
            if attempt < max_retries:
                backoff = 2 ** (attempt - 1)
                logger.debug("انتظار %d ثانیه قبل از تلاش مجدد", backoff)
                await asyncio.sleep(backoff)

        # تمام تلاش‌ها ناموفق بود
        if last_error is not None:
            raise last_error

    # ──────────────────────────────────────────────
    #  مدیریت خطا
    # ──────────────────────────────────────────────

    async def _on_error(self, error: Exception, step: Any | None = None) -> None:
        """
        مدیریت خطای رخ‌داده در حین اجرا

        عملیات: لاگ خطا → اسکرین‌شات → انتشار رویداد → توقف

        Args:
            error: استثنای رخ‌داده
            step: گامی که در آن خطا رخ داده (اختیاری)
        """
        step_name = step.name if step and hasattr(step, "name") else "unknown"
        logger.error("خطا در گام '%s': %s", step_name, str(error))
        logger.debug("جزئیات خطا:\n%s", traceback.format_exc())

        # تلاش برای اسکرین‌شات
        screenshot_path: str | None = None
        if self.browser is not None:
            try:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                filename = f"error_{step_name}_{timestamp}.png"
                screenshot_path = str(SCREENSHOTS_DIR / filename)
                # browser.screenshot() توسط عامل دیگر پیاده‌سازی می‌شود
                if hasattr(self.browser, "screenshot"):
                    await self.browser.screenshot(screenshot_path)
                    logger.info("اسکرین‌شات خطا ذخیره شد: %s", screenshot_path)
            except Exception:
                logger.warning("ذخیره اسکرین‌شات ناموفق بود")
                screenshot_path = None

        # انتقال به حالت خطا
        try:
            if self.state_machine.can_transition(
                self.state_machine.current_state, WorkflowState.ERROR
            ):
                self.state_machine.transition(WorkflowState.ERROR)
        except ValueError:
            pass

        # انتشار رویداد خطا
        await self.event_bus.emit("error", {
            "step_name": step_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "screenshot": screenshot_path,
            "step_index": self._current_step_index,
        })

        # توقف خودکار
        await self.event_bus.emit("paused", {
            "reason": "error",
            "step_name": step_name,
        })

    # ──────────────────────────────────────────────
    #  وضعیت
    # ──────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """
        دریافت وضعیت فعلی موتور

        Returns:
            دیکشنری حاوی اطلاعات وضعیت شامل حالت، نام گردش کار،
            شماره گام و وضعیت اجرا
        """
        return {
            "is_running": self._is_running,
            "state": self.state_machine.current_state.value,
            "previous_state": (
                self.state_machine.previous_state.value
                if self.state_machine.previous_state
                else None
            ),
            "workflow_name": (
                self._current_workflow.name
                if self._current_workflow
                else None
            ),
            "current_step_index": self._current_step_index,
            "scheduler_paused": self.scheduler.is_paused,
        }
