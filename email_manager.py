import re
import time
import random
import string
from typing import Optional, Tuple
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import requests
import logging

logger = logging.getLogger(__name__)


class EmailManager:
    """邮箱管理器"""
    
    def __init__(self, worker_domain: str, email_domain: str, admin_password: str):
        self.worker_domain = worker_domain
        self.email_domain = email_domain
        self.admin_password = admin_password
    
    @staticmethod
    def generate_random_name() -> str:
        """生成随机邮箱名称"""
        letters1 = ''.join(random.choices(string.ascii_lowercase, k=4))
        numbers = ''.join(random.choices(string.digits, k=2))
        letters2 = ''.join(random.choices(string.ascii_lowercase, k=3))
        return letters1 + numbers + letters2
    
    def create_email(self, username: str = "") -> Tuple[Optional[str], Optional[str]]:
        """创建邮箱"""
        try:
            name = username if username else self.generate_random_name()
            
            res = requests.post(
                f"https://{self.worker_domain}/admin/new_address",
                json={
                    "enablePrefix": True,
                    "name": name,
                    "domain": self.email_domain,
                },
                headers={
                    'x-admin-auth': self.admin_password,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            
            if res.status_code == 200:
                data = res.json()
                return data.get('jwt'), data.get('address')
            else:
                return None, None
        except Exception as e:
            logger.error(f"创建邮箱出错: {e}")
            return None, None
    
    def check_verification_code(self, email: str, max_retries: int = 15, interval: float = 3.0) -> Optional[str]:
        """检查验证码邮件"""
        for attempt in range(max_retries):
            try:
                api_url = f"https://{self.worker_domain}/admin/mails"
                res = requests.get(
                    api_url,
                    params={"limit": 5, "offset": 0, "address": email},
                    headers={
                        "x-admin-auth": self.admin_password,
                        "Content-Type": "application/json"
                    },
                    timeout=30
                )
                
                if res.status_code == 200:
                    data = res.json()
                    
                    if data.get('results') and len(data['results']) > 0:
                        email_data = data['results'][0]
                        raw_content = email_data.get('raw', '')
                        
                        # 检查邮件时间
                        try:
                            # 提取 Received 头中的时间
                            received_match = re.search(r'Received:.*?;\s*(.*?)\r\n', raw_content, re.DOTALL)
                            if received_match:
                                date_str = received_match.group(1).strip()
                                email_time = parsedate_to_datetime(date_str)
                                current_time = datetime.now(timezone.utc)
                                
                                # 如果邮件时间与当前时间相差超过1分钟，则认为是旧邮件
                                if (current_time - email_time) > timedelta(minutes=1):
                                    logger.warning(f"忽略过期邮件 (时间: {email_time}, 当前: {current_time})")
                                    time.sleep(interval)
                                    continue
                        except Exception as e:
                            logger.warning(f"解析邮件时间失败: {e}")

                        cleaned_content = raw_content.replace('=\r\n', '').replace('=\n', '').replace('=3D', '=')
                        
                        patterns = [
                            r'class=["\']?verification-code["\']?[^>]*>([A-Z0-9]{6})</span>',
                            r'verification-code[^>]*>([A-Z0-9]{6})<',
                            r'>([A-Z0-9]{6})</span>',
                            r'font-size:\s*28px[^>]*>([A-Z0-9]{6})<',
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, cleaned_content, re.IGNORECASE | re.DOTALL)
                            if match:
                                code = match.group(1).upper()
                                if len(code) == 6 and code.isalnum():
                                    logger.info(f"找到验证码: {code}")
                                    return code
                
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"检查验证码出错: {e}")
                time.sleep(interval)
        
        return None
