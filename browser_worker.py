import re
import time
import random
import threading
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import logging

from DrissionPage import Chromium, ChromiumOptions

from email_manager import EmailManager

logger = logging.getLogger(__name__)

class AccountStatus(Enum):
    PENDING = "pending"
    CREATING_EMAIL = "creating_email"
    OPENING_PAGE = "opening_page"
    ENTERING_EMAIL = "entering_email"
    WAITING_CODE = "waiting_code"
    ENTERING_CODE = "entering_code"
    VERIFYING = "verifying"
    ENTERING_NAME = "entering_name"
    AGREEING = "agreeing"
    WAITING_REDIRECT = "waiting_redirect"
    COMPLETING = "completing"
    EXTRACTING_DATA = "extracting_data"
    SUCCESS = "success"
    FAILED = "failed"
    UPDATING = "updating"


@dataclass
class AccountInfo:
    email: str = ""
    jwt: str = ""
    status: AccountStatus = AccountStatus.PENDING
    error_message: str = ""
    verification_code: str = ""
    c_oses: str = ""
    c_ses: str = ""
    csesidx: str = ""
    config_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    email_config: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "status": self.status.value,
            "error_message": self.error_message,
            "verification_code": self.verification_code,
            "c_oses": self.c_oses,
            "c_ses": self.c_ses,
            "csesidx": self.csesidx,
            "config_id": self.config_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_complete": self.is_complete()
        }
    
    def to_export_dict(self) -> dict:
        """导出格式，包含时间戳"""
        return {
            "available": True,
            "csesidx": self.csesidx,
            "host_c_oses": self.c_oses,
            "secure_c_ses": self.c_ses,
            "team_id": self.config_id,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            "created_at": self.created_at or datetime.now().isoformat(),
            "updated_at": self.updated_at or self.created_at or datetime.now().isoformat()
        }
    
    def is_complete(self) -> bool:
        return all([
            self.c_oses,
            self.c_ses,
            self.csesidx,
            self.config_id
        ])


class BrowserWorker(threading.Thread):
    """浏览器工作线程"""
    
    def __init__(
        self,
        worker_id: int,
        account: AccountInfo,
        config,
        mode: str = "register",
        on_update: Optional[Callable] = None,
        on_complete: Optional[Callable] = None
    ):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.account = account
        self.config = config
        self.mode = mode
        self.on_update = on_update
        self.on_complete = on_complete
        self.is_running = True
        self.browser: Optional[Chromium] = None
        self.page = None
    
    def update_status(self, status: AccountStatus, error: str = ""):
        """更新状态"""
        self.account.status = status
        self.account.error_message = error
        self.account.updated_at = datetime.now().isoformat()
        if self.on_update:
            self.on_update(self.account.email, self.account)
    
    def create_browser(self) -> bool:
        """创建浏览器实例"""
        try:
            self.close_browser()
            
            options = ChromiumOptions().auto_port()
            # 设置浏览器路径
            browser_path = self.config.get_browser_path()
            if browser_path:
                options.set_browser_path(browser_path)
                logger.info(f"[{self.worker_id}] 使用浏览器: {browser_path}")

            ua = self.config.get_user_agent()
            options.set_user_agent(ua)
            
            if self.config.get_headless():
                options.set_argument('--headless=new')
            options.set_argument('--incognito')
            
            options.set_argument('--disable-blink-features=AutomationControlled')
            options.set_argument('--no-sandbox')
            options.set_argument('--disable-dev-shm-usage')
            options.set_argument('--disable-gpu')
            options.set_argument('--lang=zh-CN')
            options.set_argument('--disable-web-security')
            options.set_argument('--disable-features=VizDisplayCompositor')
            
            fingerprint = self.config.get_browser_fingerprint()
            if fingerprint:
                if fingerprint.get('window_size'):
                    w, h = fingerprint['window_size'].split('x')
                    options.set_argument(f'--window-size={w},{h}')
                
                if fingerprint.get('timezone'):
                    options.set_argument(f'--timezone={fingerprint["timezone"]}')
                
                if fingerprint.get('locale'):
                    options.set_argument(f'--lang={fingerprint["locale"]}')
            
            options.set_argument('--disable-reading-from-canvas')
            options.set_pref('credentials_enable_service', False)
            options.set_pref('profile.password_manager_enabled', False)
            
            self.browser = Chromium(options)
            self.page = self.browser.latest_tab
            
            self._inject_fingerprint_script()
            
            return True
            
        except Exception as e:
            logger.error(f"创建浏览器失败: {e}")
            return False
    
    def _inject_fingerprint_script(self):
        """注入指纹混淆脚本"""
        script = '''
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        window.chrome = { runtime: {} };
        '''
        try:
            self.page.run_js(script)
        except:
            pass
    
    def close_browser(self):
        """关闭浏览器"""
        if self.browser:
            try:
                self.browser.quit()
            except:
                pass
            finally:
                self.browser = None
                self.page = None
    
    def get_screenshot(self) -> Optional[str]:
        """获取当前页面截图 (Base64)"""
        if self.page:
            try:
                return self.page.get_screenshot(as_base64=True, full_page=False)
            except Exception as e:
                logger.error(f"截图失败: {e}")
                return None
        return None
    
    def safe_input(self, selector: str, text: str, max_retries: int = 3) -> bool:
        """安全输入文本"""
        for attempt in range(max_retries):
            try:
                ele = self.page.ele(selector, timeout=10)
                if not ele:
                    continue
                
                ele.clear()
                time.sleep(0.3)
                clean_text = ''.join(c for c in text if ord(c) < 128)
                ele.input(clean_text)
                time.sleep(0.5)
                
                input_value = ele.attr('value') or ele.value
                if input_value and clean_text in input_value:
                    return True
                else:
                    ele.clear()
                    time.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"输入失败: {e}")
                time.sleep(1)
        
        return False

    def wait_and_input(self, selector: str, text: str, timeout: float = 10, description: str = "") -> bool:
        """等待元素并输入"""
        try:
            ele = self.page.ele(selector, timeout=timeout)
            if ele:
                ele.clear()
                ele.input(text)
                logger.info(f"输入成功: {description}")
                return True
            else:
                logger.warning(f"未找到输入框: {description}")
                return False
        except Exception as e:
            logger.error(f"输入失败 {description}: {e}")
            return False

    def wait_and_click(self, selector: str, timeout: float = 10) -> bool:
        """等待并点击元素"""
        try:
            ele = self.page.ele(selector, timeout=timeout)
            if ele:
                ele.click()
                return True
            return False
        except Exception as e:
            logger.error(f"点击失败: {e}")
            return False
    
    def wait_for_url_pattern(self, pattern: str, timeout: float = 60) -> bool:
        """等待URL匹配模式"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self.is_running:
                return False
            try:
                current_url = self.page.url
                if re.search(pattern, current_url):
                    return True
            except:
                pass
            time.sleep(1)
        return False
    
    def wait_for_element(self, selector: str, timeout: float = 30) -> bool:
        """等待元素出现"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self.is_running:
                return False
            try:
                ele = self.page.ele(selector, timeout=1)
                if ele:
                    return True
            except:
                pass
            time.sleep(0.5)
        return False
    
    def extract_data(self) -> bool:
        """提取数据"""
        try:
            cookies = self.page.cookies()
            for cookie in cookies:
                name = cookie.get('name', '')
                if name == '__Host-C_OSES':
                    self.account.c_oses = cookie.get('value', '')
                elif name == '__Secure-C_SES':
                    self.account.c_ses = cookie.get('value', '')
            
            current_url = self.page.url
            parsed = urlparse(current_url)
            query_params = parse_qs(parsed.query)
            self.account.csesidx = query_params.get('csesidx', [''])[0]
            
            path_match = re.search(r'/cid/([a-f0-9-]+)', parsed.path)
            if path_match:
                self.account.config_id = path_match.group(1)
            
            # 设置更新时间
            self.account.updated_at = datetime.now().isoformat()
            
            return self.account.is_complete()
            
        except Exception as e:
            logger.error(f"提取数据失败: {e}")
            return False
    
    def handle_welcome_dialog(self) -> bool:
        """处理欢迎对话框"""
        try:
            time.sleep(2)
            
            try:
                app_ele = self.page.ele('tag:ucs-standalone-app', timeout=5)
                if app_ele:
                    sr1 = app_ele.shadow_root
                    if sr1:
                        dialog_ele = sr1.ele('tag:ucs-welcome-dialog', timeout=3)
                        if dialog_ele:
                            sr2 = dialog_ele.shadow_root
                            if sr2:
                                btn_ele = sr2.ele('tag:md-text-button', timeout=3)
                                if btn_ele:
                                    sr3 = btn_ele.shadow_root
                                    if sr3:
                                        inner_btn = sr3.ele('tag:button', timeout=3)
                                        if inner_btn:
                                            inner_btn.click()
                                            return True
            except:
                pass
            
            try:
                js_code = '''
                function clickWelcomeButton() {
                    const app = document.querySelector('ucs-standalone-app');
                    if (app && app.shadowRoot) {
                        const dialog = app.shadowRoot.querySelector('ucs-welcome-dialog');
                        if (dialog && dialog.shadowRoot) {
                            const btn = dialog.shadowRoot.querySelector('md-text-button');
                            if (btn) {
                                if (btn.shadowRoot) {
                                    const innerBtn = btn.shadowRoot.querySelector('button');
                                    if (innerBtn) { innerBtn.click(); return true; }
                                }
                                btn.click();
                                return true;
                            }
                        }
                    }
                    return false;
                }
                return clickWelcomeButton();
                '''
                result = self.page.run_js(js_code)
                return bool(result)
            except:
                pass
            
            return False
            
        except:
            return False
    
    def click_verify_button(self) -> bool:
        """点击验证按钮"""
        verify_selectors = [
            'xpath://button[@jsname="XooR8e"]',
            'xpath://button[@aria-label="验证"]',
            'xpath://button[contains(@class, "YUhpIc-LgbsSe") and @type="submit"]',
            'xpath://button[.//span[contains(text(), "验证")]]',
            'css:button[jsname="XooR8e"]',
            'css:button[aria-label="验证"]',
        ]
        
        for selector in verify_selectors:
            try:
                ele = self.page.ele(selector, timeout=3)
                if ele:
                    time.sleep(0.5)
                    ele.click()
                    logger.info(f"成功点击验证按钮: {selector}")
                    return True
            except:
                continue
        
        try:
            js_code = '''
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                if (btn.getAttribute('jsname') === 'XooR8e' || 
                    btn.getAttribute('aria-label') === '验证' ||
                    btn.innerText.includes('验证')) {
                    btn.click();
                    return true;
                }
            }
            return false;
            '''
            result = self.page.run_js(js_code)
            if result:
                logger.info("通过 JavaScript 成功点击验证按钮")
                return True
        except:
            pass
        
        return False
    
    def click_resend_button(self) -> bool:
        """点击重新发送按钮"""
        resend_selectors = [
            'button[aria-label="Resend Code"]',
            'button[aria-label="重新发送"]',
            'xpath://button[contains(., "Resend")]',
            'xpath://button[contains(., "重新发送验证码")]',
        ]
        
        for sel in resend_selectors:
            if self.wait_and_click(sel, timeout=5):
                logger.info(f"[{self.worker_id}] 已点击重新发送按钮")
                return True
        
        return False

    def get_verification_code_with_retry(self, email_manager) -> Optional[str]:
        """带重试机制的获取验证码"""
        max_loops = 1
        
        for i in range(max_loops):
            logger.info(f"[{self.worker_id}] 第 {i+1} 次尝试获取验证码流程")
            
            # 1. 第一次检测 (15次)
            logger.info(f"[{self.worker_id}] 正在检测邮件 (10次尝试)...")
            code = email_manager.check_verification_code(self.account.email, max_retries=10)
            if code:
                return code
            
            # 2. 如果没收到，检测是否有重发按钮
            logger.info(f"[{self.worker_id}] 未收到邮件，检查重发按钮...")
            if self.click_resend_button():
                logger.info(f"[{self.worker_id}] 点击了重发按钮，等待邮件发送...")
                time.sleep(10) # 等待邮件发送
                continue # 重新开始循环，会再次检测邮件
            
            # 3. 如果没有重发按钮，继续等待15次
            logger.info(f"[{self.worker_id}] 未找到重发按钮，继续等待邮件 (10次尝试)...")
            code = email_manager.check_verification_code(self.account.email, max_retries=10)
            if code:
                return code
                
            # 4. 再次检测重发按钮
            logger.info(f"[{self.worker_id}] 仍未收到邮件，再次检查重发按钮...")
            if self.click_resend_button():
                logger.info(f"[{self.worker_id}] 点击了重发按钮，等待邮件发送...")
                time.sleep(10)
                continue
            else:
                logger.warning(f"[{self.worker_id}] 无法找到重发按钮且未收到邮件，本轮失败")
                return None
                
        return None

    def register_account(self) -> bool:
        """注册账号"""
        try:
            self.update_status(AccountStatus.OPENING_PAGE)
            logger.info(f"[{self.worker_id}] 正在打开页面...")
            
            self.page.get('https://business.gemini.google')
            
            email_input_selectors = [
                'xpath://input[@id="email-input"]',
                'xpath://input[@name="loginHint"]',
                '#email-input',
            ]
            
            email_input_found = False
            for selector in email_input_selectors:
                if self.wait_for_element(selector, timeout=30):
                    email_input_found = True
                    break
            
            if not email_input_found:
                raise Exception("等待邮箱输入框超时")
            
            time.sleep(1)
            
            self.update_status(AccountStatus.ENTERING_EMAIL)
            logger.info(f"[{self.worker_id}] 正在输入邮箱: {self.account.email}")
            
            input_success = False
            for selector in email_input_selectors:
                if self.safe_input(selector, self.account.email):
                    input_success = True
                    break
            
            if not input_success:
                raise Exception("无法输入邮箱")
            
            time.sleep(1)
            
            continue_selectors = [
                'xpath://button[@id="log-in-button"]',
                'xpath://button[contains(@aria-label, "使用邮箱继续")]',
                '#log-in-button',
            ]
            
            clicked = False
            for selector in continue_selectors:
                if self.wait_and_click(selector, timeout=5):
                    clicked = True
                    break
            
            if not clicked:
                raise Exception("无法点击继续按钮")
            
            time.sleep(2)
            
            self.update_status(AccountStatus.WAITING_CODE)
            logger.info(f"[{self.worker_id}] 正在等待验证码...")
            
            email_manager = EmailManager(
                self.account.email_config.get('worker_domain', ''),
                self.account.email_config.get('email_domain', ''),
                self.account.email_config.get('admin_password', '')
            )
            
            verification_code = self.get_verification_code_with_retry(email_manager)
            
            if not verification_code:
                raise Exception("未收到验证码 (已重试)")
            
            self.account.verification_code = verification_code
            logger.info(f"[{self.worker_id}] 获取到验证码: {verification_code}")
            
            self.update_status(AccountStatus.ENTERING_CODE)
            
            code_input_selectors = [
                'xpath://input[@name="pinInput"]',
                'xpath://input[contains(@aria-label, "验证码")]',
                'input[name="pinInput"]',
            ]
            logger.info(f"[{self.worker_id}] 正在输入验证码: {self.account.email}")
            input_success = False
            for selector in code_input_selectors:
                if self.wait_and_input(selector, verification_code, timeout=10, description="验证码输入框"):
                    input_success = True
                    break
            
            if not input_success:
                raise Exception("无法输入验证码")
            
            time.sleep(1)
            
            self.update_status(AccountStatus.VERIFYING)
            
            if not self.click_verify_button():
                raise Exception("无法点击验证按钮")
            
            time.sleep(3)

            # 检查验证码错误并重试
            if self.page.ele('text:请输入验证码。', timeout=2):
                logger.warning(f"[{self.worker_id}] 验证码失效，尝试重新发送...")
                
                resend_selectors = [
                    'button[aria-label="重新发送验证码"]',
                    'xpath://button[contains(., "重新发送验证码")]'
                ]
                
                resend_clicked = False
                for sel in resend_selectors:
                    if self.wait_and_click(sel, timeout=5):
                        resend_clicked = True
                        break
                
                if resend_clicked:
                    logger.info(f"[{self.worker_id}] 已点击重新发送，等待新验证码...")
                    time.sleep(10) # 等待邮件发送
                    
                    verification_code = email_manager.check_verification_code(self.account.email)
                    if not verification_code:
                         raise Exception("重发后未收到验证码")
                    
                    self.account.verification_code = verification_code
                    logger.info(f"[{self.worker_id}] 获取到新验证码: {verification_code}")
                    
                    input_success = False
                    for selector in code_input_selectors:
                        if self.wait_and_input(selector, verification_code, timeout=10, description="验证码输入框"):
                            input_success = True
                            break
                    
                    if input_success:
                        time.sleep(1)
                        if not self.click_verify_button():
                            raise Exception("无法点击验证按钮(重试)")
                        time.sleep(3)
                    else:
                        raise Exception("无法重新输入验证码")
                else:
                    logger.warning(f"[{self.worker_id}] 未找到重新发送按钮")
            
            self.update_status(AccountStatus.ENTERING_NAME)
            
            fullname = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5))
            name_selectors = [
                'xpath://input[@formcontrolname="fullName"]',
                'xpath://input[@placeholder="全名"]',
                'input[formcontrolname="fullName"]',
            ]
            
            name_input_found = False
            for selector in name_selectors:
                if self.wait_for_element(selector, timeout=15):
                    name_input_found = True
                    break
            
            if not name_input_found:
                raise Exception("等待姓名输入框超时")
            
            input_success = False
            for selector in name_selectors:
                if self.safe_input(selector, fullname):
                    input_success = True
                    break
            
            if not input_success:
                raise Exception("无法输入姓名")
            
            time.sleep(1)
            
            self.update_status(AccountStatus.AGREEING)
            
            agree_selectors = [
                'xpath://button[contains(@class, "agree-button")]',
                'xpath://button[contains(., "同意并开始使用")]',
                'xpath://button[contains(., "同意")]',
                'button.agree-button',
            ]
            
            clicked = False
            for selector in agree_selectors:
                if self.wait_and_click(selector, timeout=5):
                    clicked = True
                    break
            
            if not clicked:
                raise Exception("无法点击同意按钮")
            
            self.update_status(AccountStatus.WAITING_REDIRECT)
            
            target_pattern = r'business\.gemini\.google/home/cid/[a-f0-9-]+\?csesidx=\d+'
            if not self.wait_for_url_pattern(target_pattern, timeout=90):
                current_url = self.page.url
                if '/admin/create' in current_url:
                    time.sleep(15)
                    if not self.wait_for_url_pattern(target_pattern, timeout=120):
                        raise Exception("页面跳转超时")
                else:
                    raise Exception("页面跳转超时")
            
            time.sleep(3)
            
            self.update_status(AccountStatus.COMPLETING)
            self.handle_welcome_dialog()
            time.sleep(2)
            
            self.update_status(AccountStatus.EXTRACTING_DATA)
            
            if self.extract_data():
                # 设置创建时间
                if not self.account.created_at:
                    self.account.created_at = datetime.now().isoformat()
                self.update_status(AccountStatus.SUCCESS)
                logger.info(f"[{self.worker_id}] 注册成功!")
                return True
            else:
                raise Exception("未能获取完整数据")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[{self.worker_id}] 注册失败: {error_msg}")
            self.update_status(AccountStatus.FAILED, error_msg)
            return False
    
    def refresh_account(self) -> bool:
        """刷新账号Cookie"""
        try:
            self.update_status(AccountStatus.UPDATING)
            logger.info(f"[{self.worker_id}] 正在刷新账号: {self.account.email}")
            
            self.page.get('https://business.gemini.google')
            
            email_input_selectors = [
                'xpath://input[@id="email-input"]',
                'xpath://input[@name="loginHint"]',
                '#email-input',
            ]
            logger.info(f"[{self.worker_id}] 正在等待邮箱输入框: {self.account.email}")
            email_input_found = False
            for selector in email_input_selectors:
                if self.wait_for_element(selector, timeout=30):
                    email_input_found = True
                    break
            
            if not email_input_found:
                raise Exception("等待邮箱输入框超时")
            
            time.sleep(1)
            
            input_success = False
            for selector in email_input_selectors:
                if self.safe_input(selector, self.account.email):
                    input_success = True
                    break
            
            if not input_success:
                raise Exception("无法输入邮箱")
            
            time.sleep(1)
            
            logger.info(f"[{self.worker_id}] 正在点击继续按钮: {self.account.email}")
            continue_selectors = [
                'xpath://button[@id="log-in-button"]',
                'xpath://button[contains(@aria-label, "使用邮箱继续")]',
                '#log-in-button',
            ]
            
            clicked = False
            for selector in continue_selectors:
                if self.wait_and_click(selector, timeout=5):
                    clicked = True
                    break
            
            if not clicked:
                raise Exception("无法点击继续按钮")
            
            time.sleep(2)
            
            email_manager = EmailManager(
                self.account.email_config.get('worker_domain', ''),
                self.account.email_config.get('email_domain', ''),
                self.account.email_config.get('admin_password', '')
            )

            logger.info(f"[{self.worker_id}] 正在获取邮箱验证码: {self.account.email}")
            verification_code = self.get_verification_code_with_retry(email_manager)
            
            if not verification_code:
                raise Exception("未收到验证码 (已重试)")
            
            self.account.verification_code = verification_code
            
            code_input_selectors = [
                'xpath://input[@name="pinInput"]',
                'xpath://input[contains(@aria-label, "验证码")]',
                'input[name="pinInput"]',
            ]
            logger.info(f"[{self.worker_id}] 正在输入验证码: {self.account.email}")
            input_success = False
            for selector in code_input_selectors:
                if self.wait_and_input(selector, verification_code, timeout=10, description="验证码输入框"):
                    input_success = True
                    break
            
            if not input_success:
                raise Exception("无法输入验证码")
            
            time.sleep(1)
            
            if not self.click_verify_button():
                raise Exception("无法点击验证按钮")
            
            time.sleep(3)

            # 检查验证码错误并重试
            if self.page.ele('text:请输入验证码。', timeout=2):
                logger.warning(f"[{self.worker_id}] 验证码失效，尝试重新发送...")
                
                resend_selectors = [
                    'button[aria-label="重新发送验证码"]',
                    'xpath://button[contains(., "重新发送验证码")]'
                ]
                
                resend_clicked = False
                for sel in resend_selectors:
                    if self.wait_and_click(sel, timeout=5):
                        resend_clicked = True
                        break
                
                if resend_clicked:
                    logger.info(f"[{self.worker_id}] 已点击重新发送，等待新验证码...")
                    time.sleep(10) # 等待邮件发送
                    
                    verification_code = email_manager.check_verification_code(self.account.email)
                    if not verification_code:
                         raise Exception("重发后未收到验证码")
                    
                    self.account.verification_code = verification_code
                    logger.info(f"[{self.worker_id}] 获取到新验证码: {verification_code}")
                    
                    input_success = False
                    for selector in code_input_selectors:
                        if self.wait_and_input(selector, verification_code, timeout=10, description="验证码输入框"):
                            input_success = True
                            break
                    
                    if input_success:
                        time.sleep(1)
                        if not self.click_verify_button():
                            raise Exception("无法点击验证按钮(重试)")
                        time.sleep(3)
                    else:
                        raise Exception("无法重新输入验证码")
                else:
                    logger.warning(f"[{self.worker_id}] 未找到重新发送按钮")

            logger.info(f"[{self.worker_id}] 正在等待跳转: {self.account.email}")
            
            target_pattern = r'business\.gemini\.google/home/cid/[a-f0-9-]+\?csesidx=\d+'
            if not self.wait_for_url_pattern(target_pattern, timeout=120):
                raise Exception("页面跳转超时")
            
            time.sleep(3)
            
            self.handle_welcome_dialog()
            time.sleep(2)
            
            if self.extract_data():
                self.account.updated_at = datetime.now().isoformat()
                self.update_status(AccountStatus.SUCCESS)
                logger.info(f"[{self.worker_id}] 刷新成功!")
                return True
            else:
                raise Exception("未能获取完整数据")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[{self.worker_id}] 刷新失败: {error_msg}")
            self.update_status(AccountStatus.FAILED, error_msg)
            return False
    
    def run(self):
        """运行工作线程"""
        success = False
        
        try:
            if not self.create_browser():
                self.update_status(AccountStatus.FAILED, "创建浏览器失败")
                return
            
            if self.mode == "register":
                success = self.register_account()
            else:
                success = self.refresh_account()
                
        except Exception as e:
            self.update_status(AccountStatus.FAILED, str(e))
        finally:
            self.close_browser()
            if self.on_complete:
                self.on_complete(self.worker_id, self.account.email, success)
    
    def stop(self):
        """停止工作线程"""
        self.is_running = False
        self.close_browser()
