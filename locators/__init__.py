# -*- coding: utf-8 -*-
"""
بسته لوکیتورها (Locators)

این بسته شامل کلاس پایه مدیریت لوکیتور و مجموعه‌های لوکیتور
برای سایت‌های مختلف می‌باشد.
"""

from locators.base import LocatorSet
from locators.common import GoogleLocators

__all__ = [
    "LocatorSet",
    "GoogleLocators",
]
