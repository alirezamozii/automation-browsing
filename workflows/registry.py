# -*- coding: utf-8 -*-
"""
ثبت‌کننده گردش‌کارها (Workflow Registry)

این ماژول مسئول ثبت، نگهداری و بازیابی گردش‌کارهای موجود است.
قابلیت کشف خودکار (auto-discovery) گردش‌کارها از پوشه workflows
را نیز دارد.
"""

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import Any, Type

from workflows.base import BaseWorkflow

logger = logging.getLogger("automation_platform.workflows.registry")


class WorkflowRegistry:
    """
    ثبت‌کننده مرکزی گردش‌کارها

    این کلاس تمام گردش‌کارهای ثبت‌شده را نگهداری می‌کند و
    امکان جستجو بر اساس نام و کشف خودکار را فراهم می‌سازد.
    """

    def __init__(self) -> None:
        """مقداردهی اولیه با دیکشنری خالی."""
        self._workflows: dict[str, Type[BaseWorkflow]] = {}
        logger.debug("WorkflowRegistry مقداردهی شد")

    def register(self, workflow_class: Type[BaseWorkflow]) -> None:
        """
        ثبت یک کلاس گردش کار

        Args:
            workflow_class: کلاس گردش کار (نه نمونه) که از BaseWorkflow ارث‌بری کرده

        Raises:
            TypeError: اگر کلاس از BaseWorkflow ارث‌بری نکرده باشد
        """
        if not (inspect.isclass(workflow_class) and issubclass(workflow_class, BaseWorkflow)):
            msg = f"'{workflow_class}' باید زیرکلاس BaseWorkflow باشد"
            logger.error(msg)
            raise TypeError(msg)

        # ساخت یک نمونه موقت برای دریافت نام
        instance = workflow_class()
        name = instance.name

        if name in self._workflows:
            logger.warning(
                "گردش کار '%s' قبلاً ثبت شده، جایگزین می‌شود", name
            )

        self._workflows[name] = workflow_class
        logger.info("گردش کار '%s' ثبت شد (%s)", name, workflow_class.__name__)

    def get(self, name: str) -> BaseWorkflow:
        """
        دریافت نمونه‌ای از گردش کار بر اساس نام

        Args:
            name: نام یکتای گردش کار

        Returns:
            نمونه جدید از گردش کار

        Raises:
            KeyError: اگر گردش کار با این نام ثبت نشده باشد
        """
        if name not in self._workflows:
            available = list(self._workflows.keys())
            msg = f"گردش کار '{name}' یافت نشد. موجود: {available}"
            logger.error(msg)
            raise KeyError(msg)

        return self._workflows[name]()

    def list_all(self) -> list[dict[str, Any]]:
        """
        لیست تمام گردش‌کارهای ثبت‌شده

        Returns:
            لیست دیکشنری‌ها شامل نام و توضیحات هر گردش کار
        """
        result: list[dict[str, Any]] = []
        for name, wf_class in self._workflows.items():
            instance = wf_class()
            result.append({
                "name": instance.name,
                "description": instance.description,
                "steps_count": len(instance.steps),
                "class": wf_class.__name__,
            })
        return result

    def auto_discover(self) -> int:
        """
        کشف خودکار گردش‌کارها از پوشه workflows

        تمام ماژول‌های پایتون درون پوشه workflows را بارگذاری کرده
        و هر کلاسی که زیرکلاس BaseWorkflow باشد (و انتزاعی نباشد)
        را ثبت می‌کند.

        Returns:
            تعداد گردش‌کارهای کشف و ثبت‌شده
        """
        workflows_dir = Path(__file__).parent
        count = 0

        logger.info("شروع کشف خودکار از: %s", workflows_dir)

        for finder, module_name, is_pkg in pkgutil.iter_modules([str(workflows_dir)]):
            # نادیده گرفتن __init__, base, registry
            if module_name in ("base", "registry", "__init__"):
                continue

            full_module_name = f"workflows.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
            except Exception:
                logger.exception("خطا در بارگذاری ماژول '%s'", full_module_name)
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, BaseWorkflow)
                    and attr is not BaseWorkflow
                    and not inspect.isabstract(attr)
                ):
                    try:
                        self.register(attr)
                        count += 1
                    except (TypeError, Exception):
                        logger.exception(
                            "خطا در ثبت کلاس '%s' از ماژول '%s'",
                            attr_name,
                            full_module_name,
                        )

        logger.info("%d گردش کار کشف و ثبت شد", count)
        return count

    def __contains__(self, name: str) -> bool:
        return name in self._workflows

    def __len__(self) -> int:
        return len(self._workflows)
