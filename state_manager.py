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

        # 1. 尝试主文件
        if os.path.exists(Config.STATE_FILE):
            try:
                with open(Config.STATE_FILE, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
                return
            except Exception:
                Logger.error_once("state_load_main", "主状态文件损坏，尝试读取备份...")

        # 2. 尝试备份文件
        if os.path.exists(backup_file):
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
                Logger.info("[StateManager.py] 成功从备份文件恢复状态。")
                return
            except Exception:
                Logger.error_once("state_load_bak", "备份文件也损坏！")

        # 3. 完全失败 -> 重置
        if os.path.exists(Config.STATE_FILE) or os.path.exists(backup_file):
            Logger.info("\033[91m[CRITICAL] 状态文件严重损坏，且无法恢复！已重置为空状态。\033[0m")

        self.state = {}

    def save(self):
        try:
            # 1. 先创建备份（安全保障）
            if os.path.exists(Config.STATE_FILE):
                try:
                    shutil.copy2(Config.STATE_FILE, Config.STATE_FILE + ".bak")
                except OSError:
                    pass

                    # 2. 写入新状态
            with open(Config.STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            Logger.error_once("state_save", f"状态保存失败: {e}")

    # [v10.6 Path Fix] 核心修复：路径标准化 helper
    # 强制将路径转换为绝对路径并统一大小写/斜杠，防止跨平台或相对路径导致的查找失败
    def _norm_path(self, path):
        try:
            return os.path.normcase(os.path.abspath(path))
        except:
            return path

    def get_task_hash(self, bid):
        return self.state.get(bid, {}).get('hash')

    def find_id_by_hash(self, source_path, content_hash):
        """
        [v10.6 Rescue Helper] 路径标准化增强版
        通过“标准化的文件路径 + 内容指纹”反查 Block ID。
        """
        norm_source = self._norm_path(source_path)  # 查的时候也标准化

        for bid, data in self.state.items():
            # 对比标准化的路径，忽略斜杠差异
            if data.get('source_path') == norm_source and data.get('hash') == content_hash:
                return bid
        return None

    def get_task_date(self, bid):
        return self.state.get(bid, {}).get('date')

    # [v10.6 Modified] 更新时标准化路径
    def update_task(self, bid, content_hash, source_path, date_str=None):
        entry = {
            'hash': content_hash,
            'source_path': self._norm_path(source_path),  # 存的时候标准化
            'last_seen': time.time()
        }
        if date_str:
            entry['date'] = date_str
        elif bid in self.state and 'date' in self.state[bid]:
            entry['date'] = self.state[bid]['date']

        self.state[bid] = entry

    def remove_task(self, bid):
        if bid in self.state: del self.state[bid]

    def normalize_text(self, text):
        """
        [哈希规范化] 为指纹识别标准化文本。
        """
        if not text: return ""
        text = unicodedata.normalize('NFKC', text)
        text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}(?:\|.*?)?\]\]', '', text)
        text = re.sub(r'\d{4}-\d{2}-\d{2}', '', text)
        text = re.sub(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', '', text)
        text = re.sub(r'\d{1,2}:\d{2}', '', text)
        text = re.sub(r'(?<=\s)\^[a-zA-Z0-9]{6,7}\s*$', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def calc_hash(self, status, content_text):
        norm_content = self.normalize_text(content_text)
        norm_status = status.strip()
        raw_fingerprint = f"{norm_status}|{norm_content}"
        return hashlib.md5(raw_fingerprint.encode('utf-8')).hexdigest()