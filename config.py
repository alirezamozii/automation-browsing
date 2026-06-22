# -*- coding: utf-8 -*-
"""
پیکربندی پروژه اتوماسیون مرورگر

این ماژول تنظیمات اصلی پروژه را شامل مسیرها، پورت‌ها و پارامترهای پیش‌فرض
مدیریت می‌کند. تمام دایرکتوری‌های مورد نیاز در زمان import ساخته می‌شوند.
"""

import os
import logging
from pathlib import Path

# ──────────────────────────────────────────────
#  مسیر پایه اپلیکیشن
# ──────────────────────────────────────────────
_APPDATA = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
APP_DIR: Path = _APPDATA / "AutomationPlatform"

# ──────────────────────────────────────────────
#  مسیر پروفایل مرورگر کروم
# ──────────────────────────────────────────────
BROWSER_PROFILE_DIR: Path = APP_DIR / "chrome_profile"

# ──────────────────────────────────────────────
#  مسیر دیتابیس SQLite
# ──────────────────────────────────────────────
DB_PATH: Path = APP_DIR / "data.db"

# ──────────────────────────────────────────────
#  مسیر ذخیره اسکرین‌شات‌ها
# ──────────────────────────────────────────────
SCREENSHOTS_DIR: Path = APP_DIR / "screenshots"

# ──────────────────────────────────────────────
#  تنظیمات سرور API
# ──────────────────────────────────────────────
API_HOST: str = "127.0.0.1"
API_PORT: int = 8765

# ──────────────────────────────────────────────
#  تنظیمات عملیاتی
# ──────────────────────────────────────────────
DEFAULT_TIMEOUT: int = 30000       # میلی‌ثانیه
MAX_RETRIES: int = 3
LOG_LEVEL: str = "INFO"

# ──────────────────────────────────────────────
#  ساخت دایرکتوری‌ها در صورت عدم وجود
# ──────────────────────────────────────────────
for _dir in (APP_DIR, BROWSER_PROFILE_DIR, SCREENSHOTS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────
#  پیکربندی لاگر پایه
# ──────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("automation_platform")
