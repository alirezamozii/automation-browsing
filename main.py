# -*- coding: utf-8 -*-
"""
نقطه ورود اصلی پلتفرم اتوماسیون

این ماژول سرور FastAPI را راه‌اندازی می‌کند، وب‌سایت‌های ثابت و داینامیک را
سرو می‌کند، و دیتابیس، موتور اجرا و وب‌ساکت را به یکدیگر متصل می‌کند.
"""

import os
import sys
import logging
import asyncio
import webbrowser
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import TemplateNotFound
from fastapi.templating import Jinja2Templates

from config import API_HOST, API_PORT
from browser import BrowserController
from core import EventBus, WorkflowEngine
from workflows import WorkflowRegistry
from storage import db_manager, migration_manager, save_log
from api import router, WebSocketManager, websocket_endpoint

logger = logging.getLogger("automation_platform.main")

# ایجاد برنامه FastAPI
app = FastAPI(title="پلتفرم اتوماسیون", version="1.0.0")

# تنظیم CORS برای توسعه راحت‌تر
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# مسیرهای استاتیک و تمپلیت‌ها با پشتیبانی از دایرکتوری موقت فایل EXE (PyInstaller)
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "ui" / "static"
TEMPLATES_DIR = BASE_DIR / "ui" / "templates"

# اطمینان از وجود پوشه‌ها
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# سوار کردن فایل‌های استاتیک
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# راه‌اندازی موتور تمپلیت Jinja2
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ─── توابع مدیریت صفحات و فال‌بک‌ها ───────────────────────────────────

def get_fallback_page(title: str, description: str) -> HTMLResponse:
    """تولید یک صفحه فال‌بک زیبا در صورتی که فایل تمپلیت هنوز توسط Gemini ساخته نشده باشد."""
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="fa">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            @import url('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css');
            body {{
                font-family: Vazirmatn, Tahoma, sans-serif;
                background-color: #0f0f11;
                color: #e2e8f0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }}
            .card {{
                background-color: #1a1a2e;
                padding: 40px;
                border-radius: 16px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 500px;
                border: 1px solid #312e81;
            }}
            h1 {{
                color: #818cf8;
                margin-top: 0;
                margin-bottom: 20px;
                font-size: 26px;
            }}
            p {{
                font-size: 16px;
                line-height: 1.8;
                color: #94a3b8;
            }}
            .status-badge {{
                display: inline-block;
                padding: 6px 12px;
                background-color: #312e81;
                color: #c7d2fe;
                border-radius: 20px;
                font-size: 13px;
                margin-top: 20px;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>{title}</h1>
            <p>{description}</p>
            <p>لایه بک‌اند، دیتابیس SQLite، موتور گردش کار Playwright و سوکت به طور کامل فعال و در حال سرویس‌دهی هستند.</p>
            <div class="status-badge">بخش بک‌اند فعال است (API & Core Online)</div>
        </div>
    </body>
    </html>
    """)


@app.get("/")
async def render_dashboard(request: Request):
    """صفحه داشبورد اصلی"""
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        logger.error(f"خطای جدی در رندر داشبورد: {str(e)}", exc_info=True)
        return get_fallback_page("صفحه داشبورد", f"خطا در بارگذاری فرانت‌اند: {str(e)}")


@app.get("/workflows")
async def render_workflow(request: Request):
    """صفحه جزئیات و مدیریت ورک‌فلوها"""
    try:
        # اصلاح باگ: نام فایل اصلاح شد به workflows.html
        return templates.TemplateResponse("workflows.html", {"request": request})
    except Exception as e:
        logger.error(f"خطای جدی در رندر صفحه فرآیندها: {str(e)}", exc_info=True)
        return get_fallback_page("صفحه فرآیندها", f"خطا در بارگذاری فرانت‌اند فرآیندها: {str(e)}")


@app.get("/logs")
async def render_logs(request: Request):
    """صفحه لاگ‌های اجرا"""
    try:
        return templates.TemplateResponse("logs.html", {"request": request})
    except Exception as e:
        logger.error(f"خطای جدی در رندر لاگ‌ها: {str(e)}", exc_info=True)
        return get_fallback_page("صفحه لاگ‌ها", f"خطا در بارگذاری فرانت‌اند لاگ‌ها: {str(e)}")


@app.get("/settings")
async def render_settings(request: Request):
    """صفحه تنظیمات پلتفرم"""
    try:
        return templates.TemplateResponse("settings.html", {"request": request})
    except Exception as e:
        logger.error(f"خطای جدی در رندر تنظیمات: {str(e)}", exc_info=True)
        return get_fallback_page("صفحه تنظیمات", f"خطا در بارگذاری فرانت‌اند تنظیمات: {str(e)}")


@app.get("/developer")
async def render_developer(request: Request):
    """صفحه ابزار توسعه‌دهندگان"""
    try:
        return templates.TemplateResponse("developer.html", {"request": request})
    except Exception as e:
        logger.error(f"خطای جدی در رندر صفحه توسعه‌دهنده: {str(e)}", exc_info=True)
        return get_fallback_page("صفحه توسعه‌دهنده", f"خطا در بارگذاری فرانت‌اند توسعه‌دهنده: {str(e)}")


# ─── مسیرهای API و WebSocket ─────────────────────────────────────────

app.include_router(router)

@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    """مسیر وب‌ساکت برای ارسال لایو اطلاعات به UI"""
    await websocket_endpoint(websocket)


# ─── رویدادهای Startup و Shutdown ─────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """کارهای مورد نیاز هنگام اجرای برنامه"""
    logger.info("در حال اجرای تنظیمات شروع سرور...")
    
    # ۱. اجرای مهاجرت‌ها و آماده‌سازی دیتابیس
    await migration_manager.run_pending()
    
    # ۲. راه‌اندازی کنترلر مرورگر و موتور اجرا
    browser = BrowserController()
    event_bus = EventBus()
    engine = WorkflowEngine(browser_controller=browser, event_bus=event_bus)
    
    # ۳. راه‌اندازی رجیستری ورک‌فلوها و کشف خودکار
    registry = WorkflowRegistry()
    registry.auto_discover()
    
    # ۴. راه‌اندازی مدیریت وب‌ساکت و شروع هارت‌بیت
    ws_manager = WebSocketManager()
    await ws_manager.start_heartbeat()
    
    # ذخیره نمونه‌ها در وضعیت اپلیکیشن برای دسترسی مسیرها
    app.state.browser = browser
    app.state.engine = engine
    app.state.registry = registry
    app.state.ws_manager = ws_manager
    
    # ۵. متصل کردن رویدادهای موتور به وب‌ساکت و ذخیره‌سازی لاگ‌ها در دیتابیس
    async def global_event_listener(event_data: dict):
        event_type = event_data.get("event")
        workflow = event_data.get("workflow") or engine.get_status().get("workflow_name") or "system"
        state = engine.state_machine.current_state.value
        step = event_data.get("step_name") or "system"
        
        status = "info"
        if event_type == "error":
            status = "error"
        elif event_type in ("step_completed", "workflow_done"):
            status = "success"
        elif event_type in ("paused", "error"):
            status = "warning"
            
        message = f"رویداد: {event_type}"
        if event_type == "state_changed":
            message = f"تغییر وضعیت به {event_data.get('new_state')}"
        elif event_type == "step_started":
            message = f"شروع گام: {step}"
        elif event_type == "step_completed":
            message = f"پایان موفق گام: {step}"
        elif event_type == "error":
            message = f"خطا در اجرای گام '{step}': {event_data.get('error_message')}"
        elif event_type == "paused":
            message = "اجرای فرآیند متوقف شد"
        elif event_type == "resumed":
            message = "اجرای فرآیند از سر گرفته شد"
        elif event_type == "workflow_done":
            message = "اجرای فرآیند با موفقیت پایان یافت"

        # الف. ذخیره در دیتابیس SQLite
        try:
            log_id = await save_log(
                workflow=workflow,
                state=state,
                step=step,
                status=status,
                message=message,
                screenshot_path=event_data.get("screenshot"),
                error_traceback=event_data.get("error_traceback")
            )
        except Exception as db_err:
            logger.error(f"خطا در ذخیره لاگ رویداد: {db_err}")
            log_id = 0
            
        # ب. ارسال به وب‌ساکت
        await ws_manager.broadcast_log_entry({
            "id": log_id,
            "workflow_name": workflow,
            "state": state,
            "step_name": step,
            "status": status,
            "message": message,
            "screenshot_path": event_data.get("screenshot"),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # پ. ارسال سیگنال وضعیت به وب‌ساکت
        await ws_manager.broadcast_state_changed(
            state=state,
            workflow_name=workflow,
            step_name=step,
        )

    # اتصال شنونده برای تمام رویدادها
    for ev in ["state_changed", "step_started", "step_completed", "error", "paused", "resumed", "workflow_done"]:
        event_bus.on(ev, global_event_listener)
        
    logger.info("تمام لایه‌های سیستم به یکدیگر متصل شدند")

    # ۶. باز کردن اتوماتیک مرورگر رابط کاربری در یک ترد جداگانه
    async def open_browser():
        await asyncio.sleep(2.0)
        url = f"http://{API_HOST}:{API_PORT}"
        logger.info(f"باز کردن پنل مدیریت در مرورگر پیش‌فرض سیستم: {url}")
        webbrowser.open(url)
        
    asyncio.create_task(open_browser())


@app.on_event("shutdown")
async def shutdown_event():
    """کارهای مورد نیاز هنگام خروج از برنامه"""
    logger.info("در حال متوقف کردن فرآیندها و آزادسازی منابع...")
    
    # ۱. بستن وب‌ساکت‌ها
    if hasattr(app.state, "ws_manager"):
        await app.state.ws_manager.close_all()
        
    # ۲. بستن مرورگر
    if hasattr(app.state, "browser"):
        await app.state.browser.close()
        
    logger.info("خروج ایمن کامل شد.")


# ─── اجرای برنامه ────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=False)
