# -*- coding: utf-8 -*-
"""
مدیریت پروفایل Chrome

مدیریت مسیر پروفایل مرورگر Chrome برای حفظ session و کوکی‌ها بین اجراها.
"""

import logging
import os
import shutil
import subprocess
import sys
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

    def cleanup_for_launch(self) -> None:
        """
        پاکسازی پروفایل قبل از لانچ مرورگر جدید.
        
        این متد:
          1. تمام پروسه‌های Chrome که از این پروفایل استفاده می‌کنند را kill می‌کند
          2. فایل lockfile را حذف می‌کند
        
        این عملیات مشکل "Failed to create a ProcessSingleton" را حل می‌کند.
        """
        logger.info("🧹 پاکسازی پروفایل قبل از لانچ مرورگر...")
        
        # مرحله ۱: kill کردن پروسه‌های Chrome مرتبط با این پروفایل
        self._kill_stale_chrome_processes()
        
        # مرحله ۲: حذف lock file
        self._remove_lock_file()
        
        # مرحله ۳: اصلاح فایل Preferences برای جلوگیری از حباب بازیابی
        self._fix_preferences_for_clean_exit()
        
        logger.info("✅ پاکسازی پروفایل کامل شد")

    def _kill_stale_chrome_processes(self) -> None:
        """
        یافتن و kill کردن تمام پروسه‌های Chrome که از پروفایل اتوماسیون استفاده می‌کنند.
        
        از WMI در ویندوز برای بررسی CommandLine هر پروسه chrome.exe استفاده می‌کند.
        """
        profile_str = str(self._profile_dir)
        killed_count = 0
        
        if sys.platform == "win32":
            try:
                # دریافت لیست پروسه‌های chrome با CommandLine
                result = subprocess.run(
                    [
                        "powershell", "-NoProfile", "-Command",
                        (
                            "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" "
                            "| Select-Object ProcessId, CommandLine "
                            "| ConvertTo-Json"
                        ),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                
                if result.returncode != 0 or not result.stdout.strip():
                    logger.debug("هیچ پروسه Chrome‌ای یافت نشد")
                    return
                
                import json
                data = json.loads(result.stdout)
                
                # اگر فقط یک پروسه باشد، json.loads یک dict برمی‌گرداند نه list
                if isinstance(data, dict):
                    data = [data]
                
                for proc in data:
                    cmd_line = proc.get("CommandLine") or ""
                    pid = proc.get("ProcessId")
                    
                    if not pid:
                        continue
                    
                    # Normalize paths for comparison (Windows CMD might have escaped backslashes)
                    normalized_cmd = cmd_line.replace("\\\\", "\\").replace("\\", "/").lower()
                    normalized_prof = profile_str.replace("\\", "/").lower()
                    
                    # فقط پروسه‌هایی که از پروفایل اتوماسیون استفاده می‌کنند
                    if normalized_prof in normalized_cmd:
                        try:
                            subprocess.run(
                                ["taskkill", "/F", "/PID", str(pid)],
                                capture_output=True,
                                timeout=5,
                            )
                            killed_count += 1
                            logger.debug(f"پروسه Chrome با PID {pid} kill شد")
                        except Exception as e:
                            logger.debug(f"عدم توانایی در kill پروسه {pid}: {e}")
                
            except subprocess.TimeoutExpired:
                logger.warning("تایم‌اوت در بررسی پروسه‌های Chrome")
            except Exception as e:
                logger.warning(f"خطا در بررسی پروسه‌های Chrome: {e}")
        else:
            # لینوکس / مک
            try:
                result = subprocess.run(
                    ["pgrep", "-a", "chrome"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                for line in result.stdout.strip().splitlines():
                    if profile_str in line:
                        pid = line.split()[0]
                        try:
                            subprocess.run(["kill", "-9", pid], timeout=5)
                            killed_count += 1
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"خطا در بررسی پروسه‌های Chrome: {e}")
        
        if killed_count > 0:
            logger.info(f"🔪 {killed_count} پروسه Chrome قدیمی kill شد")
            # کمی صبر تا پروسه‌ها کاملاً بسته شوند
            import time
            time.sleep(1)
        else:
            logger.debug("هیچ پروسه Chrome قدیمی‌ای یافت نشد")

    def _remove_lock_file(self) -> None:
        """
        حذف فایل lockfile از پروفایل Chrome.
        
        این فایل توسط Chrome ایجاد می‌شود و اگر Chrome به درستی بسته نشود،
        باقی می‌ماند و مانع از اجرای مجدد می‌شود.
        """
        lock_files = ["lockfile", "SingletonLock", "SingletonSocket", "SingletonCookie"]
        
        for lock_name in lock_files:
            lock_path = self._profile_dir / lock_name
            if lock_path.exists():
                try:
                    lock_path.unlink()
                    logger.info(f"🔓 فایل قفل حذف شد: {lock_name}")
                except PermissionError:
                    logger.warning(f"عدم دسترسی برای حذف {lock_name} — احتمالاً هنوز در استفاده است")
                except Exception as e:
                    logger.warning(f"خطا در حذف {lock_name}: {e}")

    def _fix_preferences_for_clean_exit(self) -> None:
        """
        اصلاح فایل Preferences و Local State برای جلوگیری از حباب بازیابی.
        
        بعد از kill اجباری Chrome، مقدار exit_type به 'Crashed' تغییر می‌کند
        و Chrome در اجرای بعدی حباب 'Chrome didn't shut down correctly' را نشان می‌دهد.
        این متد آن مقادیر را به حالت نرمال برمی‌گرداند.
        """
        import json
        
        prefs_files = ["Preferences", "Default/Preferences"]
        
        for pref_name in prefs_files:
            pref_path = self._profile_dir / pref_name
            if pref_path.exists():
                try:
                    data = json.loads(pref_path.read_text(encoding="utf-8"))
                    
                    modified = False
                    
                    # اصلاح exit_type و exited_cleanly
                    if "profile" in data:
                        if data["profile"].get("exit_type") != "Normal":
                            data["profile"]["exit_type"] = "Normal"
                            modified = True
                        if not data["profile"].get("exited_cleanly", True):
                            data["profile"]["exited_cleanly"] = True
                            modified = True
                    
                    if modified:
                        pref_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                        logger.info(f"🔧 فایل {pref_name} اصلاح شد (exit_type=Normal)")
                    
                except Exception as e:
                    logger.debug(f"خطا در اصلاح {pref_name}: {e}")
        
        # اصلاح Local State
        local_state_path = self._profile_dir / "Local State"
        if local_state_path.exists():
            try:
                data = json.loads(local_state_path.read_text(encoding="utf-8"))
                
                modified = False
                if "profile" in data:
                    if data["profile"].get("exit_type") != "Normal":
                        data["profile"]["exit_type"] = "Normal"
                        modified = True
                    if not data["profile"].get("exited_cleanly", True):
                        data["profile"]["exited_cleanly"] = True
                        modified = True
                
                if modified:
                    local_state_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    logger.info("🔧 فایل Local State اصلاح شد")
                    
            except Exception as e:
                logger.debug(f"خطا در اصلاح Local State: {e}")

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
