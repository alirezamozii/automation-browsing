# -*- coding: utf-8 -*-
"""
لایه مرورگر — مدیریت Playwright و Chrome

این ماژول شامل کنترلر مرورگر، مدیریت پروفایل و تشخیص صفحه است.
"""

from browser.controller import BrowserController
from browser.profile import ProfileManager
from browser.page_detector import PageDetector

__all__ = ["BrowserController", "ProfileManager", "PageDetector"]
