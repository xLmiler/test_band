#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理
"""

import os
import sys
import glob
import random
import threading
import shutil
import platform
import subprocess
from typing import List, Dict, Optional

class BrowserPathFinder:
    """跨平台浏览器路径查找器"""
    
    # 浏览器可执行文件名（按优先级排序）
    BROWSER_EXECUTABLES = {
        'windows': [
            'chrome.exe',
            'msedge.exe',
            'chromium.exe',
            'brave.exe',
            'vivaldi.exe',
            'opera.exe',
        ],
        'darwin': [  # macOS
            'Google Chrome',
            'Chromium',
            'Microsoft Edge',
            'Brave Browser',
            'Vivaldi',
            'Opera',
        ],
        'linux': [
            'google-chrome',
            'google-chrome-stable',
            'google-chrome-beta',
            'google-chrome-dev',
            'google-chrome-unstable',
            'chromium',
            'chromium-browser',
            'microsoft-edge',
            'microsoft-edge-stable',
            'microsoft-edge-beta',
            'microsoft-edge-dev',
            'brave-browser',
            'brave-browser-stable',
            'brave',
            'vivaldi',
            'vivaldi-stable',
            'opera',
            'opera-stable',
            'chrome',  # 通用名称
        ],
    }
    
    # 各平台常见安装路径
    COMMON_PATHS = {
        'windows': [
            # Chrome
            os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application'),
            os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application'),
            # Edge
            os.path.expandvars(r'%ProgramFiles%\Microsoft\Edge\Application'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft\Edge\Application'),
            os.path.expandvars(r'%LocalAppData%\Microsoft\Edge\Application'),
            # Brave
            os.path.expandvars(r'%ProgramFiles%\BraveSoftware\Brave-Browser\Application'),
            os.path.expandvars(r'%LocalAppData%\BraveSoftware\Brave-Browser\Application'),
            # Chromium
            os.path.expandvars(r'%LocalAppData%\Chromium\Application'),
            # Vivaldi
            os.path.expandvars(r'%LocalAppData%\Vivaldi\Application'),
            # Opera
            os.path.expandvars(r'%LocalAppData%\Programs\Opera'),
            # Playwright
            os.path.expandvars(r'%LocalAppData%\ms-playwright'),
            os.path.expandvars(r'%UserProfile%\.cache\ms-playwright'),
            # Puppeteer
            os.path.expandvars(r'%LocalAppData%\puppeteer'),
            os.path.expandvars(r'%UserProfile%\.cache\puppeteer'),
        ],
        'darwin': [  # macOS
            # 标准应用目录
            '/Applications',
            os.path.expanduser('~/Applications'),
            # Chrome
            '/Applications/Google Chrome.app/Contents/MacOS',
            os.path.expanduser('~/Applications/Google Chrome.app/Contents/MacOS'),
            # Chromium
            '/Applications/Chromium.app/Contents/MacOS',
            os.path.expanduser('~/Applications/Chromium.app/Contents/MacOS'),
            # Edge
            '/Applications/Microsoft Edge.app/Contents/MacOS',
            os.path.expanduser('~/Applications/Microsoft Edge.app/Contents/MacOS'),
            # Brave
            '/Applications/Brave Browser.app/Contents/MacOS',
            os.path.expanduser('~/Applications/Brave Browser.app/Contents/MacOS'),
            # Vivaldi
            '/Applications/Vivaldi.app/Contents/MacOS',
            # Opera
            '/Applications/Opera.app/Contents/MacOS',
            # Homebrew
            '/opt/homebrew/bin',
            '/usr/local/bin',
            '/opt/homebrew/Caskroom/google-chrome/latest/Google Chrome.app/Contents/MacOS',
            # Playwright
            os.path.expanduser('~/.cache/ms-playwright'),
            os.path.expanduser('~/Library/Caches/ms-playwright'),
            # Puppeteer
            os.path.expanduser('~/.cache/puppeteer'),
        ],
        'linux': [
            # 标准路径
            '/usr/bin',
            '/usr/local/bin',
            '/bin',
            '/sbin',
            # Chrome
            '/opt/google/chrome',
            '/opt/google/chrome-stable',
            '/opt/google/chrome-beta',
            '/opt/google/chrome-unstable',
            # Chromium
            '/opt/chromium',
            '/opt/chromium-browser',
            '/usr/lib/chromium',
            '/usr/lib/chromium-browser',
            '/usr/lib64/chromium-browser',
            # Edge
            '/opt/microsoft/msedge',
            '/opt/microsoft/msedge-stable',
            '/opt/microsoft/msedge-beta',
            '/opt/microsoft/msedge-dev',
            # Brave
            '/opt/brave.com/brave',
            '/opt/brave.com/brave-browser',
            '/usr/lib/brave-browser',
            # Snap 安装路径
            '/snap/bin',
            '/snap/chromium/current/usr/lib/chromium-browser',
            '/snap/chromium/current/usr/lib/chromium',
            '/var/lib/snapd/snap/bin',
            # Flatpak 路径
            '/var/lib/flatpak/exports/bin',
            os.path.expanduser('~/.local/share/flatpak/exports/bin'),
            # AppImage 路径
            os.path.expanduser('~/Applications'),
            os.path.expanduser('~/.local/bin'),
            # Playwright
            os.path.expanduser('~/.cache/ms-playwright'),
            '/root/.cache/ms-playwright',
            '/home/*/.cache/ms-playwright',
            # Puppeteer
            os.path.expanduser('~/.cache/puppeteer'),
            '/root/.cache/puppeteer',
            '/home/*/.cache/puppeteer',
            # Docker 常见路径
            '/headless-shell',
            '/chrome',
            '/chromium',
            '/browser',
            '/app/chrome',
            '/app/chromium',
            '/usr/share/chromium',
            # NixOS
            '/run/current-system/sw/bin',
            os.path.expanduser('~/.nix-profile/bin'),
        ],
    }
    
    # Playwright/Puppeteer 浏览器的 glob 模式
    GLOB_PATTERNS = [
        # Playwright Chromium
        os.path.expanduser('~/.cache/ms-playwright/chromium-*/chrome-linux/chrome'),
        os.path.expanduser('~/.cache/ms-playwright/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium'),
        os.path.expanduser('~/.cache/ms-playwright/chromium-*/chrome-win/chrome.exe'),
        '/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome',
        '/home/*/.cache/ms-playwright/chromium-*/chrome-linux/chrome',
        # Playwright Chrome
        os.path.expanduser('~/.cache/ms-playwright/chrome-*/chrome-linux/chrome'),
        os.path.expanduser('~/.cache/ms-playwright/chrome-*/chrome-mac/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'),
        '/root/.cache/ms-playwright/chrome-*/chrome-linux/chrome',
        # Puppeteer
        os.path.expanduser('~/.cache/puppeteer/chrome/*/chrome-linux64/chrome'),
        os.path.expanduser('~/.cache/puppeteer/chrome/*/chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'),
        os.path.expanduser('~/.cache/puppeteer/chrome/*/chrome-win64/chrome.exe'),
        '/root/.cache/puppeteer/chrome/*/chrome-linux64/chrome',
        '/home/*/.cache/puppeteer/chrome/*/chrome-linux64/chrome',
        # Windows Playwright
        os.path.expandvars(r'%LocalAppData%\ms-playwright\chromium-*\chrome-win\chrome.exe'),
        os.path.expandvars(r'%UserProfile%\.cache\ms-playwright\chromium-*\chrome-win\chrome.exe'),
    ]
    
    @classmethod
    def get_platform(cls) -> str:
        """获取当前平台"""
        system = platform.system().lower()
        if system == 'windows':
            return 'windows'
        elif system == 'darwin':
            return 'darwin'
        else:
            return 'linux'  # Linux 和其他 Unix-like 系统
    
    @classmethod
    def find_browser(cls) -> Optional[str]:
        """
        查找可用的浏览器路径
        返回找到的第一个可执行浏览器路径，未找到返回None
        """
        current_platform = cls.get_platform()
        
        # 1. 首先检查环境变量
        for env_var in ['BROWSER_PATH', 'CHROME_PATH', 'CHROMIUM_PATH', 'CHROME_EXECUTABLE_PATH']:
            env_path = os.getenv(env_var)
            if env_path and cls._is_valid_executable(env_path):
                return env_path
        
        # 2. 使用 which/where 命令查找
        executables = cls.BROWSER_EXECUTABLES.get(current_platform, cls.BROWSER_EXECUTABLES['linux'])
        for name in executables:
            path = shutil.which(name)
            if path and cls._is_valid_executable(path):
                return path
        
        # 3. 检查 glob 模式（Playwright/Puppeteer）
        for pattern in cls.GLOB_PATTERNS:
            matches = glob.glob(pattern)
            for match in sorted(matches, reverse=True):  # 优先使用最新版本
                if cls._is_valid_executable(match):
                    return match
        
        # 4. 遍历常见路径
        common_paths = cls.COMMON_PATHS.get(current_platform, cls.COMMON_PATHS['linux'])
        for base_path in common_paths:
            # 处理包含通配符的路径
            if '*' in base_path:
                expanded_paths = glob.glob(base_path)
            else:
                expanded_paths = [base_path]
            
            for expanded_path in expanded_paths:
                if not os.path.isdir(expanded_path):
                    continue
                
                for name in executables:
                    full_path = os.path.join(expanded_path, name)
                    if cls._is_valid_executable(full_path):
                        return full_path
        
        # 5. macOS 特殊处理：检查 .app 包
        if current_platform == 'darwin':
            found = cls._find_macos_app()
            if found:
                return found
        
        # 6. 递归搜索特定目录
        search_roots = {
            'windows': [
                os.path.expandvars(r'%ProgramFiles%'),
                os.path.expandvars(r'%LocalAppData%'),
            ],
            'darwin': [
                '/Applications',
                os.path.expanduser('~/Applications'),
            ],
            'linux': [
                '/opt',
                '/usr/lib',
                '/snap',
                os.path.expanduser('~/.cache'),
            ],
        }
        
        for search_root in search_roots.get(current_platform, []):
            if os.path.isdir(search_root):
                found = cls._recursive_search(search_root, executables, max_depth=4)
                if found:
                    return found
        
        # 7. Linux: 使用 find 命令（最后手段）
        if current_platform == 'linux':
            found = cls._find_with_command(executables)
            if found:
                return found
        
        return None
    
    @classmethod
    def _is_valid_executable(cls, path: str) -> bool:
        """检查路径是否是有效的可执行文件"""
        if not path:
            return False
        
        # 处理 Windows 路径
        path = os.path.normpath(path)
        
        if not os.path.isfile(path):
            return False
        
        # Windows 不需要检查执行权限
        if cls.get_platform() == 'windows':
            return path.lower().endswith('.exe')
        
        return os.access(path, os.X_OK)
    
    @classmethod
    def _find_macos_app(cls) -> Optional[str]:
        """macOS 特殊处理：查找 .app 包"""
        app_dirs = ['/Applications', os.path.expanduser('~/Applications')]
        app_names = [
            ('Google Chrome.app', 'Contents/MacOS/Google Chrome'),
            ('Chromium.app', 'Contents/MacOS/Chromium'),
            ('Microsoft Edge.app', 'Contents/MacOS/Microsoft Edge'),
            ('Brave Browser.app', 'Contents/MacOS/Brave Browser'),
            ('Vivaldi.app', 'Contents/MacOS/Vivaldi'),
            ('Opera.app', 'Contents/MacOS/Opera'),
        ]
        
        for app_dir in app_dirs:
            for app_name, executable_path in app_names:
                full_path = os.path.join(app_dir, app_name, executable_path)
                if cls._is_valid_executable(full_path):
                    return full_path
        
        return None
    
    @classmethod
    def _recursive_search(cls, root: str, executables: List[str], max_depth: int = 3, current_depth: int = 0) -> Optional[str]:
        """递归搜索目录"""
        if current_depth >= max_depth:
            return None
        
        # 跳过的目录
        skip_dirs = {'.git', 'node_modules', '__pycache__', 'cache', 'tmp', 'temp', 
                     'logs', 'log', '.npm', '.yarn', 'site-packages', 'dist-packages'}
        
        try:
            for entry in os.scandir(root):
                try:
                    if entry.is_file(follow_symlinks=True):
                        if entry.name in executables or entry.name.lower() in [e.lower() for e in executables]:
                            if cls._is_valid_executable(entry.path):
                                return entry.path
                    elif entry.is_dir(follow_symlinks=False):
                        if entry.name.lower() in skip_dirs:
                            continue
                        found = cls._recursive_search(entry.path, executables, max_depth, current_depth + 1)
                        if found:
                            return found
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        
        return None
    
    @classmethod
    def _find_with_command(cls, executables: List[str]) -> Optional[str]:
        """使用系统命令查找浏览器（Linux）"""
        for name in executables[:5]:  # 只检查前几个常见的
            try:
                result = subprocess.run(
                    ['find', '/', '-maxdepth', '6', '-name', name, '-type', 'f', '-executable', '-print', '-quit'],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    stderr=subprocess.DEVNULL
                )
                if result.returncode == 0 and result.stdout.strip():
                    path = result.stdout.strip().split('\n')[0]
                    if cls._is_valid_executable(path):
                        return path
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
                continue
        
        return None
    
    @classmethod
    def get_browser_info(cls) -> Dict:
        """获取浏览器信息"""
        path = cls.find_browser()
        info = {
            'found': path is not None,
            'path': path,
            'version': None,
            'platform': cls.get_platform()
        }
        
        return info
    
    @classmethod
    def find_all_browsers(cls) -> List[Dict]:
        """查找所有可用的浏览器"""
        browsers = []
        seen_paths = set()
        current_platform = cls.get_platform()
        executables = cls.BROWSER_EXECUTABLES.get(current_platform, cls.BROWSER_EXECUTABLES['linux'])
        
        # 查找所有可能的浏览器
        for name in executables:
            path = shutil.which(name)
            if path and path not in seen_paths and cls._is_valid_executable(path):
                seen_paths.add(path)
                browsers.append({'name': name, 'path': path})
        
        # 检查 glob 模式
        for pattern in cls.GLOB_PATTERNS:
            matches = glob.glob(pattern)
            for match in matches:
                if match not in seen_paths and cls._is_valid_executable(match):
                    seen_paths.add(match)
                    browsers.append({'name': os.path.basename(match), 'path': match})
        
        return browsers
class Config:
    """配置管理器"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._browser_path = None
        self._user_agent = None
        self._max_workers = 1
        self._headless = True
        self._email_configs = []
        self._browser_fingerprint = {}        
        self._load_from_env()
        self._detect_browser()
    
    def _detect_browser(self):
        """检测浏览器路径"""
        import os
        
        # 优先使用环境变量
        env_path = os.getenv('BROWSER_PATH') or os.getenv('CHROME_PATH')
        if env_path and os.path.isfile(env_path):
            self._browser_path = env_path
            print(f"[Config] 使用环境变量指定的浏览器: {env_path}")
            return
        
        # 自动检测
        print(f"[Config] 正在自动检测浏览器路径 (平台: {BrowserPathFinder.get_platform()})...")
        browser_info = BrowserPathFinder.get_browser_info()
        
        if browser_info['found']:
            self._browser_path = browser_info['path']
            print(f"[Config] ✓ 检测到浏览器: {browser_info['path']}")
            if browser_info['version']:
                print(f"[Config] ✓ 浏览器版本: {browser_info['version']}")
        else:
            print("[Config] ✗ 警告: 未检测到可用的浏览器！")
            print("[Config] 请确保已安装 Chrome/Chromium/Edge 或设置 BROWSER_PATH 环境变量")
            print("[Config] 支持的浏览器: Chrome, Chromium, Edge, Brave, Vivaldi, Opera")
            
            # 列出所有检查过的路径（调试用）
            all_browsers = BrowserPathFinder.find_all_browsers()
            if all_browsers:
                print(f"[Config] 找到以下浏览器但可能不兼容:")
                for b in all_browsers:
                    print(f"[Config]   - {b['name']}: {b['path']}")
    
    def get_browser_path(self) -> Optional[str]:
        """获取浏览器路径"""
        with self._lock:
            return self._browser_path
    
    def set_browser_path(self, path: str):
        """设置浏览器路径"""
        with self._lock:
            if os.path.isfile(path):
                self._browser_path = path
            else:
                raise ValueError(f"无效的浏览器路径: {path}")
    
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
            'platform': os.getenv('PLATFORM', 'Win64'),
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
