# -*- coding: utf-8 -*-
"""
پکیج API پلتفرم اتوماسیون

شامل مسیرهای REST، مدیریت WebSocket و اسکیماهای Pydantic.
"""

from api.routes import router
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
from api.websocket import WebSocketManager, websocket_endpoint

__all__ = [
    # روتر
    "router",
    # WebSocket
    "WebSocketManager",
    "websocket_endpoint",
    # اسکیماها
    "ApiResponse",
    "DeveloperState",
    "LogEntry",
    "LogsResponse",
    "SettingsUpdate",
    "WorkflowInfo",
    "WorkflowStartRequest",
    "WorkflowStatus",
]
