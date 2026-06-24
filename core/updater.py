import os
import sys
import zipfile
import shutil
import urllib.request
import logging
import asyncio
from pathlib import Path
import time
import json

logger = logging.getLogger("automation_platform.updater")

GITHUB_REPO_URL = "https://github.com/alirezamozii/automation-browsing/archive/refs/heads/main.zip"
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/alirezamozii/automation-browsing/main/version.json"

def parse_version(v_str):
    """تبدیل رشته ورژن به تاپل برای مقایسه آسان (مثلاً '1.0.2' -> (1, 0, 2))"""
    try:
        return tuple(map(int, v_str.strip('v').split('.')))
    except:
        return (0, 0, 0)

async def check_for_updates():
    """
    بررسی گیت‌هاب برای فایل version.json و مقایسه با نسخه فعلی
    """
    try:
        def fetch():
            req = urllib.request.Request(GITHUB_VERSION_URL, headers={"User-Agent": "AutomationPlatform"})
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())

        try:
            remote_data = await asyncio.to_thread(fetch)
            latest_version = remote_data.get("version", "1.0.0")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # If version.json doesn't exist on remote yet
                latest_version = "1.0.0"
            else:
                raise

        # خواندن نسخه لوکال
        base_dir = Path(__file__).resolve().parent.parent
        version_file = base_dir / "version.json"
        
        local_version = "1.0.0"
        if version_file.exists():
            try:
                with open(version_file, "r") as f:
                    local_data = json.load(f)
                    local_version = local_data.get("version", "1.0.0")
            except:
                pass
                
        if parse_version(latest_version) > parse_version(local_version):
            return {
                "update_available": True,
                "latest_version": latest_version,
                "local_version": local_version,
                "message": f"نسخه جدید ({latest_version}) موجود است. شما در نسخه {local_version} هستید."
            }
            
        return {"update_available": False, "message": f"شما از آخرین نسخه ({local_version}) استفاده می‌کنید."}
        
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        return {"update_available": False, "message": f"خطا در بررسی آپدیت: {str(e)}"}

async def update_from_github(progress_callback=None):
    """
    دانلود سورس کد از گیت‌هاب و جایگزینی فایل‌های تغییر یافته
    با قابلیت گزارش پیشرفت دانلود
    """
    logger.info("شروع فرآیند آپدیت از گیت‌هاب...")
    try:
        base_dir = Path(__file__).resolve().parent.parent
        temp_zip = base_dir / "update_temp.zip"
        extract_dir = base_dir / "update_extract"
        
        # 1. گرفتن آخرین SHA
        latest_sha = None
        try:
            req = urllib.request.Request(GITHUB_API_URL, headers={"User-Agent": "AutomationPlatform"})
            with urllib.request.urlopen(req) as response:
                latest_sha = json.loads(response.read().decode()).get("sha")
        except Exception as e:
            logger.warning(f"Could not fetch latest SHA: {e}")

        # 2. دانلود فایل زیپ از گیت‌هاب (با chunking برای پیشرفت)
        logger.info(f"در حال دانلود از: {GITHUB_REPO_URL}")
        
        def download_chunked():
            req = urllib.request.Request(GITHUB_REPO_URL, headers={"User-Agent": "AutomationPlatform"})
            with urllib.request.urlopen(req) as response, open(temp_zip, 'wb') as out_file:
                total_size = response.headers.get('content-length')
                total_size = int(total_size) if total_size else 2000000 # Estimate 2MB if unknown
                
                downloaded = 0
                chunk_size = 8192
                start_time = time.time()
                
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback:
                        percent = min(int((downloaded / total_size) * 100), 100)
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        speed_mb = speed / (1024 * 1024)
                        
                        # Call sync or async callback
                        cb_result = progress_callback(percent, f"{speed_mb:.2f} MB/s", downloaded, total_size)
                        if asyncio.iscoroutine(cb_result):
                            # We can't await here directly in thread, but we can schedule it
                            # Usually we'll just fire and forget or use an event loop
                            pass

        await asyncio.to_thread(download_chunked)
        
        if progress_callback:
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(100, "0 MB/s", 1, 1, status="extracting")
            else:
                progress_callback(100, "0 MB/s", 1, 1, status="extracting")
                
        # 3. استخراج فایل زیپ
        logger.info("در حال استخراج فایل‌ها...")
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            
        # 4. پیدا کردن پوشه سورس داخل فایل استخراج شده
        source_folder = None
        for item in extract_dir.iterdir():
            if item.is_dir() and "automation-browsing" in item.name.lower():
                source_folder = item
                break
                
        if not source_folder:
            raise Exception("پوشه سورس در فایل زیپ پیدا نشد.")
            
        # 5. کپی کردن فایل‌های جدید روی فایل‌های قدیمی
        logger.info("در حال جایگزینی فایل‌های سورس...")
        allowed_dirs = ["api", "browser", "core", "locators", "ui", "workflows"]
        allowed_files = ["main.py", "config.py", "requirements.txt"]
        
        for item in source_folder.iterdir():
            target_path = base_dir / item.name
            
            if item.is_dir() and item.name in allowed_dirs:
                if target_path.exists():
                    shutil.rmtree(target_path, ignore_errors=True)
                shutil.copytree(item, target_path)
            elif item.is_file() and item.name in allowed_files:
                shutil.copy2(item, target_path)

        # Update version.json
        try:
            req = urllib.request.Request(GITHUB_VERSION_URL, headers={"User-Agent": "AutomationPlatform"})
            with urllib.request.urlopen(req) as response:
                remote_version_data = json.loads(response.read().decode())
                
            with open(base_dir / "version.json", "w") as f:
                json.dump(remote_version_data, f, indent=4)
        except Exception as e:
            logger.warning(f"Could not update version.json after update: {e}")

        # 6. پاکسازی فایل‌های موقت
        logger.info("در حال پاکسازی فایل‌های موقت آپدیت...")
        temp_zip.unlink(missing_ok=True)
        shutil.rmtree(extract_dir, ignore_errors=True)
        
        logger.info("آپدیت با موفقیت انجام شد!")
        return True, "آپدیت با موفقیت انجام شد! برنامه در حال راه‌اندازی مجدد است..."
        
    except Exception as e:
        error_msg = f"خطا در هنگام آپدیت: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg
