# -*- coding: utf-8 -*-
"""
ماشین حالت (State Machine) گردش کار

این ماژول یک ماشین حالت محدود (FSM) برای مدیریت مراحل مختلف اجرای
گردش کار فراهم می‌کند. انتقال بین حالات بر اساس ماتریس انتقال
تعریف‌شده اعتبارسنجی می‌شود.
"""

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger("automation_platform.state_machine")


class WorkflowState(str, Enum):
    """
    حالات مختلف گردش کار

    هر گردش کار در هر لحظه در یکی از این حالات قرار دارد.
    """

    IDLE = "idle"
    STARTING = "starting"
    LOGIN = "login"
    NAVIGATING = "navigating"
    SEARCHING = "searching"
    OPEN_FORM = "open_form"
    FILL_FORM = "fill_form"
    SAVING = "saving"
    VERIFYING = "verifying"
    DONE = "done"
    ERROR = "error"
    PAUSED = "paused"


# ──────────────────────────────────────────────
#  ماتریس انتقال حالات مجاز
#  کلید: حالت مبدأ → مقدار: مجموعه حالات مقصد مجاز
# ──────────────────────────────────────────────
TRANSITION_MATRIX: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.IDLE: {
        WorkflowState.STARTING,
    },
    WorkflowState.STARTING: {
        WorkflowState.LOGIN,
        WorkflowState.NAVIGATING,
        WorkflowState.ERROR,
    },
    WorkflowState.LOGIN: {
        WorkflowState.NAVIGATING,
        WorkflowState.ERROR,
        WorkflowState.PAUSED,
    },
    WorkflowState.NAVIGATING: {
        WorkflowState.SEARCHING,
        WorkflowState.OPEN_FORM,
        WorkflowState.LOGIN,
        WorkflowState.ERROR,
        WorkflowState.PAUSED,
        WorkflowState.DONE,
    },
    WorkflowState.SEARCHING: {
        WorkflowState.NAVIGATING,
        WorkflowState.OPEN_FORM,
        WorkflowState.ERROR,
        WorkflowState.PAUSED,
        WorkflowState.DONE,
    },
    WorkflowState.OPEN_FORM: {
        WorkflowState.FILL_FORM,
        WorkflowState.NAVIGATING,
        WorkflowState.ERROR,
        WorkflowState.PAUSED,
    },
    WorkflowState.FILL_FORM: {
        WorkflowState.SAVING,
        WorkflowState.OPEN_FORM,
        WorkflowState.ERROR,
        WorkflowState.PAUSED,
    },
    WorkflowState.SAVING: {
        WorkflowState.VERIFYING,
        WorkflowState.ERROR,
        WorkflowState.PAUSED,
    },
    WorkflowState.VERIFYING: {
        WorkflowState.NAVIGATING,
        WorkflowState.DONE,
        WorkflowState.ERROR,
        WorkflowState.PAUSED,
    },
    WorkflowState.DONE: {
        WorkflowState.IDLE,
    },
    WorkflowState.ERROR: {
        WorkflowState.IDLE,
        WorkflowState.STARTING,
        WorkflowState.PAUSED,
    },
    WorkflowState.PAUSED: {
        # resume به حالت قبلی برمی‌گردد — هر حالتی مجاز است
        WorkflowState.IDLE,
        WorkflowState.STARTING,
        WorkflowState.LOGIN,
        WorkflowState.NAVIGATING,
        WorkflowState.SEARCHING,
        WorkflowState.OPEN_FORM,
        WorkflowState.FILL_FORM,
        WorkflowState.SAVING,
        WorkflowState.VERIFYING,
        WorkflowState.ERROR,
    },
}


class StateMachine:
    """
    ماشین حالت گردش کار

    این کلاس انتقال بین حالات را مدیریت می‌کند و فقط انتقال‌های مجاز
    بر اساس ماتریس تعریف‌شده را اجازه می‌دهد.
    """

    def __init__(self, initial_state: WorkflowState = WorkflowState.IDLE) -> None:
        """
        مقداردهی اولیه ماشین حالت

        Args:
            initial_state: حالت اولیه (پیش‌فرض: IDLE)
        """
        self._current_state: WorkflowState = initial_state
        self._previous_state: WorkflowState | None = None
        self._state_before_pause: WorkflowState | None = None
        logger.info("ماشین حالت با حالت اولیه '%s' ایجاد شد", initial_state.value)

    # ──────────── خصوصیات ────────────

    @property
    def current_state(self) -> WorkflowState:
        """حالت فعلی ماشین."""
        return self._current_state

    @property
    def previous_state(self) -> WorkflowState | None:
        """حالت قبلی ماشین (None اگر هنوز انتقالی رخ نداده)."""
        return self._previous_state

    # ──────────── اعتبارسنجی ────────────

    def can_transition(self, from_state: WorkflowState, to_state: WorkflowState) -> bool:
        """
        بررسی مجاز بودن انتقال بین دو حالت

        Args:
            from_state: حالت مبدأ
            to_state: حالت مقصد

        Returns:
            True اگر انتقال مجاز باشد
        """
        allowed = TRANSITION_MATRIX.get(from_state, set())
        return to_state in allowed

    # ──────────── انتقال حالت ────────────

    def transition(self, new_state: WorkflowState) -> WorkflowState:
        """
        انتقال به حالت جدید با اعتبارسنجی

        Args:
            new_state: حالت مقصد

        Returns:
            حالت جدید فعلی

        Raises:
            ValueError: اگر انتقال مجاز نباشد
        """
        if not self.can_transition(self._current_state, new_state):
            msg = (
                f"انتقال غیرمجاز: '{self._current_state.value}' → '{new_state.value}'. "
                f"انتقال‌های مجاز: {[s.value for s in self.get_allowed_transitions()]}"
            )
            logger.error(msg)
            raise ValueError(msg)

        old = self._current_state
        self._previous_state = old
        self._current_state = new_state
        logger.info("انتقال حالت: '%s' → '%s'", old.value, new_state.value)
        return self._current_state

    # ──────────── توقف و ادامه ────────────

    def pause(self) -> WorkflowState:
        """
        توقف موقت گردش کار

        حالت فعلی ذخیره می‌شود تا هنگام ادامه بازیابی شود.

        Returns:
            حالت PAUSED

        Raises:
            ValueError: اگر انتقال به PAUSED مجاز نباشد
        """
        if self._current_state == WorkflowState.PAUSED:
            logger.warning("ماشین حالت قبلاً متوقف شده است")
            return self._current_state

        self._state_before_pause = self._current_state
        return self.transition(WorkflowState.PAUSED)

    def resume(self) -> WorkflowState:
        """
        ادامه گردش کار از حالت قبل از توقف

        Returns:
            حالت بازیابی‌شده

        Raises:
            ValueError: اگر ماشین در حالت PAUSED نباشد یا حالت قبلی ذخیره نشده باشد
        """
        if self._current_state != WorkflowState.PAUSED:
            msg = "ماشین حالت در حالت PAUSED نیست، نمی‌توان ادامه داد"
            logger.error(msg)
            raise ValueError(msg)

        if self._state_before_pause is None:
            msg = "حالت قبل از توقف ذخیره نشده، نمی‌توان ادامه داد"
            logger.error(msg)
            raise ValueError(msg)

        target = self._state_before_pause
        self._state_before_pause = None
        return self.transition(target)

    # ──────────── کمکی ────────────

    def get_allowed_transitions(self) -> list[WorkflowState]:
        """
        لیست حالات مقصد مجاز از حالت فعلی

        Returns:
            لیست حالات مجاز
        """
        return sorted(
            TRANSITION_MATRIX.get(self._current_state, set()),
            key=lambda s: s.value,
        )

    # ──────────── سریال‌سازی ────────────

    def to_dict(self) -> dict[str, Any]:
        """
        تبدیل وضعیت ماشین به دیکشنری (برای ذخیره یا ارسال)

        Returns:
            دیکشنری شامل حالت فعلی، قبلی و حالت قبل از توقف
        """
        return {
            "current_state": self._current_state.value,
            "previous_state": self._previous_state.value if self._previous_state else None,
            "state_before_pause": (
                self._state_before_pause.value if self._state_before_pause else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StateMachine":
        """
        بازسازی ماشین حالت از دیکشنری

        Args:
            data: دیکشنری حاوی وضعیت ذخیره‌شده

        Returns:
            نمونه جدید StateMachine
        """
        sm = cls(initial_state=WorkflowState(data["current_state"]))
        if data.get("previous_state"):
            sm._previous_state = WorkflowState(data["previous_state"])
        if data.get("state_before_pause"):
            sm._state_before_pause = WorkflowState(data["state_before_pause"])
        return sm

    def __repr__(self) -> str:
        return (
            f"StateMachine(current={self._current_state.value!r}, "
            f"previous={self._previous_state.value if self._previous_state else None!r})"
        )
