# -*- coding: utf-8 -*-
"""
مدیریت پروفایل Chrome

مدیریت مسیر پروفایل مرورگر Chrome برای حفظ session و کوکی‌ها بین اجراها.
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class ProfileManager:
    """
    مدیریت پروفایل مرورگر Chrome.
    
    پروفایل در مسیر %APPDATA%/AutomationPlatform/chrome_profile ذخیره می‌شود
    تا session کاربر بین اجراها حفظ شود.
    """

    def __init__(self, profile_dir: Path | None = None):
        """
        مقداردهی اولیه ProfileManager.
        
        Args:
            profile_dir: مسیر سفارشی پروفایل. اگر None باشد، از config استفاده می‌شود.
        """
        if profile_dir is None:
            from config import BROWSER_PROFILE_DIR
            self._profile_dir = BROWSER_PROFILE_DIR
        else:
            self._profile_dir = Path(profile_dir)
        
        logger.info(f"مسیر پروفایل Chrome: {self._profile_dir}")

    def get_profile_path(self) -> Path:
        """
        دریافت مسیر پروفایل و ایجاد پوشه در صورت عدم وجود.
        
        Returns:
            مسیر پوشه پروفایل Chrome
        """
        self._profile_dir.mkdir(parents=True, exist_ok=True)
        return self._profile_dir

    def profile_exists(self) -> bool:
        """
        بررسی وجود پروفایل.
        
        Returns:
            True اگر پوشه پروفایل وجود داشته باشد و خالی نباشد
        """
        if not self._profile_dir.exists():
            return False
        # بررسی اینکه پوشه خالی نباشد
        return any(self._profile_dir.iterdir())

    def clear_profile(self) -> None:
        """
        پاک کردن کامل پروفایل مرورگر.
        
        هشدار: تمام session‌ها، کوکی‌ها و داده‌های ذخیره شده حذف می‌شوند.
        """
        if self._profile_dir.exists():
            try:
                shutil.rmtree(self._profile_dir)
                self._profile_dir.mkdir(parents=True, exist_ok=True)
                logger.info("پروفایل Chrome با موفقیت پاک شد")
            except Exception as e:
                logger.error(f"خطا در پاک کردن پروفایل: {e}")
                raise

    def get_profile_size(self) -> int:
        """
        محاسبه حجم پروفایل بر حسب بایت.
        
        Returns:
            حجم کل پروفایل به بایت
        """
        if not self._profile_dir.exists():
            return 0
        total = 0
        for file_path in self._profile_dir.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
        return total
