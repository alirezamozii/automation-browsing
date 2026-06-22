# -*- coding: utf-8 -*-
"""
مسیرهای REST API برای پلتفرم اتوماسیون

این ماژول شامل تمام مسیرهای API برای مدیریت فرآیندها،
لاگ‌ها، تنظیمات و ابزارهای توسعه‌دهنده است.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
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
)
from storage import (
    get_logs,
    get_log_count,
    get_log_by_id,
    clear_logs,
    get_all_settings,
    update_settings,
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
        status["current_step"] = None
        status["error"] = None
        
        return WorkflowStatus(
            state=status["state"],
            workflow_name=status["workflow_name"],
            current_step=status.get("current_step"),
            is_running=status["is_running"],
            progress=status["progress"],
            error=status.get("error"),
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
