#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Business 账号管理系统 - Flask Web 版本
支持通过邮箱域名自动匹配配置进行刷新/注册
"""

import os
import json
import threading
import queue
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from functools import wraps

from flask import Flask, request, jsonify, render_template, Response
from dotenv import load_dotenv

from browser_worker import BrowserWorker, AccountInfo, AccountStatus
from email_manager import EmailManager
from config import Config

# 加载环境变量
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

# 全局配置和状态
config = Config()
accounts: Dict[str, AccountInfo] = {}  # email -> AccountInfo
workers: Dict[int, BrowserWorker] = {}  # worker_id -> BrowserWorker
task_queue = queue.Queue()
accounts_lock = threading.Lock()
workers_lock = threading.Lock()

# 管理员认证
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')


def check_auth(username, password):
    """验证管理员凭据"""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def authenticate():
    """返回401认证请求"""
    return Response(
        json.dumps({'error': '需要认证'}),
        401,
        {'WWW-Authenticate': 'Basic realm="Admin Area"'}
    )


def requires_auth(f):
    """认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            api_key = (
                request.headers.get("Authorization", "").replace("Bearer ", "") or
                request.headers.get("X-API-Key")
            )
            if api_key != os.getenv('ADMIN_TOKEN', ''):
                return authenticate()
        return f(*args, **kwargs)
    return decorated


def get_available_worker_slot() -> Optional[int]:
    """获取可用的工作槽位"""
    max_workers = config.get_max_workers()
    with workers_lock:
        active_count = sum(1 for w in workers.values() if w.is_alive())
        if active_count >= max_workers:
            return None
        for i in range(max_workers):
            if i not in workers or not workers[i].is_alive():
                return i
    return None


def start_worker(worker_id: int, account: AccountInfo, mode: str = "register"):
    """启动工作线程"""
    worker = BrowserWorker(
        worker_id=worker_id,
        account=account,
        config=config,
        mode=mode,
        on_update=on_account_update,
        on_complete=on_worker_complete
    )
    with workers_lock:
        workers[worker_id] = worker
    worker.start()
    return worker


def on_account_update(email: str, account: AccountInfo):
    """账号更新回调"""
    with accounts_lock:
        accounts[email] = account


def on_worker_complete(worker_id: int, email: str, success: bool):
    """工作线程完成回调"""
    with workers_lock:
        if worker_id in workers:
            del workers[worker_id]


def get_email_config_by_domain(email: str) -> Optional[Dict]:
    """根据邮箱地址获取对应的邮箱配置"""
    if '@' not in email:
        return None
    
    domain = email.split('@')[1].lower()
    email_configs = config.get_email_configs()
    
    for cfg in email_configs:
        if cfg.get('email_domain', '').lower() == domain:
            return cfg
    
    return None


def create_account_from_email(email: str) -> Optional[AccountInfo]:
    """根据邮箱地址创建账号（用于刷新场景）"""
    email_config = get_email_config_by_domain(email)
    if not email_config:
        return None
    
    # 尝试获取JWT
    email_manager = EmailManager(
        email_config['worker_domain'],
        email_config['email_domain'],
        email_config['admin_password']
    )
    
    account = AccountInfo(
        email=email,
        jwt= "",
        status=AccountStatus.PENDING,
        email_config=email_config,
        created_at=datetime.now().isoformat()
    )
    
    return account


# ==================== API 路由 ====================

@app.route('/')
def index():
    """管理面板首页"""
    return render_template('index.html')


@app.route('/api/login', methods=['POST'])
def login():
    """登录验证"""
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    
    if check_auth(username, password):
        token = str(uuid.uuid4())
        return jsonify({
            'success': True,
            'token': token,
            'message': '登录成功'
        })
    
    return jsonify({
        'success': False,
        'message': '用户名或密码错误'
    }), 401


@app.route('/api/accounts', methods=['POST'])
@requires_auth
def create_account():
    """创建新账号"""
    data = request.get_json() or {}
    username = data.get('username', '')
    
    worker_id = get_available_worker_slot()
    if worker_id is None:
        return jsonify({
            'success': False,
            'error': '浏览器线程已达上限，请稍后再试'
        }), 429
    
    email_config = config.get_random_email_config()
    if not email_config:
        return jsonify({
            'success': False,
            'error': '没有配置邮箱域'
        }), 500
    
    email_manager = EmailManager(
        email_config['worker_domain'],
        email_config['email_domain'],
        email_config['admin_password']
    )
    
    jwt, email = email_manager.create_email(username)
    if not jwt or not email:
        return jsonify({
            'success': False,
            'error': '创建邮箱失败'
        }), 500
    
    account = AccountInfo(
        email=email,
        jwt=jwt,
        status=AccountStatus.PENDING,
        email_config=email_config,
        created_at=datetime.now().isoformat()
    )
    
    with accounts_lock:
        accounts[email] = account
    
    start_worker(worker_id, account, mode="register")
    
    return jsonify({
        'success': True,
        'email': email,
        'message': '账号创建已开始'
    })


@app.route('/api/accounts', methods=['GET'])
@requires_auth
def get_accounts():
    """获取账号列表"""
    email = request.args.get('email')
    status_filter = request.args.get('status')
    search = request.args.get('search', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    with accounts_lock:
        if email:
            if email in accounts:
                return jsonify({
                    'success': True,
                    'account': accounts[email].to_dict()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '账号不存在'
                }), 404
        
        result = []
        for acc in accounts.values():
            if status_filter:
                if status_filter == 'success' and acc.status != AccountStatus.SUCCESS:
                    continue
                elif status_filter == 'failed' and acc.status != AccountStatus.FAILED:
                    continue
                elif status_filter == 'creating' and acc.status not in [
                    AccountStatus.PENDING, AccountStatus.CREATING_EMAIL, 
                    AccountStatus.ENTERING_EMAIL, AccountStatus.WAITING_CODE,
                    AccountStatus.VERIFYING, AccountStatus.COMPLETING
                ]:
                    continue
                elif status_filter == 'updating' and acc.status != AccountStatus.UPDATING:
                    continue
            
            if search and search.lower() not in acc.email.lower():
                continue
            
            result.append(acc.to_dict())
        
        total = len(result)
        success_count = sum(1 for acc in accounts.values() if acc.status == AccountStatus.SUCCESS)
        creating_count = sum(1 for acc in accounts.values() if acc.status in [
            AccountStatus.PENDING, AccountStatus.CREATING_EMAIL,
            AccountStatus.ENTERING_EMAIL, AccountStatus.WAITING_CODE,
            AccountStatus.VERIFYING, AccountStatus.COMPLETING, AccountStatus.UPDATING
        ])
        failed_count = sum(1 for acc in accounts.values() if acc.status == AccountStatus.FAILED)
        
        start = (page - 1) * per_page
        end = start + per_page
        paginated = result[start:end]
        
        return jsonify({
            'success': True,
            'accounts': paginated,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page,
            'stats': {
                'total': len(accounts),
                'success': success_count,
                'creating': creating_count,
                'failed': failed_count
            }
        })


@app.route('/api/accounts/<email>', methods=['DELETE'])
@requires_auth
def delete_account(email: str):
    """删除账号"""
    with accounts_lock:
        if email in accounts:
            del accounts[email]
            return jsonify({
                'success': True,
                'message': '账号已删除'
            })
        else:
            return jsonify({
                'success': False,
                'error': '账号不存在'
            }), 404


@app.route('/api/accounts/<email>/refresh', methods=['POST'])
@requires_auth
def refresh_account(email: str):
    """
    刷新账号Cookie
    - 如果账号存在，直接刷新
    - 如果账号不存在但邮箱域名匹配，自动创建并刷新
    """
    with accounts_lock:
        account = accounts.get(email)
    
    # 账号不存在，尝试根据邮箱域名创建
    if not account:
        account = create_account_from_email(email)
        if not account:
            return jsonify({
                'success': False,
                'error': f'账号不存在，且邮箱域名 {email.split("@")[1] if "@" in email else "unknown"} 未配置'
            }), 404
        
        # 保存新创建的账号
        with accounts_lock:
            accounts[email] = account
    
    # 检查是否有可用的工作槽位
    worker_id = get_available_worker_slot()
    if worker_id is None:
        return jsonify({
            'success': False,
            'error': '浏览器线程已达上限，请稍后再试'
        }), 429
    
    # 更新状态
    account.status = AccountStatus.UPDATING
    with accounts_lock:
        accounts[email] = account
    
    # 启动刷新工作线程
    start_worker(worker_id, account, mode="refresh")
    
    return jsonify({
        'success': True,
        'message': '刷新已开始',
        'email': email
    })


@app.route('/api/accounts/refresh-all', methods=['POST'])
@requires_auth
def refresh_all_accounts():
    """刷新所有成功的账号"""
    with accounts_lock:
        success_accounts = [acc for acc in accounts.values() if acc.status == AccountStatus.SUCCESS]
    
    if not success_accounts:
        return jsonify({
            'success': False,
            'error': '没有可刷新的账号'
        }), 400
    
    max_workers = config.get_max_workers()
    queued_count = 0
    
    for account in success_accounts:
        worker_id = get_available_worker_slot()
        if worker_id is not None:
            account.status = AccountStatus.UPDATING
            with accounts_lock:
                accounts[account.email] = account
            start_worker(worker_id, account, mode="refresh")
            queued_count += 1
        else:
            task_queue.put(('refresh', account))
            queued_count += 1
    
    return jsonify({
        'success': True,
        'message': f'已开始刷新 {queued_count} 个账号'
    })


@app.route('/api/accounts/<email>/retry', methods=['POST'])
@requires_auth
def retry_account(email: str):
    """重试失败的账号"""
    with accounts_lock:
        if email not in accounts:
            return jsonify({
                'success': False,
                'error': '账号不存在'
            }), 404
        
        account = accounts[email]
        
        if account.status != AccountStatus.FAILED:
            return jsonify({
                'success': False,
                'error': '只能重试失败的账号'
            }), 400
    
    worker_id = get_available_worker_slot()
    if worker_id is None:
        return jsonify({
            'success': False,
            'error': '浏览器线程已达上限，请稍后再试'
        }), 429
    
    account.status = AccountStatus.PENDING
    account.error_message = ""
    with accounts_lock:
        accounts[email] = account
    
    start_worker(worker_id, account, mode="register")
    
    return jsonify({
        'success': True,
        'message': '重试已开始'
    })


@app.route('/api/accounts/<email>/stop', methods=['POST'])
@requires_auth
def stop_account(email: str):
    """停止账号操作"""
    with workers_lock:
        for worker_id, worker in list(workers.items()):
            if worker.account.email == email:
                worker.stop()
                del workers[worker_id]
                
                with accounts_lock:
                    if email in accounts:
                        accounts[email].status = AccountStatus.FAILED
                        accounts[email].error_message = "用户手动停止"
                
                return jsonify({
                    'success': True,
                    'message': '已停止'
                })
    
    return jsonify({
        'success': False,
        'error': '未找到正在运行的任务'
    }), 404


@app.route('/api/accounts/stop-all', methods=['POST'])
@requires_auth
def stop_all():
    """停止所有操作"""
    stopped_count = 0
    with workers_lock:
        for worker_id, worker in list(workers.items()):
            worker.stop()
            email = worker.account.email
            
            with accounts_lock:
                if email in accounts:
                    accounts[email].status = AccountStatus.FAILED
                    accounts[email].error_message = "用户手动停止"
            
            stopped_count += 1
        workers.clear()
    
    while not task_queue.empty():
        try:
            task_queue.get_nowait()
        except:
            break
    
    return jsonify({
        'success': True,
        'message': f'已停止 {stopped_count} 个任务'
    })


@app.route('/api/accounts/export', methods=['GET'])
@requires_auth
def export_accounts():
    """导出成功的账号（包含时间戳和邮箱）"""
    with accounts_lock:
        success_accounts = [acc for acc in accounts.values() if acc.status == AccountStatus.SUCCESS and acc.is_complete()]
    
    export_data = {
        'accounts': []
    }
    
    for acc in success_accounts:
        export_data['accounts'].append({
            'available': True,
            'email': acc.email,  # 重要：包含邮箱用于刷新
            'csesidx': acc.csesidx,
            'host_c_oses': acc.c_oses,
            'secure_c_ses': acc.c_ses,
            'team_id': acc.config_id,
            'user_agent': config.get_user_agent(),
            'created_at': acc.created_at or datetime.now().isoformat(),
            'updated_at': acc.updated_at or acc.created_at or datetime.now().isoformat()
        })
    
    return jsonify(export_data)


@app.route('/api/settings', methods=['GET'])
@requires_auth
def get_settings():
    """获取设置"""
    return jsonify({
        'success': True,
        'settings': {
            'user_agent': config.get_user_agent(),
            'max_workers': config.get_max_workers(),
            'headless': config.get_headless(),
            'email_configs': config.get_email_configs_safe(),
            'browser_fingerprint': config.get_browser_fingerprint()
        }
    })


@app.route('/api/settings', methods=['POST'])
@requires_auth
def update_settings():
    """更新设置"""
    data = request.get_json()
    
    if 'user_agent' in data:
        config.set_user_agent(data['user_agent'])
    
    if 'max_workers' in data:
        config.set_max_workers(int(data['max_workers']))
    
    if 'headless' in data:
        config.set_headless(bool(data['headless']))
    
    if 'browser_fingerprint' in data:
        config.set_browser_fingerprint(data['browser_fingerprint'])
    
    return jsonify({
        'success': True,
        'message': '设置已更新'
    })


@app.route('/api/email-configs', methods=['GET'])
@requires_auth
def get_email_configs():
    """获取邮箱配置列表"""
    return jsonify({
        'success': True,
        'configs': config.get_email_configs_safe()
    })


@app.route('/api/email-configs', methods=['POST'])
@requires_auth
def add_email_config():
    """添加邮箱配置"""
    data = request.get_json()
    
    worker_domain = data.get('worker_domain', '')
    email_domain = data.get('email_domain', '')
    admin_password = data.get('admin_password', '')
    
    if not all([worker_domain, email_domain, admin_password]):
        return jsonify({
            'success': False,
            'error': '缺少必要参数'
        }), 400
    
    config.add_email_config(worker_domain, email_domain, admin_password)
    
    return jsonify({
        'success': True,
        'message': '邮箱配置已添加'
    })


@app.route('/api/email-configs/<int:index>', methods=['PUT'])
@requires_auth
def update_email_config(index: int):
    """更新邮箱配置"""
    data = request.get_json()
    
    try:
        config.update_email_config(
            index,
            data.get('worker_domain'),
            data.get('email_domain'),
            data.get('admin_password')
        )
        return jsonify({
            'success': True,
            'message': '邮箱配置已更新'
        })
    except IndexError:
        return jsonify({
            'success': False,
            'error': '配置不存在'
        }), 404


@app.route('/api/email-configs/<int:index>', methods=['DELETE'])
@requires_auth
def delete_email_config(index: int):
    """删除邮箱配置"""
    try:
        config.delete_email_config(index)
        return jsonify({
            'success': True,
            'message': '邮箱配置已删除'
        })
    except IndexError:
        return jsonify({
            'success': False,
            'error': '配置不存在'
        }), 404


@app.route('/api/status', methods=['GET'])
@requires_auth
def get_status():
    """获取系统状态"""
    with accounts_lock:
        total = len(accounts)
        success = sum(1 for acc in accounts.values() if acc.status == AccountStatus.SUCCESS)
        creating = sum(1 for acc in accounts.values() if acc.status in [
            AccountStatus.PENDING, AccountStatus.CREATING_EMAIL,
            AccountStatus.ENTERING_EMAIL, AccountStatus.WAITING_CODE,
            AccountStatus.VERIFYING, AccountStatus.COMPLETING
        ])
        updating = sum(1 for acc in accounts.values() if acc.status == AccountStatus.UPDATING)
        failed = sum(1 for acc in accounts.values() if acc.status == AccountStatus.FAILED)
    
    with workers_lock:
        active_workers = sum(1 for w in workers.values() if w.is_alive())
    
    return jsonify({
        'success': True,
        'status': {
            'accounts': {
                'total': total,
                'success': success,
                'creating': creating,
                'updating': updating,
                'failed': failed
            },
            'workers': {
                'active': active_workers,
                'max': config.get_max_workers()
            },
            'queue_size': task_queue.qsize()
        }
    })


# 后台任务处理器
def background_task_processor():
    """后台任务处理器"""
    while True:
        try:
            task = task_queue.get(timeout=1)
            if task is None:
                break
            
            mode, account = task
            worker_id = get_available_worker_slot()
            
            if worker_id is not None:
                start_worker(worker_id, account, mode=mode)
            else:
                task_queue.put(task)
                time.sleep(1)
                
        except queue.Empty:
            continue
        except Exception as e:
            print(f"后台任务处理器错误: {e}")


# 启动后台任务处理器
task_processor_thread = threading.Thread(target=background_task_processor, daemon=True)
task_processor_thread.start()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)
