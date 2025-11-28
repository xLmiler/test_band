#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理
"""

import os
import random
import threading
from typing import List, Dict, Optional


class Config:
    """配置管理器"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._load_from_env()
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # User-Agent
        self._user_agent = os.getenv(
            'USER_AGENT',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
        )
        
        # 最大工作线程数
        self._max_workers = int(os.getenv('MAX_WORKERS', '1'))
        
        # 无头模式
        self._headless = os.getenv('HEADLESS', 'true').lower() == 'true'
        
        # 邮箱配置（支持多个，用分号分隔）
        self._email_configs = []
        
        worker_domains = os.getenv('WORKER_DOMAINS', '').split(';')
        email_domains = os.getenv('EMAIL_DOMAINS', '').split(';')
        admin_passwords = os.getenv('ADMIN_PASSWORDS', '').split(';')
        
        # 确保三个列表长度一致
        max_len = max(len(worker_domains), len(email_domains), len(admin_passwords))
        
        for i in range(max_len):
            worker = worker_domains[i].strip() if i < len(worker_domains) else ''
            email = email_domains[i].strip() if i < len(email_domains) else ''
            password = admin_passwords[i].strip() if i < len(admin_passwords) else ''
            
            if worker and email and password:
                self._email_configs.append({
                    'worker_domain': worker,
                    'email_domain': email,
                    'admin_password': password
                })
        
        # 浏览器指纹配置
        self._browser_fingerprint = {
            'window_size': os.getenv('WINDOW_SIZE', '1920x1080'),
            'timezone': os.getenv('TIMEZONE', 'Asia/Shanghai'),
            'locale': os.getenv('LOCALE', 'zh-CN'),
            'platform': os.getenv('PLATFORM', 'Win32'),
            'color_depth': int(os.getenv('COLOR_DEPTH', '24')),
            'device_memory': int(os.getenv('DEVICE_MEMORY', '8')),
            'hardware_concurrency': int(os.getenv('HARDWARE_CONCURRENCY', '8'))
        }
    
    def get_user_agent(self) -> str:
        with self._lock:
            return self._user_agent
    
    def set_user_agent(self, ua: str):
        with self._lock:
            self._user_agent = ua
    
    def get_max_workers(self) -> int:
        with self._lock:
            return self._max_workers
    
    def set_max_workers(self, count: int):
        with self._lock:
            self._max_workers = max(1, min(count, 10))
    
    def get_headless(self) -> bool:
        with self._lock:
            return self._headless
    
    def set_headless(self, headless: bool):
        with self._lock:
            self._headless = headless
    
    def get_email_configs(self) -> List[Dict]:
        with self._lock:
            return self._email_configs.copy()
    
    def get_email_configs_safe(self) -> List[Dict]:
        """获取邮箱配置（隐藏密码）"""
        with self._lock:
            return [
                {
                    'worker_domain': c['worker_domain'],
                    'email_domain': c['email_domain'],
                    'admin_password': '***'
                }
                for c in self._email_configs
            ]
    
    def get_random_email_config(self) -> Optional[Dict]:
        with self._lock:
            if self._email_configs:
                return random.choice(self._email_configs)
            return None
    
    def add_email_config(self, worker_domain: str, email_domain: str, admin_password: str):
        with self._lock:
            self._email_configs.append({
                'worker_domain': worker_domain,
                'email_domain': email_domain,
                'admin_password': admin_password
            })
    
    def update_email_config(self, index: int, worker_domain: str = None, 
                           email_domain: str = None, admin_password: str = None):
        with self._lock:
            if 0 <= index < len(self._email_configs):
                if worker_domain:
                    self._email_configs[index]['worker_domain'] = worker_domain
                if email_domain:
                    self._email_configs[index]['email_domain'] = email_domain
                if admin_password:
                    self._email_configs[index]['admin_password'] = admin_password
            else:
                raise IndexError("配置索引不存在")
    
    def delete_email_config(self, index: int):
        with self._lock:
            if 0 <= index < len(self._email_configs):
                del self._email_configs[index]
            else:
                raise IndexError("配置索引不存在")
    
    def get_browser_fingerprint(self) -> Dict:
        with self._lock:
            return self._browser_fingerprint.copy()
    
    def set_browser_fingerprint(self, fingerprint: Dict):
        with self._lock:
            self._browser_fingerprint.update(fingerprint)
