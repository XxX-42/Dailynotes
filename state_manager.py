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
                    pass # 备份失败不应阻止主保存
            
            # 2. 写入新状态
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
        [哈希规范化] 为指纹识别标准化文本。
        1. 移除日期/时间链接
        2. 统一空白 (制表符/空格 -> 单个空格)
        3. Unicode 规范化 (NFKC)
        """
        if not text: return ""
        
        # 1. Unicode 规范化 (完全兼容)
        # 将全角字符转换为半角，分解编码变体
        text = unicodedata.normalize('NFKC', text)
        
        # 2. 激进地剥离日期模式 (链接和纯文本)
        # [[YYYY-MM-DD]], [[YYYY-MM-DD|...]], YYYY-MM-DD
        text = re.sub(r'\[\[\d{4}-\d{2}-\d{2}(?:\|.*?)?\]\]', '', text)
        text = re.sub(r'\d{4}-\d{2}-\d{2}', '', text)
        
        # 3. 剥离时间模式
        # HH:MM - HH:MM, HH:MM
        text = re.sub(r'\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}', '', text)
        text = re.sub(r'\d{1,2}:\d{2}', '', text)
        
        # 4. 剥离块 ID/元数据（通常是噪声源）
        # [修复] 更严格的 ID 正则：空格 + ^ + 6-7 个字母数字 + 结尾
        text = re.sub(r'(?<=\s)\^[a-zA-Z0-9]{6,7}\s*$', '', text)
        
        # 5. 压缩空白
        # \s 捕获 [ \t\n\r\f\v]，因此这将所有空白统一为单个空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def calc_hash(self, status, content_text):
        """
        计算稳定的内容哈希。
        输入 'content_text' 可以是 "纯文本" 或 "组合文本" (文本 + 子项)。
        """
        # Normalize the content thoroughly
        norm_content = self.normalize_text(content_text)
        
        # 组合指纹：状态 + 规范化内容
        # 状态通常严格 (x, 空格, /, -)，但为了以防万一，我们也剥离它
        norm_status = status.strip()
        
        raw_fingerprint = f"{norm_status}|{norm_content}"
        return hashlib.md5(raw_fingerprint.encode('utf-8')).hexdigest()
