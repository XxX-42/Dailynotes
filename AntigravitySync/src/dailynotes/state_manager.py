import os
import json
import time
import hashlib
import re
import shutil
import unicodedata
from config import Config
from .utils import Logger


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

    def _norm_path(self, path):
        """核心修复：路径标准化 helper"""
        try:
            return os.path.normcase(os.path.abspath(path))
        except:
            return path

    def get_task_hash(self, bid):
        return self.state.get(bid, {}).get('hash')

    def find_id_by_hash(self, source_path, content_hash):
        """通过"标准化的文件路径 + 内容指纹"反查 Block ID。"""
        norm_source = self._norm_path(source_path)

        for bid, data in self.state.items():
            if data.get('source_path') == norm_source and data.get('hash') == content_hash:
                return bid
        return None

    def get_task_date(self, bid):
        return self.state.get(bid, {}).get('date')

    def update_task(self, bid, content_hash, source_path, date_str=None):
        entry = {
            'hash': content_hash,
            'source_path': self._norm_path(source_path),
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
        [v13.4 Final Stability] 为指纹识别标准化文本。
        策略：剥离所有可能导致双向差异的格式符号。
        """
        if not text: return ""
        text = unicodedata.normalize('NFKC', text)

        # 1. 忽略 Markdown 链接格式: [text](url) -> url (解决 FormatCore 自动转换导致的差异)
        #    注意：这里保留 url，因为 url 是核心内容
        text = re.sub(r'\[([^\]]+?)\]\(([^)]+?)\)', r'\2', text)

        # 2. [关键修复] 移除所有 [[WikiLink]] 格式
        #    日记里有 [[文件名]]，原文件里没有。为了让哈希一致，必须把它们都视为"透明"。
        #    这同时也移除了 [[日期]]，这是符合预期的，因为日期属于元数据。
        text = re.sub(r'\[\[.*?\]\]', '', text)

        # 3. 移除时间段 (Day Planner 格式)
        text = re.sub(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', '', text)
        text = re.sub(r'\d{1,2}:\d{2}', '', text)

        # 4. 移除 ID (^xxxxxx)
        text = re.sub(r'(?<=\s)\^[a-zA-Z0-9]{6,7}\s*$', '', text)

        # 5. 压缩空白
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def calc_hash(self, status, content_text):
        norm_content = self.normalize_text(content_text)
        norm_status = status.strip()
        # 只要内容对得上，状态对得上，指纹就一致，不再受 [[Tag]] 或 [Link]() 干扰
        raw_fingerprint = f"{norm_status}|{norm_content}"
        return hashlib.md5(raw_fingerprint.encode('utf-8')).hexdigest()
