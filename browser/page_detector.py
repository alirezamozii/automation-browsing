# -*- coding: utf-8 -*-
"""
تشخیص صفحه فعلی مرورگر

تشخیص صفحه‌ای که مرورگر در آن قرار دارد بر اساس URL و المان‌های صفحه.
برای Resume بعد از Pause استفاده می‌شود.
"""

import asyncio
import logging

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class PageDetector:
    """
    تشخیص صفحه فعلی مرورگر.
    
    بر اساس الگوهای URL و المان‌های HTML، صفحه فعلی را شناسایی می‌کند.
    این قابلیت برای Resume بعد از Pause ضروری است تا سیستم بداند
    از کجا باید ادامه دهد.
    """

    async def detect(self, page: Page, patterns: dict[str, dict[str, str]]) -> str | None:
        """
        تشخیص صفحه فعلی بر اساس الگوهای داده شده.
        
        Args:
            page: آبجکت Page از Playwright
            patterns: دیکشنری الگوها. مثال:
                {
                    "login_page": {
                        "url_contains": "login",
                        "has_element": "input[name='username']"
                    },
                    "dashboard": {
                        "url_contains": "dashboard",
                        "has_element": ".dashboard-container"
                    }
                }
        
        Returns:
            نام صفحه تشخیص داده شده، یا None اگر هیچ الگویی مطابقت نداشت
        """
        if not patterns:
            logger.warning("هیچ الگویی برای تشخیص صفحه ارائه نشده")
            return None

        current_url = page.url
        logger.debug(f"تشخیص صفحه — URL فعلی: {current_url}")

        best_match: str | None = None
        best_score: int = 0

        for page_name, pattern in patterns.items():
            score = 0

            # بررسی الگوی URL
            url_pattern = pattern.get("url_contains")
            if url_pattern:
                if url_pattern.lower() in current_url.lower():
                    score += 1
                    logger.debug(f"  [{page_name}] URL مطابقت دارد: '{url_pattern}'")
                else:
                    # اگر URL مطابقت ندارد، این صفحه نیست
                    continue

            # بررسی URL دقیق
            url_exact = pattern.get("url_equals")
            if url_exact:
                if current_url.rstrip("/") == url_exact.rstrip("/"):
                    score += 2
                else:
                    continue

            # بررسی وجود المان
            element_selector = pattern.get("has_element")
            if element_selector:
                try:
                    element = page.locator(element_selector)
                    is_visible = await element.is_visible()
                    if is_visible:
                        score += 2
                        logger.debug(f"  [{page_name}] المان پیدا شد: '{element_selector}'")
                    else:
                        # المان وجود دارد ولی مخفی است — امتیاز کمتر
                        count = await element.count()
                        if count > 0:
                            score += 1
                        else:
                            continue
                except Exception:
                    continue

            # بررسی عنوان صفحه
            title_contains = pattern.get("title_contains")
            if title_contains:
                try:
                    title = await page.title()
                    if title_contains.lower() in title.lower():
                        score += 1
                except Exception:
                    pass

            if score > best_score:
                best_score = score
                best_match = page_name

        if best_match:
            logger.info(f"صفحه تشخیص داده شد: {best_match} (امتیاز: {best_score})")
        else:
            logger.warning("هیچ صفحه‌ای تشخیص داده نشد")

        return best_match

    async def wait_for_page(
        self,
        page: Page,
        page_name: str,
        patterns: dict[str, dict[str, str]],
        timeout: int = 30000,
        poll_interval: float = 0.5,
    ) -> bool:
        """
        صبر کردن تا صفحه مورد نظر لود شود.
        
        Args:
            page: آبجکت Page از Playwright
            page_name: نام صفحه مورد انتظار
            patterns: دیکشنری الگوها
            timeout: حداکثر زمان انتظار به میلی‌ثانیه
            poll_interval: فاصله بین هر بررسی به ثانیه
        
        Returns:
            True اگر صفحه پیدا شد، False اگر timeout شد
        """
        logger.info(f"در انتظار صفحه: {page_name} (timeout: {timeout}ms)")
        
        elapsed = 0
        timeout_seconds = timeout / 1000.0

        while elapsed < timeout_seconds:
            detected = await self.detect(page, patterns)
            if detected == page_name:
                logger.info(f"صفحه '{page_name}' با موفقیت شناسایی شد")
                return True
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        logger.warning(f"Timeout — صفحه '{page_name}' پیدا نشد پس از {timeout}ms")
        return False

    async def detect_with_fallback(
        self,
        page: Page,
        patterns: dict[str, dict[str, str]],
        fallback: str = "unknown",
    ) -> str:
        """
        تشخیص صفحه با مقدار پیش‌فرض در صورت عدم تشخیص.
        
        Args:
            page: آبجکت Page
            patterns: الگوها
            fallback: مقدار پیش‌فرض
        
        Returns:
            نام صفحه یا مقدار fallback
        """
        result = await self.detect(page, patterns)
        return result if result is not None else fallback
