# -*- coding: utf-8 -*-
"""
گردش کار نمونه: جستجوی گوگل و دانلود تصویر

این یک گردش کار جایگزین (placeholder) برای نمایش ساختار است.
مراحل:
  1. باز کردن google.com
  2. تایپ 'moz' در کادر جستجو
  3. انتظار برای بارگذاری نتایج
  4. کلیک بر روی تب تصاویر (Images)
  5. دانلود اولین تصویر
"""

import logging
from pathlib import Path
from typing import Any

from config import SCREENSHOTS_DIR
from core.state_machine import WorkflowState
from workflows.base import BaseWorkflow, WorkflowStep
from locators.common import GoogleLocators

logger = logging.getLogger("automation_platform.workflows.sample")


class GoogleImageSearchWorkflow(BaseWorkflow):
    """
    گردش کار نمونه: جستجوی تصویر در گوگل

    این گردش کار به عنوان الگو و نمونه ساختاری طراحی شده است.
    مراحل آن شامل باز کردن گوگل، جستجوی یک عبارت، رفتن به تب
    تصاویر و دانلود اولین تصویر است.
    """

    def __init__(self) -> None:
        """مقداردهی اولیه با تعریف نام، توضیحات و گام‌ها."""
        super().__init__()

        self._name = "google_image_search"
        self._description = "جستجوی تصویر در گوگل و دانلود اولین نتیجه"

        self._locators = GoogleLocators()

        # الگوهای URL برای تشخیص صفحه
        self._page_patterns = {
            "open_google": "google.com",
            "search": "google.com/search",
            "go_to_images": "google.com/search",
            "download_image": "google.com/search?.*tbm=isch",
        }

        # تعریف گام‌ها
        self._steps = [
            WorkflowStep(
                name="open_google",
                state=WorkflowState.NAVIGATING,
                action=self._step_open_google,
                retry_count=3,
            ),
            WorkflowStep(
                name="search",
                state=WorkflowState.SEARCHING,
                action=self._step_type_search,
                retry_count=3,
            ),
            WorkflowStep(
                name="wait_results",
                state=WorkflowState.SEARCHING,
                action=self._step_wait_results,
                retry_count=2,
            ),
            WorkflowStep(
                name="go_to_images",
                state=WorkflowState.NAVIGATING,
                action=self._step_go_to_images,
                retry_count=3,
            ),
            WorkflowStep(
                name="download_image",
                state=WorkflowState.SAVING,
                action=self._step_download_image,
                retry_count=2,
            ),
        ]

    # ──────────────────────────────────────────────
    #  اجرای کامل (برای استفاده مستقیم)
    # ──────────────────────────────────────────────

    async def execute(
        self,
        browser: Any,
        state: WorkflowState,
        data: dict[str, Any],
    ) -> None:
        """
        اجرای کامل گردش کار به صورت ترتیبی

        این متد تمام گام‌ها را به ترتیب اجرا می‌کند.
        معمولاً موتور (Engine) از لیست steps استفاده می‌کند،
        ولی این متد برای اجرای مستقل هم قابل استفاده است.

        Args:
            browser: نمونه BrowserController
            state: حالت فعلی (استفاده نمی‌شود در این پیاده‌سازی)
            data: داده‌های ورودی
        """
        logger.info("شروع اجرای گردش کار '%s'", self._name)
        for step in self._steps:
            logger.info("اجرای گام: '%s'", step.name)
            await step.action(browser, data)
        logger.info("گردش کار '%s' تکمیل شد", self._name)

    # ──────────────────────────────────────────────
    #  گام‌های گردش کار
    # ──────────────────────────────────────────────

    async def _step_open_google(
        self, browser: Any, data: dict[str, Any]
    ) -> None:
        """
        گام ۱: باز کردن صفحه اصلی گوگل
        """
        logger.info("باز کردن google.com")
        await browser.navigate("https://www.google.com")
        logger.info("صفحه گوگل بارگذاری شد")

    async def _step_type_search(
        self, browser: Any, data: dict[str, Any]
    ) -> None:
        """
        گام ۲: تایپ عبارت جستجو در کادر جستجوی گوگل
        """
        search_query = data.get("query", "moz")
        logger.info("تایپ عبارت '%s' در کادر جستجو", search_query)

        search_box_selector = self._locators.get("search_box")
        await browser.fill(search_box_selector, search_query)
        await browser.press_key("Enter", search_box_selector)

        logger.info("عبارت جستجو ارسال شد")

    async def _step_wait_results(
        self, browser: Any, data: dict[str, Any]
    ) -> None:
        """
        گام ۳: انتظار برای بارگذاری نتایج جستجو
        """
        logger.info("انتظار برای بارگذاری نتایج")
        results_selector = self._locators.get("search_results")
        await browser.wait_for_element(results_selector, timeout=10000)
        logger.info("نتایج جستجو بارگذاری شد")

    async def _step_go_to_images(
        self, browser: Any, data: dict[str, Any]
    ) -> None:
        """
        گام ۴: کلیک بر روی تب تصاویر (Images)
        """
        logger.info("رفتن به تب تصاویر")
        images_tab_selector = self._locators.get("images_tab")
        await browser.click(images_tab_selector)
        logger.info("صفحه تصاویر بارگذاری شد")

    async def _step_download_image(
        self, browser: Any, data: dict[str, Any]
    ) -> None:
        """
        گام ۵: دانلود اولین تصویر از نتایج
        """
        logger.info("دانلود اولین تصویر")
        first_image_selector = self._locators.get("first_image")

        # کلیک روی اولین تصویر
        await browser.click(first_image_selector)
        await browser.wait_seconds(2.0)

        # تلاش برای دانلود تصویر بزرگ
        large_image_selector = self._locators.get("large_image")
        is_found = await browser.wait_for_element(large_image_selector, timeout=5000)

        if is_found:
            download_path = await browser.download_image(large_image_selector)
            if download_path:
                data["download_path"] = str(download_path)
                logger.info("تصویر با موفقیت دانلود شد: %s", download_path)
            else:
                logger.warning("دانلود تصویر ناموفق بود")
        else:
            logger.warning("المان تصویر بزرگ یافت نشد")

