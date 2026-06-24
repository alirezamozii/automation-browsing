# -*- coding: utf-8 -*-
"""
مدیریت ارتباطات WebSocket برای ارسال بروزرسانی‌های زنده به رابط کاربری

این ماژول شامل کلاس WebSocketManager برای مدیریت اتصالات WebSocket
و ارسال رویدادهای موتور اجرا به کلاینت‌های متصل است.
"""

import asyncio
import logging
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    مدیر اتصالات WebSocket

    مسئول نگهداری لیست اتصالات فعال، ارسال پیام‌های broadcast
    و مدیریت heartbeat برای تشخیص قطعی اتصال.
    """

    # انواع پیام‌های پشتیبانی شده
    MESSAGE_TYPES = {
        "state_changed",
        "log_entry",
        "step_progress",
        "error",
        "notification",
    }

    def __init__(self) -> None:
        """راه‌اندازی مدیر WebSocket"""
        self.active_connections: list[WebSocket] = []
        self._heartbeat_task: asyncio.Task | None = None
        self._running: bool = False

    async def connect(self, websocket: WebSocket) -> None:
        """
        پذیرش و افزودن یک اتصال WebSocket جدید

        Args:
            websocket: اتصال WebSocket ورودی
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"اتصال WebSocket جدید برقرار شد. تعداد اتصالات فعال: {len(self.active_connections)}"
        )

        # اتصال بدون ارسال نوتیفیکیشن مزاحم به کاربر
        pass

    def disconnect(self, websocket: WebSocket) -> None:
        """
        حذف یک اتصال WebSocket قطع شده

        Args:
            websocket: اتصال WebSocket قطع شده
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            f"اتصال WebSocket قطع شد. تعداد اتصالات فعال: {len(self.active_connections)}"
        )

    async def broadcast(self, message: dict) -> None:
        """
        ارسال پیام به تمام اتصالات فعال

        اتصالات بسته شده به صورت خودکار از لیست حذف می‌شوند.

        Args:
            message: دیکشنری پیام برای ارسال
        """
        disconnected: list[WebSocket] = []

        for connection in self.active_connections:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_json(message)
                else:
                    disconnected.append(connection)
            except Exception as e:
                logger.warning(f"خطا در ارسال پیام broadcast: {e}")
                disconnected.append(connection)

        # پاکسازی اتصالات قطع شده
        for conn in disconnected:
            self.disconnect(conn)

    async def send_personal(self, websocket: WebSocket, message: dict) -> None:
        """
        ارسال پیام به یک اتصال خاص

        Args:
            websocket: اتصال WebSocket مقصد
            message: دیکشنری پیام برای ارسال
        """
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"خطا در ارسال پیام شخصی: {e}")
            self.disconnect(websocket)

    async def broadcast_state_changed(self, state: str, **kwargs) -> None:
        """
        ارسال رویداد تغییر وضعیت به همه کلاینت‌ها

        Args:
            state: وضعیت جدید ماشین حالت
            **kwargs: داده‌های اضافی
        """
        await self.broadcast({
            "type": "state_changed",
            "data": {
                "state": state,
                "timestamp": datetime.now().isoformat(),
                **kwargs,
            },
        })

    async def broadcast_log_entry(self, log_data: dict) -> None:
        """
        ارسال رکورد لاگ جدید به همه کلاینت‌ها

        Args:
            log_data: داده‌های لاگ
        """
        await self.broadcast({
            "type": "log_entry",
            "data": {
                **log_data,
                "timestamp": datetime.now().isoformat(),
            },
        })

    async def broadcast_step_progress(
        self, step_name: str, progress: float, **kwargs
    ) -> None:
        """
        ارسال پیشرفت مرحله فعلی به همه کلاینت‌ها

        Args:
            step_name: نام مرحله
            progress: درصد پیشرفت
            **kwargs: داده‌های اضافی
        """
        await self.broadcast({
            "type": "step_progress",
            "data": {
                "step_name": step_name,
                "progress": progress,
                "timestamp": datetime.now().isoformat(),
                **kwargs,
            },
        })

    async def broadcast_json(self, message: dict) -> None:
        """
        ارسال یک پیام JSON دلخواه به تمام کلاینت‌ها (alias for broadcast)

        Args:
            message: دیکشنری پیام
        """
        await self.broadcast(message)

    async def broadcast_error(self, error_message: str, **kwargs) -> None:
        """
        ارسال پیام خطا به همه کلاینت‌ها

        Args:
            error_message: متن خطا
            **kwargs: داده‌های اضافی
        """
        await self.broadcast({
            "type": "error",
            "data": {
                "message": error_message,
                "timestamp": datetime.now().isoformat(),
                **kwargs,
            },
        })

    async def start_heartbeat(self) -> None:
        """شروع ارسال heartbeat هر ۱۰ ثانیه"""
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("حلقه heartbeat WebSocket شروع شد")

    async def stop_heartbeat(self) -> None:
        """توقف ارسال heartbeat"""
        self._running = False
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info("حلقه heartbeat WebSocket متوقف شد")

    async def _heartbeat_loop(self) -> None:
        """حلقه داخلی ارسال heartbeat"""
        while self._running:
            try:
                await asyncio.sleep(10)
                if self.active_connections:
                    await self.broadcast({
                        "type": "heartbeat",
                        "data": {
                            "timestamp": datetime.now().isoformat(),
                            "connections": len(self.active_connections),
                        },
                    })
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"خطا در حلقه heartbeat: {e}")

    async def close_all(self) -> None:
        """بستن تمام اتصالات فعال"""
        await self.stop_heartbeat()
        for connection in self.active_connections[:]:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.close()
            except Exception:
                pass
        self.active_connections.clear()
        logger.info("تمام اتصالات WebSocket بسته شدند")


async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    هندلر اصلی مسیر WebSocket

    مدیریت اتصال، دریافت پیام‌ها (ping/pong) و پاکسازی هنگام قطع.

    Args:
        websocket: اتصال WebSocket ورودی
    """
    ws_manager: WebSocketManager = websocket.app.state.ws_manager

    await ws_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()

            # مدیریت پیام‌های ورودی
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await ws_manager.send_personal(websocket, {
                    "type": "pong",
                    "data": {"timestamp": datetime.now().isoformat()},
                })
            elif msg_type == "pong":
                # پاسخ pong از کلاینت - بدون نیاز به اقدام
                pass
            else:
                logger.debug(f"پیام WebSocket ناشناخته دریافت شد: {msg_type}")

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("کلاینت WebSocket اتصال را قطع کرد")
    except Exception as e:
        ws_manager.disconnect(websocket)
        logger.error(f"خطا در هندلر WebSocket: {e}")
