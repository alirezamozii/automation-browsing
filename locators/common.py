# -*- coding: utf-8 -*-
"""
لوکیتورهای گوگل (Google Locators)

مجموعه سلکتورهای CSS/XPath برای صفحات مختلف گوگل.
هر سلکتور دارای جایگزین‌های متعدد برای افزایش پایداری است.
"""

import logging

from locators.base import LocatorSet

logger = logging.getLogger("automation_platform.locators.common")


class GoogleLocators(LocatorSet):
    """
    لوکیتورهای سایت گوگل

    شامل سلکتورهای کادر جستجو، نتایج، تب تصاویر و المان‌های
    تصویر. هر سلکتور با جایگزین‌های متعدد برای مقاومت در برابر
    تغییرات DOM تعریف شده است.
    """

    def __init__(self) -> None:
        """مقداردهی اولیه و ثبت تمام سلکتورها."""
        super().__init__()

        # ──────────── کادر جستجو ────────────
        self.set("search_box", [
            'textarea[name="q"]',
            'input[name="q"]',
            "#APjFqb",
        ])

        # ──────────── دکمه جستجو ────────────
        self.set("search_button", [
            'input[name="btnK"]',
            'button[aria-label="Google Search"]',
            ".FPdoLc input[type='submit']",
        ])

        # ──────────── ناحیه نتایج جستجو ────────────
        self.set("search_results", [
            "#search",
            "#rso",
            "div[data-async-context]",
        ])

        # ──────────── تب تصاویر ────────────
        self.set("images_tab", [
            'a[href*="tbm=isch"]',
            'a:has-text("Images")',
            'a:has-text("تصاویر")',
            'div[role="navigation"] a:nth-child(2)',
        ])

        # ──────────── اولین تصویر در نتایج ────────────
        self.set("first_image", [
            "#islrg img:first-child",
            'div[data-ri="0"] img',
            "#search img:first-of-type",
        ])

        # ──────────── تصویر بزرگ (پس از کلیک) ────────────
        self.set("large_image", [
            'img[jsname="kn3ccd"]',
            'img.sFlh5c',
            'img[data-iml]',
        ])

        # ──────────── دکمه «موافقم» (GDPR consent) ────────────
        self.set("consent_button", [
            'button[id="L2AGLb"]',
            'button:has-text("I agree")',
            'button:has-text("Accept all")',
        ])

        logger.debug(
            "GoogleLocators: %d لوکیتور ثبت شد",
            len(self.names),
        )
