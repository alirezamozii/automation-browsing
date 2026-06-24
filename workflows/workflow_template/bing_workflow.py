# -*- coding: utf-8 -*-
"""
گردش کار جستجوی تصویر در بینگ — Master Reference Template
============================================================

این فایل هم یک workflow واقعی است و هم یک راهنمای کامل برای نوشتن
workflow‌های پیچیده‌تر در آینده.

══════════════════════════════════════════════════════════════════
  فهرست قابلیت‌های BrowserController (همه در این فایل توضیح داده شده)
══════════════════════════════════════════════════════════════════

  ناوبری پایه:
    browser.navigate(url)              ← رفتن به URL
    browser.reload()                   ← رفرش صفحه
    browser.go_back() / go_forward()   ← تاریخچه مرورگر
    browser.get_current_url()          ← URL فعلی
    browser.get_title()                ← عنوان صفحه
    browser.get_page_source()          ← HTML کامل

  کلیک:
    browser.click(locator)             ← کلیک ساده
    browser.double_click(locator)      ← دابل‌کلیک
    browser.right_click(locator)       ← کلیک راست (context menu)
    browser.hover(locator)             ← hover (tooltip / dropdown)

  فرم:
    browser.fill(locator, value)       ← پر کردن سریع فیلد
    browser.type_text(locator, text)   ← تایپ کاراکتر‌به‌کاراکتر (انسانی‌تر)
    browser.clear(locator)             ← پاک کردن فیلد
    browser.press_key(key, locator)    ← فشار کلید (Enter, Tab, Escape...)
    browser.focus(locator)             ← فوکوس بدون کلیک
    browser.select_option(...)         ← انتخاب از <select> dropdown
    browser.check(locator)             ← تیک زدن checkbox
    browser.uncheck(locator)           ← برداشتن تیک
    browser.upload_file(locator, path) ← آپلود فایل روی input[type=file]
    browser.drag_and_drop(src, dst)    ← Drag & Drop

  انتظار / بررسی:
    browser.wait_for_element(locator)  ← صبر تا المان ظاهر شود
    browser.wait_for_function(js)      ← صبر تا JS expression = truthy
    browser.wait_for_navigation()      ← صبر تا ناوبری تمام شود
    browser.wait_for_url(pattern)      ← صبر تا URL تغییر کند
    browser.wait_for_response(pattern) ← صبر تا API response برگردد
    browser.wait_for_request(pattern)  ← صبر تا request ارسال شود
    browser.wait_seconds(n)            ← صبر ثابت

  خواندن اطلاعات:
    browser.is_visible(locator)        ← آیا المان قابل مشاهده است؟
    browser.is_enabled(locator)        ← آیا المان فعال است؟
    browser.is_checked(locator)        ← آیا checkbox تیک خورده؟
    browser.count_elements(locator)    ← تعداد المان‌های مطابق
    browser.get_text(locator)          ← متن یک المان
    browser.get_all_text(locator)      ← متن همه المان‌های مطابق
    browser.get_attribute(loc, attr)   ← مقدار attribute
    browser.get_input_value(locator)   ← مقدار فعلی input

  JavaScript:
    browser.evaluate(js)               ← اجرای JS
    browser.evaluate_on_element(l, js) ← اجرای JS روی المان خاص

  اسکرین‌شات:
    browser.screenshot()               ← اسکرین‌شات کامل (خودکار!)
    browser.screenshot_element(loc)    ← اسکرین‌شات crop‌شده از المان

  اسکرول:
    browser.scroll_to_bottom()         ← اسکرول به پایین
    browser.scroll_to_top()            ← اسکرول به بالا
    browser.scroll_to_element(loc)     ← اسکرول به المان
    browser.scroll_by(x, y)            ← اسکرول به مقدار مشخص

  تب‌ها:
    browser.open_new_tab(url)          ← باز کردن تب جدید
    browser.switch_to_tab(index)       ← سوئیچ به تب
    browser.close_current_tab()        ← بستن تب فعلی

  کوکی و Storage:
    browser.get_cookies(url)           ← خواندن کوکی‌ها
    browser.set_cookies([...])         ← تنظیم کوکی (bypass login)
    browser.clear_cookies()            ← پاک کردن کوکی‌ها
    browser.get_local_storage(key)     ← خواندن از localStorage
    browser.set_local_storage(k, v)    ← نوشتن در localStorage

  Network:
    browser.set_extra_headers({...})   ← هدرهای اضافی برای همه request‌ها
    browser.intercept_requests(...)    ← رهگیری و تغییر request‌ها
    browser.block_resources([...])     ← بلاک منابع (۴۰-۶۰٪ سریع‌تر)
    browser.unblock_resources()        ← برداشتن بلاک

  دستگاه:
    browser.emulate_device("iPhone 13") ← شبیه‌سازی موبایل/تبلت
    browser.set_viewport(w, h)          ← تغییر اندازه viewport

  دانلود:
    browser.download_file(loc_or_url)  ← دانلود فایل
    browser.download_image(locator)    ← دانلود تصویر از img

══════════════════════════════════════════════════════════════════
  ویژگی‌های WorkflowStep پیشرفته
══════════════════════════════════════════════════════════════════

  WorkflowStep(
      name="step_name",
      state=WorkflowState.NAVIGATING,
      action=self._my_action,
      retry_count=3,            ← تعداد تلاش مجدد
      timeout_override=60.0,    ← تایم‌اوت ثانیه (پیش‌فرض ۳۰)
      description="توضیح",      ← نمایش در UI
      tags=["login", "critical"], ← برچسب‌ها
      skip_if=self._already_logged_in,  ← تابع async که اگر True → skip
  )

══════════════════════════════════════════════════════════════════
"""

import logging
import re
from typing import Any

from core.state_machine import WorkflowState
from workflows.base import BaseWorkflow, WorkflowStep

logger = logging.getLogger("automation_platform.workflows.bing")


class BingImageSearchWorkflow(BaseWorkflow):
    """
    گردش کار هوشمند جستجوی تصویر در بینگ.
    این فایل هم workflow واقعی است هم Master Reference Template.
    """

    def __init__(self) -> None:
        super().__init__()
        self._name = "bing_image_search"
        self._description = "جستجوی هوشمند تصویر در بینگ"

        # الگوهای URL برای پرش هوشمند engine هنگام Resume
        self._page_patterns = {
            "open_bing":        "bing.com",
            "search":           "bing.com/search",
            "go_to_images":     "bing.com/images/search",
            "click_first_image":"bing.com/images/search",
        }

        self._steps = [
            WorkflowStep(
                name="open_bing",
                state=WorkflowState.NAVIGATING,
                action=self._step_open_bing,
                retry_count=3,
                description="باز کردن bing.com",
                tags=["navigation"],
            ),
            WorkflowStep(
                name="search",
                state=WorkflowState.SEARCHING,
                action=self._step_type_search,
                retry_count=3,
                description="تایپ عبارت جستجو و ارسال",
                # skip_if example: اگر URL از قبل حاوی نتایج جستجو باشد، این گام skip می‌شود
                skip_if=self._already_on_results,
                tags=["form", "search"],
            ),
            WorkflowStep(
                name="go_to_images",
                state=WorkflowState.NAVIGATING,
                action=self._step_go_to_images,
                retry_count=3,
                description="رفتن به تب تصاویر",
                tags=["navigation"],
            ),
            WorkflowStep(
                name="click_first_image",
                state=WorkflowState.NAVIGATING,
                action=self._step_click_first_image,
                retry_count=2,
                description="کلیک روی اولین تصویر",
                tags=["click"],
            ),
        ]

    # ── skip_if conditions ────────────────────────────────────────────────────

    async def _already_on_results(self, browser: Any, data: dict[str, Any]) -> bool:
        """اگر URL از قبل حاوی نتایج جستجو باشد → گام search را skip کن."""
        try:
            url = browser.page.url if browser.page else ""
            query = data.get("query", "")
            return "search" in url and "q=" in url and query.lower() in url.lower()
        except Exception:
            return False

    # ── execute (direct call بدون engine) ────────────────────────────────────

    async def execute(self, browser: Any, state: WorkflowState, data: dict[str, Any]) -> None:
        logger.info("اجرای مستقیم workflow '%s'", self._name)
        for step in self._steps:
            if step.skip_if and await step.skip_if(browser, data):
                logger.info("⏭ skip: %s", step.name)
                continue
            logger.info("▶ %s", step.name)
            await step.action(browser, data)
        logger.info("✅ workflow '%s' تمام شد", self._name)

    # ── Shared helpers ────────────────────────────────────────────────────────

    async def _sync_active_page(self, browser: Any) -> None:
        """سوئیچ هوشمند به آخرین تب باز شده."""
        if browser.context and len(browser.context.pages) > 1:
            last = browser.context.pages[-1]
            if browser.page != last:
                logger.info("سوئیچ به تب جدید: %s", last.url)
                browser._page = last
                try:
                    await last.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass

    async def _dismiss_popups(self, browser: Any) -> None:
        """بستن popup‌های رایج (کوکی، consent، login prompt)."""
        selectors = [
            "button:has-text('Accept')",
            "button:has-text('پذیرش')",
            "#bnp_btn_accept",
            "button:has-text('موافقم')",
            "#adlt_set_yes",
        ]
        try:
            for sel in selectors:
                if await browser.is_visible(f"{sel} >> nth=0"):
                    logger.info("popup بسته شد: %s", sel)
                    await browser.click(f"{sel} >> nth=0")
                    await browser.wait_seconds(0.8)
                    break
        except Exception:
            pass  # popup نباید workflow را متوقف کند

    # ── Steps ─────────────────────────────────────────────────────────────────

    async def _step_open_bing(self, browser: Any, data: dict[str, Any]) -> None:
        """گام ۱: باز کردن bing.com با Smart Bypass."""
        url = browser.page.url if browser.page else ""
        if "bing.com" in url:
            logger.info("از قبل در bing.com هستیم")
            return
        await browser.navigate("https://www.bing.com")
        await self._dismiss_popups(browser)

    async def _step_type_search(self, browser: Any, data: dict[str, Any]) -> None:
        """گام ۲: تایپ و ارسال جستجو."""
        await self._sync_active_page(browser)
        query = data.get("query", "automation")
        logger.info("جستجو: '%s'", query)
        search_box = "#sb_form_q"
        try:
            await browser.clear(search_box)
            await browser.fill(search_box, query)
            await browser.press_key("Enter", search_box)
            await browser.wait_for_element("#b_results >> nth=0", timeout=8000)
        except Exception as e:
            logger.error("خطا در جستجو: %s — fallback به URL", e)
            await browser.navigate(f"https://www.bing.com/search?q={query}")
        await self._dismiss_popups(browser)

    async def _step_go_to_images(self, browser: Any, data: dict[str, Any]) -> None:
        """گام ۳: رفتن به تب تصاویر."""
        await self._sync_active_page(browser)
        if "images/search" in browser.page.url:
            return
        selectors = [
            ("role", "Images"), ("role", "تصاویر"),
            ("css", "a[href*='images/search']"),
            ("css", "#b-scopeListItem-images a"),
        ]
        clicked = False
        for sel_type, sel_value in selectors:
            try:
                if sel_type == "role":
                    t = browser.page.get_by_role("link", name=sel_value, exact=True)
                    if await t.count() > 0 and await t.first.is_visible():
                        await t.first.click()
                        clicked = True
                        break
                elif await browser.is_visible(f"{sel_value} >> nth=0"):
                    await browser.click(f"{sel_value} >> nth=0")
                    clicked = True
                    break
            except Exception:
                continue

        if clicked:
            await browser.wait_seconds(1.5)
            await self._sync_active_page(browser)
        else:
            query = data.get("query", "automation")
            await browser.navigate(f"https://www.bing.com/images/search?q={query}")
            await self._sync_active_page(browser)

    async def _step_click_first_image(self, browser: Any, data: dict[str, Any]) -> None:
        """گام ۴: کلیک روی اولین تصویر."""
        await self._sync_active_page(browser)
        await self._dismiss_popups(browser)

        for sel in ["a.iusc", "a.mimg", ".imgpt a"]:
            try:
                if await browser.wait_for_element(f"{sel} >> nth=0", timeout=4000):
                    await browser.click(f"{sel} >> nth=0")
                    await browser.wait_seconds(2.5)
                    return
            except Exception:
                continue

        # آخرین تلاش با regex label
        try:
            pattern = re.compile(r"Image result for|تصویر برای")
            t = browser.page.get_by_label(pattern).first
            if await t.count() > 0:
                await t.click()
                await browser.wait_seconds(2.5)
                return
        except Exception as e:
            logger.error("کلیک روی تصویر ناموفق: %s", e)

        raise RuntimeError("هیچ تصویری یافت نشد — آیا جستجو نتیجه دارد؟")


# ══════════════════════════════════════════════════════════════════
#  ADVANCED PATTERNS — برای workflow‌های پیچیده‌تر در آینده
# ══════════════════════════════════════════════════════════════════
#
# ── ۱. بلاک کردن منابع برای سرعت بیشتر ──────────────────────────
#
#   async def _step_fast_navigate(self, browser, data):
#       # فقط HTML و JS لود می‌شود → ۴۰-۶۰٪ سریع‌تر
#       await browser.block_resources(["image", "stylesheet", "font", "media"])
#       await browser.navigate("https://example.com")
#       await browser.unblock_resources()  # بعد از لود، بلاک را بردار
#
# ── ۲. Bypass login با cookie ────────────────────────────────────
#
#   async def _step_inject_session(self, browser, data):
#       await browser.set_cookies([{
#           "name": "session_token",
#           "value": data.get("session_token"),
#           "domain": "example.com",
#           "path": "/",
#           "httpOnly": True,
#       }])
#       await browser.navigate("https://example.com/dashboard")
#       # اگر به dashboard رفتیم یعنی login موفق بود
#       if "dashboard" not in await browser.get_current_url():
#           raise RuntimeError("Session cookie معتبر نیست")
#
# ── ۳. Request Interception (تغییر API response) ─────────────────
#
#   async def _step_mock_api(self, browser, data):
#       async def mock_handler(route):
#           if "/api/config" in route.request.url:
#               await route.fulfill(
#                   status=200,
#                   content_type="application/json",
#                   body='{"feature_flag": true}'
#               )
#           else:
#               await route.continue_()
#       await browser.intercept_requests("**/api/**", mock_handler)
#
# ── ۴. صبر برای API response ─────────────────────────────────────
#
#   async def _step_wait_for_data(self, browser, data):
#       # شروع navigation و همزمان صبر برای response
#       response = await browser.wait_for_response("**/api/products*")
#       products = await response.json()
#       self._output["products"] = products
#
# ── ۵. شبیه‌سازی موبایل ──────────────────────────────────────────
#
#   async def _step_mobile_view(self, browser, data):
#       await browser.emulate_device("iPhone 13")
#       await browser.navigate("https://example.com")
#       # حالا سایت mobile view نشان می‌دهد
#
# ── ۶. آپلود فایل ────────────────────────────────────────────────
#
#   async def _step_upload_resume(self, browser, data):
#       resume_path = data.get("resume_path", "C:/Documents/resume.pdf")
#       await browser.upload_file("input[type='file'][name='resume']", resume_path)
#       await browser.click("button[type='submit']")
#
# ── ۷. Drag & Drop ───────────────────────────────────────────────
#
#   async def _step_reorder_items(self, browser, data):
#       await browser.drag_and_drop("#task-1", "#column-done")
#
# ── ۸. get_all_text برای scraping ────────────────────────────────
#
#   async def _step_collect_results(self, browser, data):
#       titles = await browser.get_all_text("h3.result-title")
#       prices = await browser.get_all_text(".price-value")
#       self._output["results"] = list(zip(titles, prices))
#       logger.info("تعداد نتایج: %d", len(titles))
#
# ── ۹. اسکرین‌شات فقط از یک المان خاص ──────────────────────────
#
#   async def _step_capture_chart(self, browser, data):
#       path = await browser.screenshot_element(".analytics-chart")
#       self._output["chart_screenshot"] = str(path)
#
# ── ۱۰. اسکرول تا پایین برای Infinite Scroll ────────────────────
#
#   async def _step_load_all_items(self, browser, data):
#       prev_count = 0
#       for _ in range(10):  # حداکثر ۱۰ بار اسکرول
#           await browser.scroll_to_bottom()
#           await browser.wait_seconds(1.5)
#           count = await browser.count_elements(".item-card")
#           if count == prev_count:
#               break  # دیگر چیزی لود نمی‌شود
#           prev_count = count
#       self._output["total_items"] = prev_count
#
# ── ۱۱. چند تب همزمان ────────────────────────────────────────────
#
#   async def _step_open_multiple_tabs(self, browser, data):
#       urls = data.get("urls", [])
#       for url in urls:
#           await browser.open_new_tab(url)
#           await browser.wait_seconds(1.0)
#       # برگشت به اولین تب
#       await browser.switch_to_tab(0)
#
# ── ۱۲. skip_if — اگر کاربر لاگین باشد، گام login رو skip کن ────
#
#   async def _is_logged_in(self, browser, data):
#       return await browser.is_visible("#user-avatar")
#
#   # در __init__:
#   WorkflowStep(
#       name="login",
#       state=WorkflowState.LOGIN,
#       action=self._do_login,
#       skip_if=self._is_logged_in,
#   )
#
# ══════════════════════════════════════════════════════════════════
