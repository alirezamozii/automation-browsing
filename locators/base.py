# -*- coding: utf-8 -*-
"""
کلاس پایه مدیریت لوکیتورها (Locator Set)

این ماژول یک سیستم مدیریت لوکیتور مبتنی بر دیکشنری با پشتیبانی
از لوکیتور جایگزین (fallback) فراهم می‌کند. اگر لوکیتور اصلی
یافت نشود، لوکیتور جایگزین استفاده می‌شود.
"""

import logging

logger = logging.getLogger("automation_platform.locators.base")


class LocatorSet:
    """
    مجموعه لوکیتورها با پشتیبانی از جایگزین (fallback)

    لوکیتورها به صورت دیکشنری ذخیره می‌شوند. هر لوکیتور می‌تواند
    یک مقدار ساده (str) یا لیستی از مقادیر جایگزین باشد.
    """

    def __init__(self) -> None:
        """مقداردهی اولیه با دیکشنری خالی."""
        self._locators: dict[str, str | list[str]] = {}
        logger.debug("LocatorSet '%s' مقداردهی شد", self.__class__.__name__)

    def set(self, name: str, selector: str | list[str]) -> None:
        """
        تنظیم یک لوکیتور

        Args:
            name: نام یکتای لوکیتور
            selector: سلکتور CSS/XPath یا لیست سلکتورهای جایگزین
        """
        self._locators[name] = selector
        logger.debug("لوکیتور '%s' تنظیم شد", name)

    def get(self, name: str, fallback_index: int = 0) -> str:
        """
        دریافت سلکتور لوکیتور بر اساس نام

        اگر لوکیتور یک لیست باشد، سلکتور با اندیس مشخص‌شده
        بازگردانده می‌شود. اگر اندیس خارج از محدوده باشد،
        اولین سلکتور بازگردانده می‌شود.

        Args:
            name: نام لوکیتور
            fallback_index: اندیس سلکتور جایگزین (پیش‌فرض ۰ = اصلی)

        Returns:
            سلکتور CSS/XPath

        Raises:
            KeyError: اگر لوکیتور با این نام وجود نداشته باشد
        """
        if name not in self._locators:
            msg = (
                f"لوکیتور '{name}' یافت نشد. "
                f"موجود: {list(self._locators.keys())}"
            )
            logger.error(msg)
            raise KeyError(msg)

        value = self._locators[name]

        if isinstance(value, list):
            if 0 <= fallback_index < len(value):
                return value[fallback_index]
            logger.warning(
                "اندیس %d برای لوکیتور '%s' خارج از محدوده، استفاده از اولین",
                fallback_index,
                name,
            )
            return value[0]

        return value

    def get_all_fallbacks(self, name: str) -> list[str]:
        """
        دریافت تمام سلکتورهای جایگزین یک لوکیتور

        Args:
            name: نام لوکیتور

        Returns:
            لیست تمام سلکتورهای موجود (همیشه لیست)

        Raises:
            KeyError: اگر لوکیتور وجود نداشته باشد
        """
        if name not in self._locators:
            msg = f"لوکیتور '{name}' یافت نشد."
            logger.error(msg)
            raise KeyError(msg)

        value = self._locators[name]
        if isinstance(value, list):
            return value
        return [value]

    def has(self, name: str) -> bool:
        """
        بررسی وجود لوکیتور

        Args:
            name: نام لوکیتور

        Returns:
            True اگر لوکیتور موجود باشد
        """
        return name in self._locators

    @property
    def names(self) -> list[str]:
        """لیست نام تمام لوکیتورهای ثبت‌شده."""
        return list(self._locators.keys())

    def to_dict(self) -> dict[str, str | list[str]]:
        """
        تبدیل لوکیتورها به دیکشنری

        Returns:
            کپی از دیکشنری لوکیتورها
        """
        return dict(self._locators)

    def __repr__(self) -> str:
        return f"LocatorSet({self.__class__.__name__}, count={len(self._locators)})"
