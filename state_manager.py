import os
import json
import time
import hashlib
import re
import shutil
import unicodedata
from config import Config
from utils import Logger

class StateManager:
    def __init__(self):
        self.state = {}
        self.load()

    def load(self):
        backup_file = Config.STATE_FILE + ".bak"
        
        # 1. Try Main File
        if os.path.exists(Config.STATE_FILE):
            try:
                with open(Config.STATE_FILE, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
                return
            except Exception:
                Logger.error_once("state_load_main", "主状态文件损坏，尝试读取备份...")
        
        # 2. Try Backup File
        if os.path.exists(backup_file):
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
                Logger.info("[StateManager.py] 成功从备份文件恢复状态。")
                return
            except Exception:
                Logger.error_once("state_load_bak", "备份文件也损坏！")
        
        # 3. Total Failure -> Reset
        if os.path.exists(Config.STATE_FILE) or os.path.exists(backup_file):
            print("\033[91m[CRITICAL] 状态文件严重损坏，且无法恢复！已重置为空状态。\033[0m")
        
        self.state = {}

    def save(self):
        try:
            # 1. Create Backup first (Safeguard)
            if os.path.exists(Config.STATE_FILE):
                try:
                    shutil.copy2(Config.STATE_FILE, Config.STATE_FILE + ".bak")
                except OSError:
                    pass # Backup fail should not stop main save
            
            # 2. Write new state
            with open(Config.STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            Logger.error_once("state_save", f"状态保存失败: {e}")

    def get_task_hash(self, bid):
        return self.state.get(bid, {}).get('hash')

    def update_task(self, bid, content_hash, source_path):
        self.state[bid] = {
            'hash': content_hash,
            'source_path': source_path,
            'last_seen': time.time()
        }

    def remove_task(self, bid):
        if bid in self.state: del self.state[bid]

    def normalize_text(self, text):
        """
        [HASH NORM] Standardize text for fingerprinting.
        1. Remove dates/time links
        2. Unify whitespace (Tab/Space -> Single Space)
        3. Unicode Normalization (NFKC)
        """
        if not text: return ""
        
        # 1. Unicode Normalization (Full Compatibility)
        # Converts full-width chars to half-width, decomposes encoding variations
        text = unicodedata.normalize('NFKC', text)
        
        # 2. Aggressively Strip Date Patterns (Links & Plain)
        # [[YYYY-MM-DD]], [[YYYY-MM-DD|...]], YYYY-MM-DD
        text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}(?:\|.*?)?\]\]', '', text)
        text = re.sub(r'\d{4}-\d{2}-\d{2}', '', text)
        
        # 3. Strip Time Patterns
        # HH:MM - HH:MM, HH:MM
        text = re.sub(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', '', text)
        text = re.sub(r'\d{1,2}:\d{2}', '', text)
        
        # 4. Strip Block IDs/Metadata (often sources of noise)
        # [FIX] Stricter ID Regex: Space + ^ + 6-7 alphanum + End
        text = re.sub(r'(?<=\s)\^[a-zA-Z0-9]{6,7}\s*$', '', text)
        
        # 5. Compress Whitespace
        # \s captures [ \t\n\r\f\v], so this unifies ALL whitespace into single space
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def calc_hash(self, status, content_text):
        """
        Calculates a Stable Content Hash.
        Input 'content_text' can be "Pure Text" or "Combined Text" (Text + Children).
        """
        # Normalize the content thoroughly
        norm_content = self.normalize_text(content_text)
        
        # Combined Fingerprint: Status + Normalized Content
        # Status usually strict (x, space, /, -), but let's strip it too just in case
        norm_status = status.strip()
        
        raw_fingerprint = f"{norm_status}|{norm_content}"
        return hashlib.md5(raw_fingerprint.encode('utf-8')).hexdigest()
