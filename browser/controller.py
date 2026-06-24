# -*- coding: utf-8 -*-
"""
کنترلر مرورگر — لایه انتزاعی Playwright

لایه اصلی ارتباط با مرورگر Chrome از طریق Playwright.
تمام عملیات مرورگر (کلیک، تایپ، ناوبری و...) از این لایه عبور می‌کنند.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from browser.profile import ProfileManager
from config import DEFAULT_TIMEOUT, SCREENSHOTS_DIR

logger = logging.getLogger(__name__)


class BrowserController:
    """
    کنترلر اصلی مرورگر.
    
    این کلاس لایه انتزاعی روی Playwright فراهم می‌کند و قابلیت‌های
    Pause/Resume، مدیریت خطا و اسکرین‌شات اتوماتیک را اضافه می‌کند.
    
    ویژگی‌ها:
        - استفاده از Chrome واقعی با پروفایل ثابت
        - پشتیبانی از Pause/Resume با asyncio.Event
        - Smart click و fill با wait_for(visible)
        - اسکرین‌شات اتوماتیک هنگام خطا
        - دانلود فایل
    """

    def __init__(self, profile_manager: ProfileManager | None = None):
        """
        مقداردهی اولیه BrowserController.
        
        Args:
            profile_manager: مدیریت‌کننده پروفایل. اگر None باشد، یکی ساخته می‌شود.
        """
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._profile_manager = profile_manager or ProfileManager()
        
        # سیستم Pause/Resume
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # شروع به حالت فعال (not paused)
        self._is_paused = False
        
        # تنظیمات
        self._default_timeout = DEFAULT_TIMEOUT
        self._screenshots_dir = SCREENSHOTS_DIR
        self.on_action = None

    # ────────────────────────────── Properties ──────────────────────────────

    @property
    def page(self) -> Page | None:
        """صفحه فعلی مرورگر"""
        return self._page

    @property
    def context(self) -> BrowserContext | None:
        """Context مرورگر"""
        return self._context

    @property
    def browser(self) -> Browser | None:
        """نمونه مرورگر"""
        return self._browser

    @property
    def is_launched(self) -> bool:
        """آیا مرورگر باز است؟"""
        if self._context is None:
            return False
        # اگر کاربر همه تب‌ها را ببندد، طول صفحات صفر می‌شود و یعنی مرورگر عملاً بسته است
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
        """آیا سیستم در حالت Pause است؟"""
        return self._is_paused

    # ────────────────────────────── Lifecycle ──────────────────────────────

    async def launch(self, headless: bool = False) -> Page:
        """
        باز کردن مرورگر Chrome واقعی با پروفایل ثابت.
        
        از Chrome نصب‌شده روی سیستم استفاده می‌کند (channel='chrome')
        و پروفایل ثابت برای حفظ session بین اجراها.
        
        قبل از لانچ، پروسه‌های Chrome قدیمی مرتبط با این پروفایل
        و فایل‌های قفل پاکسازی می‌شوند.
        
        Returns:
            آبجکت Page آماده استفاده
        
        Raises:
            RuntimeError: اگر مرورگر قبلاً باز باشد
        """
        if self.is_launched:
            logger.warning("مرورگر قبلاً باز است")
            return self._page

        logger.info("🚀 در حال باز کردن مرورگر Chrome...")
        
        # پاکسازی پروسه‌های قدیمی و lock file قبل از لانچ
        self._profile_manager.cleanup_for_launch()
        
        profile_path = self._profile_manager.get_profile_path()
        
        self._playwright = await async_playwright().start()
        
        # تعیین User-Agent طبیعی برای جلوگیری از شناسایی در حالت Headless
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        # استفاده از persistent context برای حفظ session
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            channel="chrome",
            headless=headless,
            user_agent=user_agent,
            no_viewport=True,  # بدون محدودیت viewport — اجازه می‌دهد --start-maximized کار کند
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
            ],
            ignore_default_args=["--enable-automation"],
        )
        
        # انتظار کوتاه تا Chrome کاملاً آماده شود
        await asyncio.sleep(1)
        
        # استفاده از صفحه اول یا ساخت صفحه جدید
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()
        
        # تنظیم timeout پیش‌فرض
        self._page.set_default_timeout(self._default_timeout)
        self._page.set_default_navigation_timeout(self._default_timeout)
        
        # تنظیم دانلود
        self._context.on("page", self._on_new_page)
        
        logger.info("✅ مرورگر Chrome با موفقیت باز شد")
        return self._page

    async def close(self) -> None:
        """
        بستن مرورگر و آزادسازی منابع.
        """
        logger.info("🔒 در حال بستن مرورگر...")
        
        try:
            if self._context:
                await self._context.close()
                self._context = None
                self._page = None
                self._browser = None
        except Exception as e:
            logger.error(f"خطا در بستن context: {e}")
        
        try:
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception as e:
            logger.error(f"خطا در بستن Playwright: {e}")
        
        logger.info("✅ مرورگر بسته شد")

    # ────────────────────────────── Pause/Resume ──────────────────────────────

    def pause(self) -> None:
        """
        متوقف کردن عملیات مرورگر.
        
        تمام عملیات بعدی منتظر می‌مانند تا resume() فراخوانی شود.
        کاربر می‌تواند در این حالت به صورت دستی با مرورگر کار کند.
        """
        if not self._is_paused:
            self._is_paused = True
            self._pause_event.clear()
            logger.info("⏸ مرورگر Pause شد — کاربر می‌تواند دستی کار کند")

    def resume(self) -> None:
        """
        ادامه دادن عملیات مرورگر بعد از Pause.
        """
        if self._is_paused:
            self._is_paused = False
            self._pause_event.set()
            logger.info("▶ مرورگر Resume شد — ادامه عملیات اتوماتیک")

    async def _check_paused(self) -> None:
        """
        بررسی وضعیت Pause قبل از هر عملیات.
        
        اگر سیستم Pause باشد، منتظر می‌ماند تا Resume شود.
        """
        if self._is_paused:
            logger.debug("⏳ منتظر Resume...")
            await self._pause_event.wait()

    async def _after_action(self) -> None:
        """گرفتن اسکرین‌شات بعد از هر عملیات موفق و اجرای کالبک"""
        if self.on_action:
            try:
                # گرفتن اسکرین‌شات با مسیر خودکار
                screenshot_path = await self.screenshot()
                # فراخوانی کالبک ثبت لاگ
                await self.on_action(screenshot_path)
            except Exception as e:
                logger.debug(f"خطا در گرفتن اسکرین‌شات پس از عملیات: {e}")

    # ────────────────────────────── Browser Actions ──────────────────────────────

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """
        ناوبری به URL مشخص.
        
        Args:
            url: آدرس مقصد
            wait_until: شرط اتمام لود ('load', 'domcontentloaded', 'networkidle', 'commit')
        """
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

    async def click(self, locator: str, timeout: int | None = None) -> None:
        """
        کلیک روی المان با انتظار تا visible شدن.
        
        Args:
            locator: سلکتور المان (CSS, XPath, text, etc.)
            timeout: زمان انتظار به میلی‌ثانیه
        """
        await self._check_paused()
        self._ensure_page()
        
        timeout = timeout or self._default_timeout
        logger.debug(f"🖱 کلیک روی: {locator}")
        
        try:
            element = self._page.locator(locator)
            await element.wait_for(state="visible", timeout=timeout)
            await element.click(timeout=timeout)
            logger.debug(f"✅ کلیک موفق: {locator}")
            await self._after_action()
        except Exception as e:
            logger.error(f"❌ خطا در کلیک روی '{locator}': {e}")
            raise

    async def fill(self, locator: str, value: str, timeout: int | None = None) -> None:
        """
        پر کردن فیلد ورودی با مقدار مشخص.
        
        ابتدا فیلد را پاک می‌کند و سپس مقدار جدید را وارد می‌کند.
        
        Args:
            locator: سلکتور فیلد ورودی
            value: مقدار برای وارد کردن
            timeout: زمان انتظار
        """
        await self._check_paused()
        self._ensure_page()
        
        timeout = timeout or self._default_timeout
        logger.debug(f"⌨ پر کردن '{locator}' با مقدار: '{value[:50]}...' " if len(value) > 50 else f"⌨ پر کردن '{locator}' با مقدار: '{value}'")
        
        try:
            element = self._page.locator(locator)
            await element.wait_for(state="visible", timeout=timeout)
            await element.fill(value, timeout=timeout)
            logger.debug(f"✅ فیلد پر شد: {locator}")
            await self._after_action()
        except Exception as e:
            logger.error(f"❌ خطا در پر کردن '{locator}': {e}")
            raise

    async def type_text(self, locator: str, text: str, delay: float = 50, timeout: int | None = None) -> None:
        """
        تایپ متن کاراکتر به کاراکتر (شبیه‌سازی تایپ انسانی).
        
        Args:
            locator: سلکتور فیلد
            text: متن برای تایپ
            delay: تاخیر بین هر کاراکتر به میلی‌ثانیه
            timeout: زمان انتظار
        """
        await self._check_paused()
        self._ensure_page()
        
        timeout = timeout or self._default_timeout
        logger.debug(f"⌨ تایپ در '{locator}': '{text[:30]}...' " if len(text) > 30 else f"⌨ تایپ در '{locator}': '{text}'")
        
        try:
            element = self._page.locator(locator)
            await element.wait_for(state="visible", timeout=timeout)
            await element.click(timeout=timeout)
            await element.type(text, delay=delay)
            logger.debug(f"✅ تایپ موفق: {locator}")
            await self._after_action()
        except Exception as e:
            logger.error(f"❌ خطا در تایپ در '{locator}': {e}")
            raise

    async def press_key(self, key: str, locator: str | None = None) -> None:
        """
        فشار دادن کلید.
        
        Args:
            key: نام کلید (Enter, Tab, Escape, etc.)
            locator: سلکتور المان (اختیاری — اگر None باشد روی صفحه فشار می‌دهد)
        """
        await self._check_paused()
        self._ensure_page()
        
        logger.debug(f"⌨ فشار کلید: {key}")
        
        try:
            if locator:
                element = self._page.locator(locator)
                await element.press(key)
            else:
                await self._page.keyboard.press(key)
            await self._after_action()
        except Exception as e:
            logger.error(f"❌ خطا در فشار کلید '{key}': {e}")
            raise

    async def wait_for_element(
        self,
        locator: str,
        state: str = "visible",
        timeout: int | None = None,
    ) -> bool:
        """
        انتظار برای ظاهر شدن المان.
        
        Args:
            locator: سلکتور المان
            state: وضعیت مورد انتظار ('visible', 'hidden', 'attached', 'detached')
            timeout: زمان انتظار
        
        Returns:
            True اگر المان پیدا شد
        """
        await self._check_paused()
        self._ensure_page()
        
        timeout = timeout or self._default_timeout
        logger.debug(f"⏳ انتظار برای '{locator}' (state={state})")
        
        try:
            element = self._page.locator(locator)
            await element.wait_for(state=state, timeout=timeout)
            return True
        except Exception:
            logger.debug(f"⏰ Timeout — المان '{locator}' پیدا نشد")
            return False

    async def get_text(self, locator: str, timeout: int | None = None) -> str:
        """
        خواندن متن المان.
        
        Args:
            locator: سلکتور المان
            timeout: زمان انتظار
        
        Returns:
            متن المان
        """
        await self._check_paused()
        self._ensure_page()
        
        timeout = timeout or self._default_timeout
        
        try:
            element = self._page.locator(locator)
            await element.wait_for(state="visible", timeout=timeout)
            text = await element.text_content()
            return text.strip() if text else ""
        except Exception as e:
            logger.error(f"❌ خطا در خواندن متن '{locator}': {e}")
            raise

    async def is_visible(self, locator: str) -> bool:
        """
        بررسی قابل مشاهده بودن المان.
        
        Args:
            locator: سلکتور المان
        
        Returns:
            True اگر المان قابل مشاهده باشد
        """
        self._ensure_page()
        
        try:
            element = self._page.locator(locator)
            return await element.is_visible()
        except Exception:
            return False

    async def get_attribute(self, locator: str, attribute: str, timeout: int | None = None) -> str | None:
        """
        دریافت مقدار attribute یک المان.
        
        Args:
            locator: سلکتور المان
            attribute: نام attribute
            timeout: زمان انتظار
        
        Returns:
            مقدار attribute یا None
        """
        await self._check_paused()
        self._ensure_page()
        
        timeout = timeout or self._default_timeout
        
        try:
            element = self._page.locator(locator)
            await element.wait_for(state="visible", timeout=timeout)
            return await element.get_attribute(attribute)
        except Exception as e:
            logger.error(f"❌ خطا در خواندن attribute '{attribute}' از '{locator}': {e}")
            return None

    async def wait_for_navigation(self, wait_until: str = "domcontentloaded", timeout: int | None = None) -> None:
        """
        انتظار برای اتمام ناوبری (بعد از کلیک روی لینک).
        
        Args:
            wait_until: شرط اتمام
            timeout: زمان انتظار
        """
        await self._check_paused()
        self._ensure_page()
        
        timeout = timeout or self._default_timeout
        
        try:
            await self._page.wait_for_load_state(wait_until, timeout=timeout)
        except Exception as e:
            logger.warning(f"⚠ انتظار ناوبری timeout شد: {e}")

    async def wait_for_url(self, url_pattern: str, timeout: int | None = None) -> None:
        """
        انتظار تا URL صفحه با الگو مطابقت پیدا کند.
        
        Args:
            url_pattern: الگوی URL (می‌تواند regex یا substring باشد)
            timeout: زمان انتظار
        """
        await self._check_paused()
        self._ensure_page()
        
        timeout = timeout or self._default_timeout
        
        try:
            await self._page.wait_for_url(f"**/{url_pattern}**" if "://" not in url_pattern else url_pattern, timeout=timeout)
        except Exception as e:
            logger.warning(f"⚠ انتظار URL timeout شد: {e}")

    # ────────────────────────────── Screenshot ──────────────────────────────

    async def screenshot(self, path: str | Path | None = None, full_page: bool = False) -> Path | None:
        """
        گرفتن اسکرین‌شات از صفحه فعلی.
        
        Args:
            path: مسیر ذخیره. اگر None باشد، خودکار تولید می‌شود.
            full_page: آیا تمام صفحه باشد یا فقط viewport
        
        Returns:
            مسیر فایل اسکرین‌شات یا None در صورت بروز خطا
        """
        self._ensure_page()
        
        if path is None:
            self._screenshots_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique = uuid.uuid4().hex[:6]
            path = self._screenshots_dir / f"screenshot_{timestamp}_{unique}.png"
        else:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # استفاده از تایم‌اوت ۵ ثانیه‌ای برای جلوگیری از مسدود شدن طولانی توسط فونت‌ها
            await self._page.screenshot(path=str(path), full_page=full_page, timeout=5000)
            logger.info(f"📸 اسکرین‌شات ذخیره شد: {path}")
            return path
        except Exception as e:
            logger.warning(f"❌ خطا در گرفتن اسکرین‌شات: {e}")
            return None

    # ────────────────────────────── Download ──────────────────────────────

    async def download_file(self, locator_or_url: str, save_dir: str | Path | None = None) -> Path | None:
        """
        دانلود فایل با کلیک روی المان یا ناوبری به URL.
        
        Args:
            locator_or_url: سلکتور المان دانلود یا URL مستقیم فایل
            save_dir: پوشه ذخیره. اگر None باشد، از downloads استفاده می‌شود.
        
        Returns:
            مسیر فایل دانلود شده یا None در صورت خطا
        """
        await self._check_paused()
        self._ensure_page()
        
        if save_dir is None:
            save_dir = self._screenshots_dir.parent / "downloads"
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            if locator_or_url.startswith(("http://", "https://")):
                # دانلود مستقیم از URL
                logger.info(f"📥 دانلود مستقیم از URL: {locator_or_url}")
                async with self._page.expect_download() as download_info:
                    await self._page.evaluate(
                        f"""() => {{
                            const a = document.createElement('a');
                            a.href = '{locator_or_url}';
                            a.download = '';
                            document.body.appendChild(a);
                            a.click();
                            a.remove();
                        }}"""
                    )
                download = await download_info.value
            else:
                # دانلود با کلیک روی المان
                logger.info(f"📥 دانلود با کلیک روی: {locator_or_url}")
                async with self._page.expect_download() as download_info:
                    await self._page.locator(locator_or_url).click()
                download = await download_info.value
            
            # ذخیره فایل
            suggested_name = download.suggested_filename or f"download_{uuid.uuid4().hex[:8]}"
            save_path = save_dir / suggested_name
            await download.save_as(str(save_path))
            
            logger.info(f"✅ فایل دانلود شد: {save_path}")
            return save_path
            
        except Exception as e:
            logger.error(f"❌ خطا در دانلود: {e}")
            return None

    async def download_image(self, image_locator: str, save_dir: str | Path | None = None) -> Path | None:
        """
        دانلود تصویر از المان img.
        
        ابتدا src تصویر را می‌خواند و سپس با fetch دانلود می‌کند.
        
        Args:
            image_locator: سلکتور المان img
            save_dir: پوشه ذخیره
        
        Returns:
            مسیر فایل ذخیره شده
        """
        await self._check_paused()
        self._ensure_page()
        
        if save_dir is None:
            save_dir = self._screenshots_dir.parent / "downloads"
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # دریافت URL تصویر
            element = self._page.locator(image_locator).first
            img_src = await element.get_attribute("src")
            
            if not img_src:
                logger.error("❌ المان img فاقد attribute src است")
                return None
            
            logger.info(f"📥 دانلود تصویر از: {img_src[:100]}...")
            
            # دانلود با JavaScript fetch
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image_{timestamp}_{uuid.uuid4().hex[:6]}.png"
            save_path = save_dir / filename
            
            # استفاده از Playwright برای دانلود
            response = await self._page.request.get(img_src)
            if response.ok:
                body = await response.body()
                save_path.write_bytes(body)
                logger.info(f"✅ تصویر ذخیره شد: {save_path}")
                return save_path
            else:
                logger.error(f"❌ خطا در دانلود تصویر — HTTP {response.status}")
                return None
                
        except Exception as e:
            logger.error(f"❌ خطا در دانلود تصویر: {e}")
            return None

    # ────────────────────────────── Helpers ──────────────────────────────

    def _ensure_page(self) -> None:
        """بررسی اینکه صفحه‌ای فعال وجود دارد"""
        if self._page is None:
            raise RuntimeError("مرورگر هنوز باز نشده — ابتدا launch() را فراخوانی کنید")
        
        # اگر کاربر تب فعلی را ببندد، تب دیگری را انتخاب کن
        if getattr(self._page, "is_closed", lambda: False)():
            if self._context and len(self._context.pages) > 0:
                self._page = self._context.pages[-1]
                logger.info("صفحه قبلی بسته شده بود، جایگزین شد با آخرین تب باز.")
            else:
                self._context = None
                self._page = None
                raise RuntimeError("همه تب‌ها بسته شده‌اند. لطفا مرورگر را مجددا اجرا کنید.")

    async def _on_new_page(self, page: Page) -> None:
        """هندل کردن باز شدن صفحه جدید (popup, new tab)"""
        logger.info(f"📄 صفحه جدید باز شد: {page.url}")
        # می‌توان صفحه جدید را ردیابی کرد
        page.set_default_timeout(self._default_timeout)

    async def evaluate(self, expression: str) -> Any:
        """
        اجرای JavaScript در صفحه.
        
        Args:
            expression: کد JavaScript
        
        Returns:
            نتیجه اجرای JavaScript
        """
        await self._check_paused()
        self._ensure_page()
        return await self._page.evaluate(expression)

    async def get_current_url(self) -> str:
        """دریافت URL فعلی صفحه"""
        self._ensure_page()
        return self._page.url

    async def get_title(self) -> str:
        """دریافت عنوان صفحه فعلی"""
        self._ensure_page()
        return await self._page.title()

    async def scroll_to_bottom(self) -> None:
        """اسکرول به انتهای صفحه"""
        await self._check_paused()
        self._ensure_page()
        await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    async def scroll_to_element(self, locator: str) -> None:
        """اسکرول تا المان مشخص"""
        await self._check_paused()
        self._ensure_page()
        element = self._page.locator(locator)
        await element.scroll_into_view_if_needed()

    async def wait_seconds(self, seconds: float) -> None:
        """
        انتظار به مدت مشخص (با پشتیبانی از Pause).
        
        Args:
            seconds: مدت انتظار به ثانیه
        """
        await self._check_paused()
        await asyncio.sleep(seconds)

    def __repr__(self) -> str:
        status = "فعال" if self.is_launched else "غیرفعال"
        paused = " | متوقف" if self.is_paused else ""
        return f"<BrowserController [{status}{paused}]>"
