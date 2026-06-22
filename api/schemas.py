# -*- coding: utf-8 -*-
"""
مدل‌های Pydantic برای اعتبارسنجی درخواست‌ها و پاسخ‌های API

این ماژول شامل تمام اسکیماهای مورد نیاز برای ارتباط بین
کلاینت و سرور است.
"""

from pydantic import BaseModel, Field


class WorkflowStartRequest(BaseModel):
    """درخواست شروع یک فرآیند اتوماسیون"""
    name: str = Field(..., description="نام فرآیند برای اجرا")
    data: dict | None = Field(default=None, description="داده‌های ورودی اختیاری")


class WorkflowInfo(BaseModel):
    """اطلاعات یک فرآیند ثبت‌شده"""
    name: str = Field(..., description="نام فرآیند")
    description: str = Field(..., description="توضیحات فرآیند")
    steps_count: int = Field(..., description="تعداد مراحل فرآیند")


class WorkflowStatus(BaseModel):
    """وضعیت فعلی موتور اجرا"""
    state: str = Field(..., description="وضعیت فعلی ماشین حالت")
    workflow_name: str | None = Field(default=None, description="نام فرآیند در حال اجرا")
    current_step: str | None = Field(default=None, description="مرحله فعلی")
    is_running: bool = Field(..., description="آیا فرآیندی در حال اجراست")
    progress: float = Field(..., description="درصد پیشرفت ۰ تا ۱۰۰")
    error: str | None = Field(default=None, description="پیام خطا در صورت وجود")


class LogEntry(BaseModel):
    """یک رکورد لاگ"""
    id: int = Field(..., description="شناسه یکتای لاگ")
    workflow_name: str = Field(..., description="نام فرآیند مرتبط")
    state: str = Field(..., description="وضعیت ماشین حالت هنگام ثبت")
    step_name: str = Field(..., description="نام مرحله")
    status: str = Field(..., description="وضعیت مرحله: success, error, running")
    message: str = Field(..., description="پیام لاگ")
    screenshot_path: str | None = Field(default=None, description="مسیر اسکرین‌شات")
    created_at: str = Field(..., description="زمان ثبت لاگ")


class LogsResponse(BaseModel):
    """پاسخ لیست لاگ‌ها با اطلاعات صفحه‌بندی"""
    logs: list[LogEntry] = Field(default_factory=list, description="لیست لاگ‌ها")
    total: int = Field(..., description="تعداد کل لاگ‌ها")


class SettingsUpdate(BaseModel):
    """درخواست بروزرسانی تنظیمات"""
    settings: dict[str, str] = Field(..., description="دیکشنری تنظیمات جدید")


class DeveloperState(BaseModel):
    """وضعیت داخلی سیستم برای ابزار توسعه‌دهنده"""
    state_machine: dict = Field(default_factory=dict, description="وضعیت ماشین حالت")
    allowed_transitions: list[str] = Field(default_factory=list, description="انتقال‌های مجاز فعلی")
    event_bus_listeners: dict[str, int] = Field(
        default_factory=dict, description="تعداد شنوندگان هر رویداد"
    )


class ApiResponse(BaseModel):
    """پاسخ استاندارد API برای عملیات‌ها"""
    success: bool = Field(..., description="آیا عملیات موفق بود")
    message: str = Field(..., description="پیام توضیحی")
    data: dict | None = Field(default=None, description="داده‌های اضافی")
