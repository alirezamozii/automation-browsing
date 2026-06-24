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
import sys
import asyncio
from pathlib import Path
from typing import Any, Type

from workflows.base import BaseWorkflow, WorkflowStep
from core.state_machine import WorkflowState

logger = logging.getLogger("automation_platform.workflows.registry")


class ScriptTemplateWorkflow(BaseWorkflow):
    """
    گردش کار پویا برای اجرای اسکریپت‌های قالب (Python, JS, TS, Java)
    """
    file_path: Path = None

    def __init__(self) -> None:
        super().__init__()
        if not self.file_path:
            raise ValueError("file_path class attribute must be set")
            
        self._name = f"template_{self.file_path.stem}"
        self._description = f"اجرای اسکریپت {self.file_path.name}"
        self._steps = [
            WorkflowStep(
                name="run_script",
                state=WorkflowState.NAVIGATING,
                action=self._step_run_script,
                retry_count=1,
            )
        ]

    async def execute(
        self,
        browser: Any,
        state: WorkflowState,
        data: dict[str, Any],
    ) -> None:
        await self._step_run_script(browser, data)

    async def _step_run_script(self, browser: Any, data: dict[str, Any]) -> None:
        suffix = self.file_path.suffix.lower()
        
        # تعیین دستور اجرا بر اساس پسوند فایل
        if suffix == ".py":
            cmd = [sys.executable, str(self.file_path)]
        elif suffix == ".js":
            cmd = ["node", str(self.file_path)]
        elif suffix in (".ts", ".tsx"):
            # اجرای فایل‌های TypeScript با npx tsx به صورت زنده و بدون نیاز به کانفیگ
            cmd = ["npx", "tsx", str(self.file_path)]
        elif suffix == ".java":
            cmd = ["java", str(self.file_path)]
        else:
            raise ValueError(f"پسوند فایل {suffix} پشتیبانی نمی‌شود")

        logger.info("در حال اجرای دستور: %s", " ".join(cmd))
        
        # ارسال لاگ شروع اجرا
        if hasattr(browser, "event_bus") and browser.event_bus:
            await browser.event_bus.emit("action_logged", {
                "workflow": self.name,
                "state": "navigating",
                "step_name": "run_script",
                "status": "info",
                "message": f"شروع اجرای اسکریپت {self.file_path.name}...",
            })

        # اجرای اسکریپت در یک پروسه جداگانه و ضبط لاگ‌ها
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def read_stream(stream, is_stderr=False):
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode('utf-8', errors='replace').strip()
                if text:
                    log_status = "warning" if is_stderr else "info"
                    
                    # استخراج مسیر تصویر (Screenshot) از خروجی لاگ اسکریپت
                    screenshot_path = None
                    if "[SCREENSHOT]" in text:
                        parts = text.split("[SCREENSHOT]")
                        screenshot_path = parts[1].strip()
                        text = parts[0].strip() or "تصویر صفحه ثبت شد"
                    
                    # ارسال فوری لاگ خروجی اسکریپت به EventBus جهت نمایش در داشبورد
                    if hasattr(browser, "event_bus") and browser.event_bus:
                        log_data = {
                            "workflow": self.name,
                            "state": "navigating",
                            "step_name": "run_script",
                            "status": log_status,
                            "message": text,
                        }
                        if screenshot_path:
                            log_data["screenshot"] = screenshot_path
                            
                        await browser.event_bus.emit("action_logged", log_data)
                    logger.info(f"[{self.file_path.name}] {text}")

        # خواندن همزمان خروجی‌های استاندارد و خطا
        await asyncio.gather(
            read_stream(process.stdout, is_stderr=False),
            read_stream(process.stderr, is_stderr=True),
        )

        await process.wait()
        
        if process.returncode != 0:
            raise RuntimeError(f"اسکریپت {self.file_path.name} با کد خروج {process.returncode} خاتمه یافت")
            
        if hasattr(browser, "event_bus") and browser.event_bus:
            await browser.event_bus.emit("action_logged", {
                "workflow": self.name,
                "state": "navigating",
                "step_name": "run_script",
                "status": "success",
                "message": f"اسکریپت {self.file_path.name} با موفقیت اجرا شد",
            })


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
        کشف خودکار گردش‌کارها از پوشه workflows و همچنین پوشه قالب‌های اسکریپت
        """
        import sys
        
        # تشخیص اینکه آیا نرم‌افزار به صورت EXE اجرا شده یا معمولی
        if getattr(sys, 'frozen', False):
            # مسیر موقت در حالت EXE (PyInstaller)
            workflows_dir = Path(sys._MEIPASS) / "workflows"
        else:
            workflows_dir = Path(__file__).parent
            
        count = 0

        logger.info("شروع کشف خودکار از: %s", workflows_dir)

        # ۱. بارگذاری کلاس‌های گردش کار استاندارد پایتون
        for finder, module_name, is_pkg in pkgutil.iter_modules([str(workflows_dir)]):
            # نادیده گرفتن __init__, base, registry, workflow_template, archive
            if module_name in ("base", "registry", "__init__", "workflow_template", "archive"):
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
                    and attr is not ScriptTemplateWorkflow
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

        # ۲. بارگذاری اسکریپت‌های متفرقه از پوشه workflow_template
        template_dir = workflows_dir / "workflow_template"
        if template_dir.exists() and template_dir.is_dir():
            for file_path in template_dir.iterdir():
                if file_path.is_file() and file_path.name != ".gitkeep":
                    suffix = file_path.suffix.lower()
                    if suffix in (".py", ".js", ".ts", ".tsx", ".java"):
                        try:
                            # اگر فایل پایتون است، ابتدا بررسی می‌کنیم آیا کلاس گردش کار بومی دارد یا خیر
                            if suffix == ".py":
                                import importlib.util
                                spec = importlib.util.spec_from_file_location(
                                    f"workflows.workflow_template.{file_path.stem}",
                                    str(file_path)
                                )
                                if spec and spec.loader:
                                    module = importlib.util.module_from_spec(spec)
                                    sys.modules[module.__name__] = module
                                    spec.loader.exec_module(module)
                                    
                                    found_native = False
                                    for attr_name in dir(module):
                                        attr = getattr(module, attr_name)
                                        if (
                                            inspect.isclass(attr)
                                            and issubclass(attr, BaseWorkflow)
                                            and attr is not BaseWorkflow
                                            and attr is not ScriptTemplateWorkflow
                                            and not inspect.isabstract(attr)
                                        ):
                                            self.register(attr)
                                            count += 1
                                            found_native = True
                                            
                                    if found_native:
                                        continue

                            # ساخت یک کلاس پویا برای ثبت این اسکریپت (به عنوان اسکریپت خارجی)
                            class_name = f"TemplateWorkflow_{file_path.stem}_{suffix[1:]}"
                            dynamic_class = type(
                                class_name,
                                (ScriptTemplateWorkflow,),
                                {
                                    "file_path": file_path,
                                }
                            )
                            self.register(dynamic_class)
                            count += 1
                        except Exception:
                            logger.exception("خطا در بارگذاری قالب اسکریپت '%s'", file_path.name)

        logger.info("%d گردش کار کشف و ثبت شد", count)
        return count

    def __contains__(self, name: str) -> bool:
        return name in self._workflows

    def __len__(self) -> int:
        return len(self._workflows)


    def __contains__(self, name: str) -> bool:
        return name in self._workflows

    def __len__(self) -> int:
        return len(self._workflows)
