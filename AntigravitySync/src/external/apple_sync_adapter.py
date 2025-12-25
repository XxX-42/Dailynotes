"""
Apple Sync Adapter for Antigravity Architecture.

This module wraps the TaskSynctoreminder logic as a downstream plugin for Dailynotes.
Apple Calendar sync only triggers when files are clean and stable.
"""
import os
import sys
import datetime

# Ensure paths are set up correctly
sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from dailynotes.utils import Logger


class AppleSyncAdapter:
    """
    Adapter that wraps Apple Calendar sync functionality.
    
    Features:
    - Lazy initialization (only loads AppleScript dependencies on first use)
    - Graceful degradation on non-macOS systems
    - Platform-safe imports
    """
    
    def __init__(self):
        self.enabled = False
        self._initialized = False
        self.sm = None
        
        # Defer initialization until first use (lazy loading)
        self._try_initialize()
    
    def _try_initialize(self):
        """
        Attempt to initialize Apple Calendar sync.
        This will gracefully fail on non-macOS systems.
        """
        if self._initialized:
            return
        
        self._initialized = True
        
        # Check if we're on macOS
        if sys.platform != 'darwin':
            Logger.info("🍏 Apple Sync: 非 macOS 系统，外部同步已禁用")
            return
        
        try:
            # Try to import the core modules
            from .task_sync_core.calendar_service import check_calendars_exist_simple
            from .task_sync_core.apple_state_manager import StateManager as AppleStateManager
            
            if check_calendars_exist_simple():
                self.enabled = True
                self.sm = AppleStateManager(Config.APPLE_SYNC_STATE_FILE)
                Logger.info("🍏 Apple Calendar Sync 模块已加载")
            else:
                Logger.error_once("apple_cal_check", "❌ 无法连接 Apple Calendar，外部同步已禁用")
        except ImportError as e:
            Logger.error_once("apple_import_fail", f"❌ Apple Sync 模块导入失败: {e}")
        except Exception as e:
            Logger.error_once("apple_init_fail", f"❌ Apple Sync 初始化失败: {e}")
    
    def sync_day(self, date_str: str):
        """
        Execute single-day sync to Apple Calendar.
        
        Note: This function is relatively slow due to AppleScript calls.
        Do not call frequently.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
        """
        if not self.enabled:
            return
        
        try:
            target_dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            daily_path = os.path.join(Config.DAILY_NOTE_DIR, f"{date_str}.md")
            
            if not os.path.exists(daily_path):
                return
            
            # Import and call the core sync logic
            from .task_sync_core.sync_engine import perform_bidirectional_sync
            
            # Call the original TaskSynctoreminder sync logic
            perform_bidirectional_sync(date_str, daily_path, self.sm, target_dt)
            
        except Exception as e:
            Logger.error_once(f"apple_sync_err_{date_str}", f"Apple Sync Error: {e}")
    
    def is_available(self) -> bool:
        """Check if Apple Sync is available and initialized."""
        return self.enabled
