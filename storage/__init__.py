# -*- coding: utf-8 -*-
"""
بسته مدیریت ذخیره‌سازی و دیتابیس.

این بسته شامل ماژول‌های مدیریت دیتابیس SQLite، مدل‌های داده
و سیستم مهاجرت (migration) برای پلتفرم اتوماسیون است.
"""

from storage.database import DatabaseManager, db_manager
from storage.models import (
    clear_logs,
    clear_state,
    get_all_settings,
    get_execution_stats,
    get_log_count,
    get_logs,
    get_log_by_id,
    get_setting,
    get_sessions,
    get_session_count,
    load_state,
    save_log,
    save_setting,
    save_state,
    update_settings,
)
from storage.migrations import MigrationManager, migration_manager

__all__: list[str] = [
    # database
    "DatabaseManager",
    "db_manager",
    # models – execution logs
    "save_log",
    "get_logs",
    "get_log_by_id",
    "get_log_count",
    "clear_logs",
    "get_sessions",
    "get_session_count",
    # models – workflow state
    "save_state",
    "load_state",
    "clear_state",
    # models – settings
    "save_setting",
    "get_setting",
    "get_all_settings",
    "update_settings",
    # models – stats
    "get_execution_stats",
    # migrations
    "MigrationManager",
    "migration_manager",
]

