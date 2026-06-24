# -*- coding: utf-8 -*-
"""
گردش کار جستجوی تصویر در بینگ (Advanced Smart Template)

این گردش کار به عنوان **قالب مرجع (Master Template)** برای اتوماسیون‌های آینده طراحی شده است.
هوش‌های مصنوعی (AI Agents) آینده باید از این فایل به عنوان یک نمونه استاندارد برای ساخت
اسکریپت‌های Native و پیچیده استفاده کنند.

ویژگی‌های کلیدی این الگو:
۱. مدیریت خطای هوشمند (Resilience): استفاده از بلاک‌های try/except در تک‌تک مراحل.
۲. بازگشت خودکار (Smart Fallback): اگر کاربر دستی کاری را انجام دهد یا صفحه خودبه‌خود لود شود، کد نباید کرش کند.
۳. استقلال گام‌ها: در صورت شکست یک زیربخش، تلاش‌های جایگزین اجرا می‌شود.
۴. اسکرین‌شات‌های خودکار: نیازی به دستور page.screenshot() نیست؛ پلتفرم مرکزی (BrowserController)
   پس از هر action مانند کلیک یا تایپ، به صورت کاملاً اتوماتیک اسکرین‌شات می‌گیرد و در داشبورد لاگ می‌کند.
۵. هندلینگ پاپ‌آپ‌ها: مدیریت خودکار کوکی‌ها و لاگین‌های مزاحم.
"""

import logging
import re
from typing import Any

from core.state_machine import WorkflowState
from workflows.base import BaseWorkflow, WorkflowStep

logger = logging.getLogger("automation_platform.workflows.bing")

class BingImageSearchWorkflow(BaseWorkflow):
    """
    گردش کار هوشمند جستجوی تصویر در بینگ
    """

    def __init__(self) -> None:
        """مقداردهی اولیه قالب هوشمند با تعریف نام، توضیحات و گام‌ها."""
        super().__init__()

        self._name = "bing_image_search"
        self._description = "جستجوی هوشمند تصویر در بینگ (Master Template)"

        # الگوهای URL برای تشخیص هوشمندانه وضعیت فعلی مرورگر
        self._page_patterns = {
            "open_bing": "bing.com",
            "search": "bing.com/search",
            "go_to_images": "bing.com/images/search",
        }

        # تعریف گام‌ها با Retry های مشخص
        # سیستم در صورت بروز خطا در هر action، آن گام را مجدد تلاش می‌کند
        self._steps = [
            WorkflowStep(
                name="open_bing",
                state=WorkflowState.NAVIGATING,
                action=self._step_open_bing,
                retry_count=3,
            ),
            WorkflowStep(
                name="search",
                state=WorkflowState.SEARCHING,
                action=self._step_type_search,
                retry_count=3,
            ),
            WorkflowStep(
                name="go_to_images",
                state=WorkflowState.NAVIGATING,
                action=self._step_go_to_images,
                retry_count=3,
            ),
            WorkflowStep(
                name="click_first_image",
                state=WorkflowState.NAVIGATING,
                action=self._step_click_first_image,
                retry_count=2,
            ),
        ]

    async def _sync_active_page_async(self, browser: Any) -> None:
        """
        همگام‌سازی صفحه فعال با آخرین تب باز شده.
        این متد یکی از مهم‌ترین بخش‌های اتوماسیون‌های Native است. اگر سایت در تب جدیدی باز شود،
        این متد کنترل Playwright را به صورت پویا به آن تب منتقل می‌کند.
        """
        if browser.context and len(browser.context.pages) > 1:
            active_page = browser.context.pages[-1]
            if browser.page != active_page:
                logger.info("سوئیچ هوشمند به تب جدید: %s", active_page.url)
                browser._page = active_page
                try:
                    await active_page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception as e:
                    logger.debug("خطا در انتظار لود تب جدید: %s", e)

    async def _handle_popup_consent(self, browser: Any) -> None:
        """
        بستن هوشمند پاپ‌آپ‌ها (نظیر کوکی‌ها، نوتیفیکیشن‌ها و لاگین‌های مزاحم).
        باید در هر گام که احتمال نمایش پاپ‌آپ هست، فراخوانی شود.
        """
        selectors = [
            "button:has-text('Accept')", "button:has-text('پذیرش')",
            "#bnp_btn_accept", "button:has-text('موافقم')",
            "#adlt_set_yes" # برای پاپ‌آپ محتوای بزرگسالان در جستجوی تصاویر
        ]
        try:
            for sel in selectors:
                if await browser.is_visible(f"{sel} >> nth=0"):
                    logger.info("پاپ‌آپ مزاحم با سلکتور '%s' شناسایی شد. در حال رد کردن...", sel)
                    await browser.click(f"{sel} >> nth=0")
                    await browser.wait_seconds(1.0)
                    break
        except Exception:
            pass # هیچ‌گاه نباید روند اصلی بخاطر پاپ‌آپ متوقف شود

    async def _step_open_bing(self, browser: Any, data: dict[str, Any]) -> None:
        """گام ۱: باز کردن صفحه اصلی (با دور زدن هوشمند در صورت لزوم)"""
        current_url = browser.page.url if browser.page else ""
        
        # Smart Bypass: اگر کاربر خودش صفحه را باز کرده باشد، اسکیپ می‌کنیم
        if "bing.com" in current_url:
            logger.info("کاربر از قبل در سایت بینگ است. نیازی به بارگذاری مجدد نیست.")
            return

        logger.info("باز کردن هوشمند bing.com")
        await browser.navigate("https://www.bing.com")
        await self._handle_popup_consent(browser)

    async def _step_type_search(self, browser: Any, data: dict[str, Any]) -> None:
        """گام ۲: تایپ و جستجو"""
        await self._sync_active_page_async(browser)
        current_url = browser.page.url
        
        search_query = data.get("query", "moz")
        
        # Smart Bypass: اگر کاربر خودش جستجو کرده و در صفحه نتایج است
        if "search" in current_url and "q=" in current_url:
            logger.info("کاربر جستجو را دستی انجام داده است. از این گام عبور می‌کنیم.")
            return

        logger.info("تایپ هوشمند عبارت '%s' در کادر جستجو", search_query)
        search_box = "#sb_form_q"
        
        try:
            # پاک کردن کادر در صورت وجود متن قبلی
            await browser.fill(search_box, "")
            await browser.fill(search_box, search_query)
            await browser.press_key("Enter", search_box)
            logger.info("جستجو با موفقیت ارسال شد.")
            
            # انتظار برای نمایان شدن نتایج
            await browser.wait_for_element("#b_results >> nth=0", timeout=8000)
        except Exception as e:
            logger.error("خطا در جستجو: %s", e)
            # راهکار پشتیبان (Fallback)
            logger.info("استفاده از مسیر جایگزین (ناوبری مستقیم به URL)...")
            await browser.navigate(f"https://www.bing.com/search?q={search_query}")

        await self._handle_popup_consent(browser)

    async def _step_go_to_images(self, browser: Any, data: dict[str, Any]) -> None:
        """گام ۳: انتقال به بخش تصاویر با شناسایی پویا"""
        await self._sync_active_page_async(browser)
        
        if "images/search" in browser.page.url:
            logger.info("کاربر در حال حاضر در صفحه تصاویر است.")
            return

        logger.info("انتقال به تب تصاویر با سلکتورهای پویا...")
        
        # ترکیبی از متن و CSS برای بیشترین مقاومت در برابر تغییرات رابط کاربری
        selectors = [
            ("link", "Images"), ("link", "تصاویر"),
            ("css", "a[href*='images/search']"),
            ("css", "#b-scopeListItem-images a")
        ]
        
        clicked = False
        for sel_type, sel_value in selectors:
            try:
                if sel_type == "link":
                    target = browser.page.get_by_role("link", name=sel_value, exact=True)
                    if await target.count() > 0 and await target.first.is_visible():
                        await target.first.click()
                        clicked = True
                        break
                else:
                    if await browser.is_visible(f"{sel_value} >> nth=0"):
                        await browser.click(f"{sel_value} >> nth=0")
                        clicked = True
                        break
            except Exception:
                continue

        if clicked:
            await browser.wait_seconds(2.0)
            await self._sync_active_page_async(browser)
        else:
            # آخرین راهکار (Absolute Fallback)
            search_query = data.get("query", "moz")
            logger.warning("تب تصاویر در UI یافت نشد. ناوبری مستقیم از طریق URL.")
            await browser.navigate(f"https://www.bing.com/images/search?q={search_query}")
            await self._sync_active_page_async(browser)

    async def _step_click_first_image(self, browser: Any, data: dict[str, Any]) -> None:
        """گام ۴: کلیک نهایی روی تصویر و اتمام کار"""
        await self._sync_active_page_async(browser)
        await self._handle_popup_consent(browser)

        logger.info("تلاش برای باز کردن اولین عکس نتایج...")
        
        selectors = ["a.iusc", "a.mimg", ".imgpt a"]
        success = False
        
        for sel in selectors:
            first_sel = f"{sel} >> nth=0"
            try:
                if await browser.wait_for_element(first_sel, timeout=4000):
                    await browser.click(first_sel)
                    success = True
                    break
            except Exception:
                continue
                
        if not success:
            logger.warning("نتوانستیم با CSSهای معمول روی تصویر کلیک کنیم. تلاش با Regex المتنی...")
            try:
                pattern = re.compile("Image result for|تصویر برای")
                target = browser.page.get_by_label(pattern).first
                if await target.count() > 0:
                    await target.click()
                    success = True
            except Exception as e:
                logger.error("خطا در کلیک با لیبل: %s", e)
                raise RuntimeError("کلاً هیچ تصویری برای کلیک پیدا نشد. آیا عبارت سرچ نتیجه‌ای دارد؟")

        if success:
            logger.info("تصویر با موفقیت باز شد. (اسکرین‌شات نهایی اتوماتیک گرفته خواهد شد)")
            await browser.wait_seconds(3.0)

