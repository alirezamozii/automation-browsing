# -*- coding: utf-8 -*-
"""
کنترلر مرورگر — لایه انتزاعی Playwright

لایه اصلی ارتباط با مرورگر Chrome از طریق Playwright.
تمام عملیات مرورگر از این لایه عبور می‌کنند.

قابلیت‌ها:
  - Chrome واقعی با پروفایل ثابت (session حفظ می‌شود)
  - Pause / Resume با asyncio.Event
  - اسکرین‌شات خودکار بعد از هر action
  - کلیک، تایپ، ناوبری، فرم، فایل آپلود، drag & drop
  - مدیریت کوکی، هدر، request interception
  - بلاک‌کردن منابع برای اجرای سریع‌تر
  - شبیه‌سازی دستگاه موبایل
  - دانلود فایل و تصویر
"""

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Route,
    async_playwright,
)

from browser.profile import ProfileManager
from config import DEFAULT_TIMEOUT, SCREENSHOTS_DIR

logger = logging.getLogger(__name__)


class BrowserController:
    """
    کنترلر اصلی مرورگر — wrapper کامل روی Playwright.

    هر متد قبل از اجرا وضعیت Pause را بررسی می‌کند و بعد از
    اجرای موفق یک اسکرین‌شات می‌گیرد و کالبک on_action را صدا می‌زند.
    """

    def __init__(self, profile_manager: ProfileManager | None = None):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._profile_manager = profile_manager or ProfileManager()

        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._is_paused = False

        self._default_timeout = DEFAULT_TIMEOUT
        self._screenshots_dir = SCREENSHOTS_DIR
        self.on_action: Callable | None = None
        self.event_bus: Any = None  # injected by WorkflowEngine


    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def page(self) -> Page | None:
        return self._page

    @property
    def context(self) -> BrowserContext | None:
        return self._context

    @property
    def browser(self) -> Browser | None:
        return self._browser

    @property
    def is_launched(self) -> bool:
        if self._context is None:
            return False
        try:
            if len(self._context.pages) == 0:
                self._context = None
                self._page = None
                return False
        except Exception:
            return False
        return True

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def launch(self, headless: bool = False) -> Page:
        """باز کردن Chrome با پروفایل ثابت."""
        if self.is_launched:
            logger.warning("مرورگر قبلاً باز است")
            return self._page

        logger.info("🚀 در حال باز کردن Chrome...")
        self._profile_manager.cleanup_for_launch()
        profile_path = self._profile_manager.get_profile_path()
        self._playwright = await async_playwright().start()

        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            channel="chrome",
            headless=headless,
            user_agent=user_agent,
            no_viewport=not headless,
            viewport={"width": 1280, "height": 900} if headless else None,
            locale="fa-IR",
            timezone_id="Asia/Tehran",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--start-maximized",
                "--disable-session-crashed-bubble",
                "--hide-crash-restore-bubble",
                "--window-size=1280,900",
            ],
            ignore_default_args=["--enable-automation"],
        )

        await asyncio.sleep(1)
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        self._page.set_default_timeout(self._default_timeout)
        self._page.set_default_navigation_timeout(self._default_timeout)
        self._context.on("page", self._on_new_page)
        logger.info("✅ Chrome باز شد")
        return self._page

    async def close(self) -> None:
        """بستن مرورگر و آزادسازی منابع."""
        logger.info("🔒 بستن Chrome...")
        try:
            if self._context:
                await self._context.close()
                self._context = self._page = self._browser = None
        except Exception as e:
            logger.error(f"خطا در بستن context: {e}")
        try:
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception as e:
            logger.error(f"خطا در بستن Playwright: {e}")
        logger.info("✅ Chrome بسته شد")


    # ── Pause / Resume ────────────────────────────────────────────────────────

    def pause(self) -> None:
        if not self._is_paused:
            self._is_paused = True
            self._pause_event.clear()
            logger.info("⏸ مرورگر Pause شد")

    def resume(self) -> None:
        if self._is_paused:
            self._is_paused = False
            self._pause_event.set()
            logger.info("▶ مرورگر Resume شد")

    async def _check_paused(self) -> None:
        if self._is_paused:
            logger.debug("⏳ منتظر Resume...")
            await self._pause_event.wait()

    async def _after_action(self) -> None:
        """اسکرین‌شات + کالبک بعد از هر عملیات موفق."""
        if self.on_action:
            try:
                path = await self.screenshot()
                if path is not None:
                    await self.on_action(path)
            except Exception as e:
                logger.debug(f"خطا در اسکرین‌شات پس از عملیات: {e}")

    # ── Core Navigation ───────────────────────────────────────────────────────

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """ناوبری به URL."""
        await self._check_paused()
        self._ensure_page()
        logger.info(f"🌐 ناوبری به: {url}")
        try:
            await self._page.goto(url, wait_until=wait_until)
            logger.info(f"✅ صفحه لود شد: {url}")
            await self._after_action()
        except Exception as e:
            logger.error(f"❌ خطا در ناوبری به {url}: {e}")
            raise

    async def reload(self, wait_until: str = "domcontentloaded") -> None:
        """رفرش صفحه."""
        await self._check_paused()
        self._ensure_page()
        await self._page.reload(wait_until=wait_until)
        await self._after_action()

    async def go_back(self) -> None:
        """برگشت به صفحه قبلی."""
        await self._check_paused()
        self._ensure_page()
        await self._page.go_back()
        await self._after_action()

    async def go_forward(self) -> None:
        """رفتن به صفحه بعدی."""
        await self._check_paused()
        self._ensure_page()
        await self._page.go_forward()
        await self._after_action()

    # ── Click Actions ─────────────────────────────────────────────────────────

    async def click(self, locator: str, timeout: int | None = None) -> None:
        """کلیک روی المان."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        try:
            el = self._page.locator(locator)
            await el.wait_for(state="visible", timeout=timeout)
            await el.click(timeout=timeout)
            await self._after_action()
        except Exception as e:
            logger.error(f"❌ خطا در کلیک روی '{locator}': {e}")
            raise

    async def double_click(self, locator: str, timeout: int | None = None) -> None:
        """دابل‌کلیک روی المان."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        try:
            el = self._page.locator(locator)
            await el.wait_for(state="visible", timeout=timeout)
            await el.dblclick(timeout=timeout)
            await self._after_action()
        except Exception as e:
            logger.error(f"❌ خطا در دابل‌کلیک روی '{locator}': {e}")
            raise

    async def right_click(self, locator: str, timeout: int | None = None) -> None:
        """کلیک راست روی المان (باز کردن context menu)."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        try:
            el = self._page.locator(locator)
            await el.wait_for(state="visible", timeout=timeout)
            await el.click(button="right", timeout=timeout)
            await self._after_action()
        except Exception as e:
            logger.error(f"❌ خطا در کلیک‌راست روی '{locator}': {e}")
            raise

    async def hover(self, locator: str, timeout: int | None = None) -> None:
        """Hover روی المان (فعال کردن tooltip / dropdown)."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        try:
            el = self._page.locator(locator)
            await el.wait_for(state="visible", timeout=timeout)
            await el.hover(timeout=timeout)
            await self._after_action()
        except Exception as e:
            logger.error(f"❌ خطا در hover روی '{locator}': {e}")
            raise


    # ── Form Actions ──────────────────────────────────────────────────────────

    async def fill(self, locator: str, value: str, timeout: int | None = None) -> None:
        """پر کردن فیلد (پاک + تایپ یکجا)."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        try:
            el = self._page.locator(locator)
            await el.wait_for(state="visible", timeout=timeout)
            await el.fill(value, timeout=timeout)
            await self._after_action()
        except Exception as e:
            logger.error(f"❌ خطا در fill '{locator}': {e}")
            raise

    async def clear(self, locator: str, timeout: int | None = None) -> None:
        """پاک کردن محتوای یک فیلد."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        el = self._page.locator(locator)
        await el.wait_for(state="visible", timeout=timeout)
        await el.clear(timeout=timeout)

    async def type_text(self, locator: str, text: str, delay: float = 50, timeout: int | None = None) -> None:
        """تایپ کاراکتر به کاراکتر (رفتار انسانی)."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        try:
            el = self._page.locator(locator)
            await el.wait_for(state="visible", timeout=timeout)
            await el.click(timeout=timeout)
            await el.type(text, delay=delay)
            await self._after_action()
        except Exception as e:
            logger.error(f"❌ خطا در type_text '{locator}': {e}")
            raise

    async def press_key(self, key: str, locator: str | None = None) -> None:
        """فشار دادن کلید (Enter, Tab, Escape, ArrowDown, …)."""
        await self._check_paused()
        self._ensure_page()
        try:
            if locator:
                await self._page.locator(locator).press(key)
            else:
                await self._page.keyboard.press(key)
            await self._after_action()
        except Exception as e:
            logger.error(f"❌ خطا در press_key '{key}': {e}")
            raise

    async def focus(self, locator: str, timeout: int | None = None) -> None:
        """فوکوس روی یک المان (بدون کلیک)."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        el = self._page.locator(locator)
        await el.wait_for(state="visible", timeout=timeout)
        await el.focus(timeout=timeout)

    async def select_option(
        self,
        locator: str,
        value: str | None = None,
        label: str | None = None,
        index: int | None = None,
        timeout: int | None = None,
    ) -> None:
        """
        انتخاب گزینه از <select> dropdown.

        یکی از value / label / index را بدهید:
          await browser.select_option("#country", value="IR")
          await browser.select_option("#size", label="Large")
          await browser.select_option("#item", index=2)
        """
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        el = self._page.locator(locator)
        await el.wait_for(state="visible", timeout=timeout)
        kwargs: dict = {}
        if value is not None:
            kwargs["value"] = value
        elif label is not None:
            kwargs["label"] = label
        elif index is not None:
            kwargs["index"] = index
        await el.select_option(**kwargs, timeout=timeout)
        await self._after_action()

    async def check(self, locator: str, timeout: int | None = None) -> None:
        """تیک زدن checkbox / radio."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        el = self._page.locator(locator)
        await el.wait_for(state="visible", timeout=timeout)
        await el.check(timeout=timeout)
        await self._after_action()

    async def uncheck(self, locator: str, timeout: int | None = None) -> None:
        """برداشتن تیک checkbox."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        el = self._page.locator(locator)
        await el.wait_for(state="visible", timeout=timeout)
        await el.uncheck(timeout=timeout)
        await self._after_action()

    async def upload_file(self, locator: str, file_path: str | Path, timeout: int | None = None) -> None:
        """
        آپلود فایل از طریق input[type=file].

        Example:
          await browser.upload_file("#avatar", "/path/to/photo.jpg")
        """
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        el = self._page.locator(locator)
        await el.wait_for(state="attached", timeout=timeout)
        await el.set_input_files(str(file_path), timeout=timeout)
        await self._after_action()

    async def drag_and_drop(
        self,
        source_locator: str,
        target_locator: str,
        timeout: int | None = None,
    ) -> None:
        """
        Drag & drop از المان مبدأ به مقصد.

        Example:
          await browser.drag_and_drop("#item-1", "#trash-zone")
        """
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        source = self._page.locator(source_locator)
        target = self._page.locator(target_locator)
        await source.wait_for(state="visible", timeout=timeout)
        await target.wait_for(state="visible", timeout=timeout)
        await source.drag_to(target, timeout=timeout)
        await self._after_action()


    # ── Wait / Query ──────────────────────────────────────────────────────────

    async def wait_for_element(self, locator: str, state: str = "visible", timeout: int | None = None) -> bool:
        """انتظار تا المان به حالت مشخص برسد. True اگر پیدا شد."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        try:
            await self._page.locator(locator).wait_for(state=state, timeout=timeout)
            return True
        except Exception:
            return False

    async def wait_for_function(self, js_expression: str, timeout: int | None = None) -> Any:
        """
        صبر تا یک expression جاوااسکریپت مقدار truthy برگرداند.

        Example:
          await browser.wait_for_function("() => document.readyState === 'complete'")
          await browser.wait_for_function("() => window.__dataLoaded === true")
        """
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        return await self._page.wait_for_function(js_expression, timeout=timeout)

    async def wait_for_navigation(self, wait_until: str = "domcontentloaded", timeout: int | None = None) -> None:
        """انتظار تا ناوبری تمام شود."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        try:
            await self._page.wait_for_load_state(wait_until, timeout=timeout)
        except Exception as e:
            logger.warning(f"⚠ انتظار ناوبری timeout شد: {e}")

    async def wait_for_url(self, url_pattern: str, timeout: int | None = None) -> None:
        """انتظار تا URL به pattern مطابقت پیدا کند."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        try:
            target = f"**/{url_pattern}**" if "://" not in url_pattern else url_pattern
            await self._page.wait_for_url(target, timeout=timeout)
        except Exception as e:
            logger.warning(f"⚠ انتظار URL timeout شد: {e}")

    async def wait_seconds(self, seconds: float) -> None:
        """انتظار ثابت (با Pause-aware)."""
        await self._check_paused()
        await asyncio.sleep(seconds)

    async def is_visible(self, locator: str) -> bool:
        """True اگر المان قابل مشاهده باشد."""
        self._ensure_page()
        try:
            return await self._page.locator(locator).is_visible()
        except Exception:
            return False

    async def is_enabled(self, locator: str) -> bool:
        """True اگر المان enabled باشد (disabled نباشد)."""
        self._ensure_page()
        try:
            return await self._page.locator(locator).is_enabled()
        except Exception:
            return False

    async def is_checked(self, locator: str) -> bool:
        """True اگر checkbox تیک خورده باشد."""
        self._ensure_page()
        try:
            return await self._page.locator(locator).is_checked()
        except Exception:
            return False

    async def count_elements(self, locator: str) -> int:
        """تعداد المان‌های مطابق با locator را برمی‌گرداند."""
        self._ensure_page()
        try:
            return await self._page.locator(locator).count()
        except Exception:
            return 0

    async def get_text(self, locator: str, timeout: int | None = None) -> str:
        """متن یک المان را می‌خواند."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        el = self._page.locator(locator)
        await el.wait_for(state="visible", timeout=timeout)
        text = await el.text_content()
        return text.strip() if text else ""

    async def get_all_text(self, locator: str) -> list[str]:
        """
        متن تمام المان‌های مطابق با locator را برمی‌گرداند.

        Example:
          titles = await browser.get_all_text("h3.result-title")
          # → ["عنوان ۱", "عنوان ۲", ...]
        """
        self._ensure_page()
        try:
            return await self._page.locator(locator).all_text_contents()
        except Exception:
            return []

    async def get_attribute(self, locator: str, attribute: str, timeout: int | None = None) -> str | None:
        """مقدار یک attribute از المان."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        try:
            el = self._page.locator(locator)
            await el.wait_for(state="visible", timeout=timeout)
            return await el.get_attribute(attribute)
        except Exception as e:
            logger.error(f"❌ خطا در get_attribute '{attribute}': {e}")
            return None

    async def get_input_value(self, locator: str, timeout: int | None = None) -> str:
        """مقدار فعلی یک input / textarea را می‌خواند."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        el = self._page.locator(locator)
        await el.wait_for(state="visible", timeout=timeout)
        return await el.input_value(timeout=timeout)


    # ── JavaScript ────────────────────────────────────────────────────────────

    async def evaluate(self, expression: str) -> Any:
        """اجرای JavaScript و برگرداندن نتیجه."""
        await self._check_paused()
        self._ensure_page()
        return await self._page.evaluate(expression)

    async def evaluate_on_element(self, locator: str, js: str) -> Any:
        """
        اجرای JavaScript با المان به عنوان آرگومان اول.

        Example:
          text = await browser.evaluate_on_element("#title", "el => el.innerText")
          style = await browser.evaluate_on_element(".box", "el => el.style.color")
        """
        await self._check_paused()
        self._ensure_page()
        return await self._page.locator(locator).evaluate(js)

    # ── Scroll ────────────────────────────────────────────────────────────────

    async def scroll_to_bottom(self) -> None:
        """اسکرول به انتهای صفحه."""
        await self._check_paused()
        self._ensure_page()
        await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    async def scroll_to_top(self) -> None:
        """اسکرول به ابتدای صفحه."""
        await self._check_paused()
        self._ensure_page()
        await self._page.evaluate("window.scrollTo(0, 0)")

    async def scroll_to_element(self, locator: str) -> None:
        """اسکرول به المان مشخص."""
        await self._check_paused()
        self._ensure_page()
        await self._page.locator(locator).scroll_into_view_if_needed()

    async def scroll_by(self, x: int = 0, y: int = 500) -> None:
        """اسکرول به اندازه مشخص (px)."""
        await self._check_paused()
        self._ensure_page()
        await self._page.evaluate(f"window.scrollBy({x}, {y})")

    # ── Page Info ─────────────────────────────────────────────────────────────

    async def get_current_url(self) -> str:
        self._ensure_page()
        return self._page.url

    async def get_title(self) -> str:
        self._ensure_page()
        return await self._page.title()

    async def get_page_source(self) -> str:
        """HTML کامل صفحه فعلی."""
        self._ensure_page()
        return await self._page.content()

    # ── Tabs ──────────────────────────────────────────────────────────────────

    async def open_new_tab(self, url: str = "") -> Page:
        """باز کردن تب جدید و سوئیچ به آن."""
        await self._check_paused()
        self._ensure_page()
        new_page = await self._context.new_page()
        new_page.set_default_timeout(self._default_timeout)
        self._page = new_page
        if url:
            await new_page.goto(url)
            await self._after_action()
        return new_page

    async def switch_to_tab(self, index: int = -1) -> None:
        """
        سوئیچ به تب با شماره index (پیش‌فرض: آخرین تب).

        Example:
          await browser.switch_to_tab(0)   # اولین تب
          await browser.switch_to_tab(-1)  # آخرین تب
        """
        self._ensure_page()
        pages = self._context.pages
        if pages:
            self._page = pages[index]
            logger.info(f"سوئیچ به تب {index}: {self._page.url}")

    async def close_current_tab(self) -> None:
        """بستن تب فعلی و سوئیچ به تب قبلی."""
        self._ensure_page()
        await self._page.close()
        pages = self._context.pages
        if pages:
            self._page = pages[-1]


    # ── Cookies & Storage ─────────────────────────────────────────────────────

    async def get_cookies(self, url: str | None = None) -> list[dict]:
        """
        خواندن کوکی‌ها.

        Example:
          all_cookies = await browser.get_cookies()
          site_cookies = await browser.get_cookies("https://example.com")
        """
        self._ensure_page()
        urls = [url] if url else None
        return await self._context.cookies(urls=urls)

    async def set_cookies(self, cookies: list[dict]) -> None:
        """
        تنظیم کوکی‌ها (مثلاً برای bypass login).

        Example:
          await browser.set_cookies([
              {"name": "session", "value": "abc123", "domain": "example.com", "path": "/"}
          ])
        """
        self._ensure_page()
        await self._context.add_cookies(cookies)
        logger.info(f"🍪 {len(cookies)} کوکی تنظیم شد")

    async def clear_cookies(self) -> None:
        """پاک کردن تمام کوکی‌ها."""
        self._ensure_page()
        await self._context.clear_cookies()
        logger.info("🍪 تمام کوکی‌ها پاک شدند")

    async def get_local_storage(self, key: str) -> str | None:
        """خواندن یک مقدار از localStorage."""
        self._ensure_page()
        return await self._page.evaluate(f"() => localStorage.getItem('{key}')")

    async def set_local_storage(self, key: str, value: str) -> None:
        """نوشتن یک مقدار در localStorage."""
        self._ensure_page()
        await self._page.evaluate(f"() => localStorage.setItem('{key}', '{value}')")

    # ── Headers & Network ─────────────────────────────────────────────────────

    async def set_extra_headers(self, headers: dict[str, str]) -> None:
        """
        تنظیم هدرهای اضافی برای تمام requestها.

        Example:
          await browser.set_extra_headers({
              "Authorization": "Bearer my_token",
              "Accept-Language": "fa-IR",
          })
        """
        self._ensure_page()
        await self._page.set_extra_http_headers(headers)
        logger.info(f"🔧 هدرهای اضافی تنظیم شدند: {list(headers.keys())}")

    async def intercept_requests(
        self,
        url_pattern: str,
        handler: Callable,
    ) -> None:
        """
        رهگیری و تغییر requestها.

        handler باید async باشد و Route را قبول کند:
          async def my_handler(route):
              # ادامه بده
              await route.continue_()
              # یا response مصنوعی برگردان
              await route.fulfill(status=200, body='{"ok": true}')
              # یا بلاک کن
              await route.abort()

        Example:
          await browser.intercept_requests("**/api/**", my_handler)
        """
        self._ensure_page()
        await self._page.route(url_pattern, handler)
        logger.info(f"🔌 Request interception فعال شد: {url_pattern}")

    async def block_resources(
        self,
        resource_types: list[str] | None = None,
    ) -> None:
        """
        بلاک کردن انواع منابع برای اجرای سریع‌تر.

        resource_types می‌تواند شامل: 'image', 'stylesheet', 'font',
        'media', 'script', 'websocket', 'xhr', 'fetch' باشد.

        پیش‌فرض (None) = بلاک کردن image + stylesheet + font + media
        که معمولاً ۴۰-۶۰٪ سرعت اجرا را افزایش می‌دهد.

        Example:
          # حالت سریع — فقط HTML/JS لود می‌شود
          await browser.block_resources()

          # فقط تصاویر را بلاک کن
          await browser.block_resources(["image"])

          # همه چیز غیر از document و script را بلاک کن
          await browser.block_resources(["image", "stylesheet", "font", "media", "xhr", "fetch"])
        """
        self._ensure_page()
        blocked = resource_types or ["image", "stylesheet", "font", "media"]

        async def _block_handler(route: Route) -> None:
            if route.request.resource_type in blocked:
                await route.abort()
            else:
                await route.continue_()

        await self._page.route("**/*", _block_handler)
        logger.info(f"🚫 منابع بلاک شدند: {blocked}")

    async def unblock_resources(self) -> None:
        """برداشتن تمام route handlerها (undo block_resources)."""
        self._ensure_page()
        await self._page.unroute("**/*")
        logger.info("✅ بلاک منابع برداشته شد")

    async def wait_for_response(
        self,
        url_pattern: str,
        timeout: int | None = None,
    ) -> Any:
        """
        صبر تا یک response با URL pattern دریافت شود.

        Example:
          resp = await browser.wait_for_response("**/api/data")
          data = await resp.json()
        """
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        return await self._page.wait_for_response(url_pattern, timeout=timeout)

    async def wait_for_request(
        self,
        url_pattern: str,
        timeout: int | None = None,
    ) -> Any:
        """صبر تا یک request با URL pattern ارسال شود."""
        await self._check_paused()
        self._ensure_page()
        timeout = timeout or self._default_timeout
        return await self._page.wait_for_request(url_pattern, timeout=timeout)


    # ── Device Emulation ──────────────────────────────────────────────────────

    async def emulate_device(self, device_name: str) -> None:
        """
        شبیه‌سازی یک دستگاه موبایل/تبلت.

        نام دستگاه‌های پشتیبانی‌شده از Playwright device descriptors:
          "iPhone 13", "iPhone 13 Pro", "iPhone SE",
          "Pixel 5", "Galaxy S9+",
          "iPad Pro 11", "iPad Mini",
          "Desktop Chrome" و ...

        Example:
          await browser.emulate_device("iPhone 13")
          await browser.navigate("https://example.com")  # حالا mobile view

        NOTE: این متد context فعلی را تغییر نمی‌دهد —
        برای emulation کامل باید قبل از launch فراخوانی شود.
        اما viewport و user-agent را تغییر می‌دهد که برای اکثر سایت‌ها کافی است.
        """
        self._ensure_page()
        devices = self._playwright.devices
        if device_name not in devices:
            available = list(devices.keys())[:10]
            logger.warning(f"دستگاه '{device_name}' پیدا نشد. نمونه‌ها: {available}")
            return

        device = devices[device_name]
        if "viewport" in device:
            await self._page.set_viewport_size(device["viewport"])
        if "user_agent" in device:
            await self._page.evaluate(
                f"() => Object.defineProperty(navigator, 'userAgent', {{value: '{device['user_agent']}'}})"
            )
        logger.info(f"📱 دستگاه '{device_name}' شبیه‌سازی شد")

    async def set_viewport(self, width: int, height: int) -> None:
        """تغییر اندازه viewport."""
        self._ensure_page()
        await self._page.set_viewport_size({"width": width, "height": height})
        logger.info(f"📐 Viewport تنظیم شد: {width}×{height}")

    # ── Screenshot ────────────────────────────────────────────────────────────

    async def screenshot(self, path: str | Path | None = None, full_page: bool = False) -> Path | None:
        """اسکرین‌شات از صفحه فعلی."""
        self._ensure_page()
        if path is None:
            self._screenshots_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            uid = uuid.uuid4().hex[:6]
            path = self._screenshots_dir / f"screenshot_{ts}_{uid}.png"
        else:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
        try:
            await self._page.screenshot(path=str(path), full_page=full_page, timeout=5000)
            logger.info(f"📸 اسکرین‌شات: {path}")
            return path
        except Exception as e:
            logger.warning(f"❌ خطا در اسکرین‌شات: {e}")
            return None

    async def screenshot_element(self, locator: str, path: str | Path | None = None) -> Path | None:
        """
        اسکرین‌شات فقط از یک المان خاص (crop شده).

        Example:
          await browser.screenshot_element(".chart-container", "chart.png")
        """
        self._ensure_page()
        if path is None:
            self._screenshots_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self._screenshots_dir / f"element_{ts}.png"
        else:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
        try:
            el = self._page.locator(locator)
            await el.screenshot(path=str(path), timeout=5000)
            return path
        except Exception as e:
            logger.warning(f"❌ خطا در اسکرین‌شات المان: {e}")
            return None

    # ── Download ──────────────────────────────────────────────────────────────

    async def download_file(self, locator_or_url: str, save_dir: str | Path | None = None) -> Path | None:
        """دانلود فایل (کلیک روی المان یا URL مستقیم)."""
        await self._check_paused()
        self._ensure_page()
        save_dir = Path(save_dir) if save_dir else self._screenshots_dir.parent / "downloads"
        save_dir.mkdir(parents=True, exist_ok=True)
        try:
            if locator_or_url.startswith(("http://", "https://")):
                async with self._page.expect_download() as dl:
                    await self._page.evaluate(
                        f"""() => {{
                            const a = document.createElement('a');
                            a.href = '{locator_or_url}';
                            a.download = '';
                            document.body.appendChild(a);
                            a.click(); a.remove();
                        }}"""
                    )
                download = await dl.value
            else:
                async with self._page.expect_download() as dl:
                    await self._page.locator(locator_or_url).click()
                download = await dl.value
            name = download.suggested_filename or f"download_{uuid.uuid4().hex[:8]}"
            dest = save_dir / name
            await download.save_as(str(dest))
            logger.info(f"✅ دانلود: {dest}")
            return dest
        except Exception as e:
            logger.error(f"❌ خطا در دانلود: {e}")
            return None

    async def download_image(self, image_locator: str, save_dir: str | Path | None = None) -> Path | None:
        """دانلود تصویر از المان img."""
        await self._check_paused()
        self._ensure_page()
        save_dir = Path(save_dir) if save_dir else self._screenshots_dir.parent / "downloads"
        save_dir.mkdir(parents=True, exist_ok=True)
        try:
            img_src = await self._page.locator(image_locator).first.get_attribute("src")
            if not img_src:
                logger.error("❌ img فاقد src")
                return None
            response = await self._page.request.get(img_src)
            if response.ok:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest = save_dir / f"image_{ts}_{uuid.uuid4().hex[:6]}.png"
                dest.write_bytes(await response.body())
                logger.info(f"✅ تصویر ذخیره شد: {dest}")
                return dest
            logger.error(f"❌ HTTP {response.status} در دانلود تصویر")
            return None
        except Exception as e:
            logger.error(f"❌ خطا در دانلود تصویر: {e}")
            return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ensure_page(self) -> None:
        if self._page is None:
            raise RuntimeError("مرورگر باز نیست — ابتدا launch() را فراخوانی کنید")
        if getattr(self._page, "is_closed", lambda: False)():
            if self._context and self._context.pages:
                self._page = self._context.pages[-1]
                logger.info("تب قبلی بسته شده بود — سوئیچ به آخرین تب")
            else:
                self._context = self._page = None
                raise RuntimeError("همه تب‌ها بسته‌اند. مرورگر را مجدداً اجرا کنید.")

    async def _on_new_page(self, page: Page) -> None:
        logger.info(f"📄 تب جدید: {page.url}")
        page.set_default_timeout(self._default_timeout)

    def __repr__(self) -> str:
        s = "فعال" if self.is_launched else "غیرفعال"
        p = " | متوقف" if self.is_paused else ""
        return f"<BrowserController [{s}{p}]>"
