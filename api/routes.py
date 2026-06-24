# -*- coding: utf-8 -*-
"""
مسیرهای REST API برای پلتفرم اتوماسیون

این ماژول شامل تمام مسیرهای API برای مدیریت فرآیندها،
لاگ‌ها، تنظیمات و ابزارهای توسعه‌دهنده است.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from api.schemas import (
    ApiResponse,
    DeveloperState,
    LogEntry,
    LogsResponse,
    SettingsUpdate,
    WorkflowInfo,
    WorkflowStartRequest,
    WorkflowStatus,
    SessionEntry,
    SessionsResponse,
)
from storage import (
    get_logs,
    get_log_count,
    get_log_by_id,
    clear_logs,
    get_all_settings,
    update_settings,
    get_sessions,
    get_session_count,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


# ─── وضعیت موتور اجرا ───────────────────────────────────────────────

@router.get("/status", response_model=WorkflowStatus)
async def get_status(request: Request) -> WorkflowStatus:
    """دریافت وضعیت فعلی موتور اجرا"""
    try:
        engine = request.app.state.engine
        status = engine.get_status()
        
        # محاسبه درصد پیشرفت بر اساس گام فعلی و کل گام‌ها
        progress = 0.0
        if status.get("is_running") and status.get("workflow_name"):
            registry = request.app.state.registry
            try:
                wf = registry.get(status["workflow_name"])
                total_steps = len(wf.steps)
                current_idx = status.get("current_step_index", 0)
                if total_steps > 0:
                    progress = (current_idx / total_steps) * 100.0
            except Exception:
                pass
                
        status["progress"] = progress
        
        return WorkflowStatus(
            state=status["state"],
            workflow_name=status["workflow_name"],
            current_step=status.get("current_step"), # حالا اطلاعات واقعی انجین فرستاده می‌شود
            is_running=status["is_running"],
            progress=status["progress"],
            error=status.get("error"),               # حالا خطای واقعی انجین فرستاده می‌شود
        )
    except Exception as e:
        logger.error(f"خطا در دریافت وضعیت: {e}")
        raise HTTPException(status_code=500, detail=f"خطا در دریافت وضعیت: {str(e)}")


# ─── فرآیندها ──────────────────────────────────────────────────────

@router.get("/workflows", response_model=list[WorkflowInfo])
async def get_workflows_route(request: Request) -> list[WorkflowInfo]:
    """دریافت لیست فرآیندهای ثبت‌شده"""
    try:
        registry = request.app.state.registry
        workflows = registry.list_all()
        return [
            WorkflowInfo(
                name=wf.get("name", ""),
                description=wf.get("description", ""),
                steps_count=wf.get("steps_count", 0),
            )
            for wf in workflows
        ]
    except Exception as e:
        logger.error(f"خطا در دریافت لیست فرآیندها: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در دریافت لیست فرآیندها: {str(e)}"
        )


@router.post("/workflows/{name}/archive", response_model=ApiResponse)
async def archive_workflow_route(request: Request, name: str) -> ApiResponse:
    """بایگانی کردن یک اسکریپت گردش کار"""
    try:
        import shutil
        import sys
        from pathlib import Path
        
        registry = request.app.state.registry
        try:
            workflow = registry.get(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"ورک‌فلو '{name}' یافت نشد")
        
        if not hasattr(workflow, "file_path") or not workflow.file_path:
            raise HTTPException(status_code=400, detail="فقط اسکریپت‌های آپلود شده قابل بایگانی هستند")
            
        if getattr(sys, 'frozen', False):
            workflows_dir = Path(sys._MEIPASS) / "workflows"
        else:
            workflows_dir = Path(__file__).resolve().parent.parent / "workflows"
            
        archive_dir = workflows_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        dest_path = archive_dir / workflow.file_path.name
        shutil.move(str(workflow.file_path), str(dest_path))
        
        if name in registry._workflows:
            del registry._workflows[name]
            
        return ApiResponse(
            success=True,
            message=f"اسکریپت '{workflow.file_path.name}' با موفقیت بایگانی شد"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"خطا در بایگانی فرآیند: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در بایگانی فرآیند: {str(e)}"
        )


@router.post("/workflow/start", response_model=ApiResponse)
async def start_workflow_route(request: Request, body: WorkflowStartRequest) -> ApiResponse:
    """شروع اجرای یک فرآیند"""
    try:
        engine = request.app.state.engine
        registry = request.app.state.registry
        
        try:
            workflow = registry.get(body.name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"ورک‌فلو '{body.name}' یافت نشد")
            
        await engine.start(workflow, body.data)
        return ApiResponse(
            success=True,
            message=f"فرآیند '{body.name}' با موفقیت شروع شد",
            data={"workflow_name": body.name},
        )
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"خطای اعتبارسنجی در شروع فرآیند: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"خطا در شروع فرآیند: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در شروع فرآیند: {str(e)}"
        )


@router.post("/workflow/pause", response_model=ApiResponse)
async def pause_workflow_route(request: Request) -> ApiResponse:
    """متوقف کردن موقت فرآیند در حال اجرا"""
    try:
        engine = request.app.state.engine
        await engine.pause()
        return ApiResponse(success=True, message="فرآیند با موفقیت متوقف شد")
    except Exception as e:
        logger.error(f"خطا در توقف فرآیند: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در توقف فرآیند: {str(e)}"
        )


@router.post("/workflow/resume", response_model=ApiResponse)
async def resume_workflow_route(request: Request) -> ApiResponse:
    """ادامه اجرای فرآیند متوقف شده"""
    try:
        engine = request.app.state.engine
        await engine.resume()
        return ApiResponse(success=True, message="فرآیند با موفقیت از سر گرفته شد")
    except Exception as e:
        logger.error(f"خطا در ادامه فرآیند: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در ادامه فرآیند: {str(e)}"
        )


@router.post("/workflow/stop", response_model=ApiResponse)
async def stop_workflow_route(request: Request) -> ApiResponse:
    """توقف کامل فرآیند در حال اجرا"""
    try:
        engine = request.app.state.engine
        await engine.stop()
        return ApiResponse(success=True, message="فرآیند با موفقیت متوقف شد")
    except Exception as e:
        logger.error(f"خطا در توقف فرآیند: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در توقف فرآیند: {str(e)}"
        )


# ─── لاگ‌ها ──────────────────────────────────────────────────────────

@router.get("/logs", response_model=LogsResponse)
async def get_logs_route(
    request: Request,
    workflow: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> LogsResponse:
    """
    دریافت لیست لاگ‌ها با امکان فیلتر و صفحه‌بندی
    """
    try:
        result_logs = await get_logs(
            workflow=workflow,
            status=status,
            limit=limit,
            offset=offset,
        )
        total = await get_log_count(workflow=workflow, status=status)
        
        logs = [
            LogEntry(
                id=log["id"],
                workflow_name=log["workflow_name"],
                state=log["state"],
                step_name=log["step_name"],
                status=log["status"],
                message=log["message"],
                screenshot_path=log.get("screenshot_path"),
                created_at=log["created_at"],
            )
            for log in result_logs
        ]
        
        return LogsResponse(logs=logs, total=total)
    except Exception as e:
        logger.error(f"خطا در دریافت لاگ‌ها: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در دریافت لاگ‌ها: {str(e)}"
        )


@router.get("/logs/{log_id}/screenshot")
async def get_screenshot_route(request: Request, log_id: int) -> FileResponse:
    """
    دریافت تصویر اسکرین‌شات مرتبط با یک لاگ
    """
    try:
        log_entry = await get_log_by_id(log_id)

        if not log_entry:
            raise HTTPException(status_code=404, detail="لاگ یافت نشد")

        screenshot_path = log_entry.get("screenshot_path")
        if not screenshot_path:
            raise HTTPException(
                status_code=404, detail="اسکرین‌شاتی برای این لاگ وجود ندارد"
            )

        file_path = Path(screenshot_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=404, detail="فایل اسکرین‌شات یافت نشد"
            )

        return FileResponse(
            path=str(file_path),
            media_type="image/png",
            filename=f"screenshot_{log_id}.png",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"خطا در دریافت اسکرین‌شات: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در دریافت اسکرین‌شات: {str(e)}"
        )


@router.delete("/logs", response_model=ApiResponse)
async def clear_logs_route(request: Request) -> ApiResponse:
    """پاک کردن تمام لاگ‌ها"""
    try:
        await clear_logs()
        return ApiResponse(success=True, message="تمام لاگ‌ها با موفقیت پاک شدند")
    except Exception as e:
        logger.error(f"خطا در پاک کردن لاگ‌ها: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در پاک کردن لاگ‌ها: {str(e)}"
        )


# ─── تنظیمات ─────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings_route(request: Request) -> dict:
    """دریافت تمام تنظیمات فعلی"""
    try:
        settings = await get_all_settings()
        return settings
    except Exception as e:
        logger.error(f"خطا در دریافت تنظیمات: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در دریافت تنظیمات: {str(e)}"
        )


@router.put("/settings", response_model=ApiResponse)
async def update_settings_route(request: Request, body: SettingsUpdate) -> ApiResponse:
    """بروزرسانی تنظیمات"""
    try:
        await update_settings(body.settings)
        return ApiResponse(
            success=True,
            message="تنظیمات با موفقیت بروزرسانی شدند",
            data=body.settings,
        )
    except Exception as e:
        logger.error(f"خطا در بروزرسانی تنظیمات: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در بروزرسانی تنظیمات: {str(e)}"
        )


# ─── ابزار توسعه‌دهنده ───────────────────────────────────────────────

@router.get("/developer/state", response_model=DeveloperState)
async def get_developer_state_route(request: Request) -> DeveloperState:
    """دریافت وضعیت داخلی سیستم برای دیباگ"""
    try:
        engine = request.app.state.engine

        # دریافت اطلاعات ماشین حالت
        state_machine_info = {}
        if hasattr(engine, "state_machine"):
            sm = engine.state_machine
            state_machine_info = {
                "current_state": str(getattr(sm, "current_state", "UNKNOWN")),
                "previous_state": str(getattr(sm, "previous_state", "UNKNOWN")),
            }

        # دریافت انتقال‌های مجاز
        allowed = []
        if hasattr(engine, "state_machine") and hasattr(
            engine.state_machine, "get_allowed_transitions"
        ):
            allowed = [s.value for s in engine.state_machine.get_allowed_transitions()]

        # دریافت اطلاعات EventBus
        event_bus_info: dict[str, int] = {}
        if hasattr(engine, "event_bus"):
            bus = engine.event_bus
            if hasattr(bus, "_listeners"):
                event_bus_info = {
                    event: len(handlers)
                    for event, handlers in bus._listeners.items()
                }

        return DeveloperState(
            state_machine=state_machine_info,
            allowed_transitions=allowed,
            event_bus_listeners=event_bus_info,
        )
    except Exception as e:
        logger.error(f"خطا در دریافت وضعیت توسعه‌دهنده: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در دریافت وضعیت: {str(e)}"
        )


# ─── جلسات اجرا (Sessions) ──────────────────────────────────────────

@router.get("/sessions", response_model=SessionsResponse)
async def get_sessions_route(
    request: Request,
    limit: int = 50,
    offset: int = 0,
) -> SessionsResponse:
    """دریافت لیست جلسات اجرا شده به همراه اطلاعات کلی"""
    try:
        sessions_data = await get_sessions(limit=limit, offset=offset)
        total = await get_session_count()
        
        sessions = [
            SessionEntry(
                session_id=s["session_id"],
                workflow_name=s["workflow_name"],
                started_at=s["started_at"],
                ended_at=s["ended_at"],
                final_status=s["final_status"],
            )
            for s in sessions_data
        ]
        return SessionsResponse(sessions=sessions, total=total)
    except Exception as e:
        logger.error(f"خطا در دریافت لیست جلسات: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در دریافت لیست جلسات: {str(e)}"
        )


@router.get("/session/{session_id}/logs", response_model=LogsResponse)
async def get_session_logs_route(
    request: Request,
    session_id: str,
    limit: int = 200,
    offset: int = 0,
) -> LogsResponse:
    """دریافت تمام لاگ‌های مربوط به یک جلسه اجرا"""
    try:
        result_logs = await get_logs(
            session_id=session_id,
            limit=limit,
            offset=offset,
        )
        total = await get_log_count(session_id=session_id)
        
        logs = [
            LogEntry(
                id=log["id"],
                workflow_name=log["workflow_name"],
                state=log["state"],
                step_name=log["step_name"],
                status=log["status"],
                message=log["message"],
                screenshot_path=log.get("screenshot_path"),
                created_at=log["created_at"],
            )
            for log in result_logs
        ]
        
        return LogsResponse(logs=logs, total=total)
    except Exception as e:
        logger.error(f"خطا در دریافت لاگ‌های جلسه: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در دریافت لاگ‌های جلسه: {str(e)}"
        )


@router.post("/workflow/upload", response_model=ApiResponse)
async def upload_workflow_route(
    request: Request,
    file: UploadFile = File(...),
) -> ApiResponse:
    """آپلود اسکریپت گردش کار جدید و کشف خودکار آن"""
    try:
        filename = file.filename
        if not filename:
            raise HTTPException(status_code=400, detail="نام فایل نامعتبر است")
            
        ext = Path(filename).suffix.lower()
        if ext not in (".py", ".js", ".ts", ".tsx", ".java"):
            raise HTTPException(
                status_code=400,
                detail=f"فرمت فایل {ext} پشتیبانی نمی‌شود. فرمت‌های مجاز: .py, .js, .ts, .tsx, .java"
            )
            
        import sys
        if getattr(sys, 'frozen', False):
            workflows_dir = Path(sys._MEIPASS) / "workflows"
        else:
            workflows_dir = Path(__file__).resolve().parent.parent / "workflows"
            
        template_dir = workflows_dir / "workflow_template"
        template_dir.mkdir(parents=True, exist_ok=True)
        
        dest_path = template_dir / filename
        
        contents = await file.read()
        with open(dest_path, "wb") as f:
            f.write(contents)
            
        # کشف خودکار مجدد برای اضافه کردن ورک‌فلو جدید
        registry = request.app.state.registry
        registry.auto_discover()
        
        return ApiResponse(
            success=True,
            message=f"اسکریپت {filename} با موفقیت بارگذاری و ثبت شد",
            data={"filename": filename}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"خطا در آپلود اسکریپت: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در آپلود اسکریپت: {str(e)}"
        )


# ─── سیستم ──────────────────────────────────────────────────────────

@router.get("/system/check-update")
async def check_update_route(request: Request) -> dict:
    """بررسی وجود آپدیت جدید در گیت‌هاب"""
    try:
        from core.updater import check_for_updates
        result = await check_for_updates()
        return result
    except Exception as e:
        logger.error(f"خطا در بررسی آپدیت: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/system/update", response_model=ApiResponse)
async def update_system_route(request: Request) -> ApiResponse:
    """آپدیت سورس کدها از گیت‌هاب"""
    try:
        from core.updater import update_from_github
        import asyncio
        import os
        import sys

        ws_manager = request.app.state.ws_manager

        async def progress_callback(percent: int, status_msg: str) -> None:
            await ws_manager.broadcast_json({
                "type": "update_progress",
                "percent": percent,
                "status": status_msg,
            })

        success, message = await update_from_github(progress_callback=progress_callback)
        
        if success:
            # Restart the application gracefully after a short delay
            async def restart_app():
                await asyncio.sleep(2.0)
                os.execv(sys.executable, [sys.executable, *sys.argv])
                
            asyncio.create_task(restart_app())
            return ApiResponse(success=True, message=message)
        else:
            raise HTTPException(status_code=500, detail=message)
    except Exception as e:
        logger.error(f"خطا در بروزرسانی سیستم: {e}")
        raise HTTPException(
            status_code=500, detail=f"خطا در بروزرسانی سیستم: {str(e)}"
        )
