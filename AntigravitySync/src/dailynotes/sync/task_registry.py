"""
TaskRegistry - Incremental Task Cache for AntigravitySync v1.8

This module implements a persistent in-memory cache for all source tasks,
enabling O(1) file updates instead of O(n) full-disk scans.

Architecture:
    - _file_cache:  { filepath: [task_dicts...] }  # Tasks indexed by source file
    - _date_index:  { date_str: {bid: task_dict} } # Tasks indexed by date (derived view)

Key Methods:
    - initialize(project_map, sm): Full scan at startup (one-time os.walk)
    - update_file(filepath, project_name, sm): Incremental single-file rescan
    - get_tasks_by_date(date_str): Fast lookup for process_date()
    - get_affected_dates(filepath): Returns dates affected by a file change
"""

import os
import re
import datetime
import random
import string
import threading
from typing import Dict, List, Set, Optional, Any, Tuple
from config import Config
from ..utils import Logger, FileUtils
from .parsing import (
    capture_block, 
    clean_task_text, 
    normalize_block_content, 
    get_indent_depth,
    parse_file_tasks,
    generate_block_id
)


class TaskRegistry:
    """
    Thread-safe task registry implementing incremental synchronization.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._file_cache: Dict[str, List[Dict]] = {}   # { filepath: [tasks...] }
        self._date_index: Dict[str, Dict[str, Dict]] = {}  # { date: {bid: task} }
        self._file_to_dates: Dict[str, Set[str]] = {}  # { filepath: {dates...} }
        self._project_map: Dict[str, str] = {}  # Cached project map
        self._file_lock = threading.RLock()  # Reentrant lock for nested calls
        self._initialized = True
        
        Logger.info("📦 [TaskRegistry] 实例已创建")
    
    def initialize(self, project_map: Dict[str, str], sm) -> None:
        """
        Perform full scan at startup to populate the registry.
        This is the ONLY place where os.walk should be used.
        
        Args:
            project_map: { directory_path: project_name }
            sm: StateManager instance for hash calculations
        """
        with self._file_lock:
            self._project_map = project_map.copy()
            self._file_cache.clear()
            self._date_index.clear()
            self._file_to_dates.clear()
            
            today_str = datetime.date.today().strftime('%Y-%m-%d')
            file_count = 0
            task_count = 0
            
            # Single os.walk at startup
            for root, dirs, files in os.walk(Config.ROOT_DIR):
                dirs[:] = [d for d in dirs if not FileUtils.is_excluded(os.path.join(root, d))]
                if FileUtils.is_excluded(root):
                    continue
                
                # Determine project for this directory
                curr_proj = self._resolve_project(root)
                if not curr_proj:
                    continue
                
                for f in files:
                    if not f.endswith('.md'):
                        continue
                    
                    filepath = os.path.join(root, f)
                    tasks = self._scan_single_file(filepath, curr_proj, sm)
                    
                    if tasks:
                        self._file_cache[filepath] = tasks
                        self._update_date_index_from_file(filepath, tasks)
                        file_count += 1
                        task_count += len(tasks)
            
            # Ensure at least 3 recent dates exist in index
            for delta in range(3):
                target_date = datetime.date.today() - datetime.timedelta(days=delta)
                target_str = target_date.strftime('%Y-%m-%d')
                if target_str not in self._date_index:
                    self._date_index[target_str] = {}
            
            Logger.info(f"📦 [TaskRegistry] 初始化完成: {file_count} 文件, {task_count} 任务")
    
    def _resolve_project(self, directory: str) -> Optional[str]:
        """Traverse up to find the nearest ancestor project."""
        temp = directory
        while temp.startswith(Config.ROOT_DIR):
            if temp in self._project_map:
                return self._project_map[temp]
            parent = os.path.dirname(temp)
            if parent == temp:
                break
            temp = parent
        return None
    
    def _scan_single_file(self, filepath: str, project_name: str, sm) -> List[Dict]:
        """
        Parse a single markdown file and extract all source tasks.
        [v1.8.1] Now delegates to centralized parse_file_tasks for DRY.
        
        Args:
            filepath: Absolute path to the .md file
            project_name: The project this file belongs to
            sm: StateManager for hash calculations
            
        Returns:
            List of task dictionaries
        """
        lines = FileUtils.read_file(filepath)
        if not lines:
            return []
        
        # Delegate to centralized parsing function
        tasks, _, _ = parse_file_tasks(filepath, lines, project_name, sm, write_back=True)
        
        return tasks
    
    def _update_date_index_from_file(self, filepath: str, tasks: List[Dict]) -> None:
        """Update the date index with tasks from a file."""
        dates_in_file = set()
        
        for task in tasks:
            task_date = task.get('_task_date')
            if not task_date:
                continue
            
            dates_in_file.add(task_date)
            
            if task_date not in self._date_index:
                self._date_index[task_date] = {}
            
            bid = task['bid']
            # Create a copy without the internal _task_date field
            task_copy = {k: v for k, v in task.items() if not k.startswith('_')}
            self._date_index[task_date][bid] = task_copy
        
        self._file_to_dates[filepath] = dates_in_file
    
    def update_file(self, filepath: str, sm) -> Set[str]:
        """
        Incrementally update the cache for a single file.
        Called when a file change event is received.
        
        Args:
            filepath: The file that was modified
            sm: StateManager for hash calculations
            
        Returns:
            Set of date strings affected by this change
        """
        with self._file_lock:
            # Collect old affected dates before clearing
            old_dates = self._file_to_dates.get(filepath, set()).copy()
            
            # Clear old tasks from date index
            old_tasks = self._file_cache.get(filepath, [])
            for task in old_tasks:
                task_date = task.get('_task_date')
                bid = task.get('bid')
                if task_date and bid and task_date in self._date_index:
                    self._date_index[task_date].pop(bid, None)
            
            # Clear file from cache
            self._file_cache.pop(filepath, None)
            self._file_to_dates.pop(filepath, None)
            
            # Re-scan file if it still exists
            if os.path.exists(filepath):
                # Determine project
                directory = os.path.dirname(filepath)
                project_name = self._resolve_project(directory)
                
                if project_name:
                    tasks = self._scan_single_file(filepath, project_name, sm)
                    
                    if tasks:
                        self._file_cache[filepath] = tasks
                        self._update_date_index_from_file(filepath, tasks)
            
            # Get new affected dates
            new_dates = self._file_to_dates.get(filepath, set())
            
            # Return union of old and new dates
            return old_dates | new_dates
    
    def get_tasks_by_date(self, date_str: str) -> Dict[str, Dict]:
        """
        Get all tasks for a specific date.
        Fast O(1) lookup from the date index.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            Dictionary of { bid: task_dict }
        """
        with self._file_lock:
            return self._date_index.get(date_str, {}).copy()
    
    def get_affected_dates(self, filepath: str) -> Set[str]:
        """
        Get all dates that have tasks from a specific file.
        
        Args:
            filepath: Absolute path to the file
            
        Returns:
            Set of date strings
        """
        with self._file_lock:
            return self._file_to_dates.get(filepath, set()).copy()
    
    def refresh_project_map(self, project_map: Dict[str, str]) -> None:
        """
        Update the internal project map (called when projects are re-scanned).
        
        Args:
            project_map: Updated { directory_path: project_name }
        """
        with self._file_lock:
            self._project_map = project_map.copy()
    
    def get_all_tasks_by_date(self) -> Dict[str, Dict[str, Dict]]:
        """
        Get the entire date index.
        Used for compatibility with the original scan_all_source_tasks() return value.
        
        Returns:
            Dictionary of { date_str: { bid: task_dict } }
        """
        with self._file_lock:
            return {date: tasks.copy() for date, tasks in self._date_index.items()}
    
    def is_initialized(self) -> bool:
        """Check if the registry has been initialized."""
        return bool(self._file_cache) or bool(self._date_index)
    
    def clear(self) -> None:
        """Clear all cached data (for testing)."""
        with self._file_lock:
            self._file_cache.clear()
            self._date_index.clear()
            self._file_to_dates.clear()
            self._project_map.clear()


# Global singleton access
_registry: Optional[TaskRegistry] = None

def get_registry() -> TaskRegistry:
    """Get the global TaskRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = TaskRegistry()
    return _registry
