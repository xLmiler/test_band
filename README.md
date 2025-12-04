# Gemini Business 账号管理系统

这是一个基于 Flask 和 DrissionPage 的自动化系统，用于批量注册和管理 Gemini Business 账号。支持通过 Docker 部署，提供 RESTful API 和简单的 Web 管理界面。

## 功能特性

*   **自动化注册**: 全自动完成 Gemini Business 账号的注册流程。
*   **账号保活/刷新**: 支持自动刷新账号 Cookie，保持会话有效。
*   **多账号管理**: 支持配置多个邮箱域名和管理密码。
*   **并发控制**: 可配置最大并发浏览器数量，避免资源过载。
*   **Web 管理界面**: 提供直观的 Web 界面查看账号状态、手动触发注册/刷新。
*   **RESTful API**: 提供完整的 API 接口，方便集成。

## 快速开始

### Docker 部署 (推荐)

1.  **构建镜像**

    ```bash
    docker build -t gemini-manager .
    ```

2.  **运行容器**

    ```bash
    docker run -d \
      -p 7860:7860 \
      --env-file .env \
      --name gemini-manager \
      gemini-manager
    ```

### 本地运行

1.  **安装依赖**

    需要 Python 3.10+ 和 Chrome/Chromium 浏览器。

    ```bash
    pip install -r requirements.txt
    ```
    *(注: 如果没有 requirements.txt，请安装: `flask python-dotenv DrissionPage requests`)*

2.  **运行**

    ```bash
    python app.py
    ```

## 环境变量配置

请在项目根目录创建 `.env` 文件或在 Docker 运行命令中指定。

### 基础配置

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `PORT` | `7860` | 服务监听端口 |
| `SECRET_KEY` | `your-secret-key...` | Flask Session 密钥，生产环境请修改 |
| `DEBUG` | `false` | 是否开启调试模式 |

### 管理员认证

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `ADMIN_USERNAME` | `admin` | Web 界面登录用户名 |
| `ADMIN_PASSWORD` | `admin123` | Web 界面登录密码 |
| `ADMIN_TOKEN` | - | API 调用鉴权 Token (Header: `X-API-Key` 或 `Authorization: Bearer ...`) |

### 浏览器与并发

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `MAX_WORKERS` | `1` | 最大并发浏览器实例数，建议根据机器性能调整 |
| `HEADLESS` | `true` | 是否使用无头模式运行浏览器 (Docker 环境必须为 true) |
| `USER_AGENT` | (Chrome UA) | 浏览器使用的 User-Agent |

### 邮箱服务配置 (核心)

支持配置多组邮箱服务，使用分号 `;` 分隔。三组配置的顺序必须一一对应。

| 变量名 | 说明 | 示例 |
| :--- | :--- | :--- |
| `WORKER_DOMAINS` | 邮箱管理后台域名 (Cloudflare Worker) | `admin.domain1.com;admin.domain2.com` |
| `EMAIL_DOMAINS` | 注册用的邮箱后缀域名 | `domain1.com;domain2.com` |
| `ADMIN_PASSWORDS` | 邮箱管理后台的访问密码 (`x-admin-auth`) | `pass1;pass2` |

### 浏览器指纹 (高级配置)

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `WINDOW_SIZE` | `1920x1080` | 浏览器窗口大小 |
| `TIMEZONE` | `Asia/Shanghai` | 浏览器时区 |
| `LOCALE` | `zh-CN` | 浏览器语言环境 |
| `PLATFORM` | `Win64` | 模拟的操作系统平台 |
| `COLOR_DEPTH` | `24` | 颜色深度 |
| `DEVICE_MEMORY` | `8` | 设备内存 (GB) |
| `HARDWARE_CONCURRENCY`| `8` | CPU 核心数 |

## API 接口

所有 API 需要 Bearer Token (`ADMIN_TOKEN`) 认证。

*   `GET /api/status`: 获取系统状态（账号数、Worker 状态）。
*   `GET /api/accounts`: 获取账号列表。
*   `POST /api/accounts`: 创建新账号。
*   `POST /api/accounts/<email>/refresh`: 刷新指定账号。
*   `POST /api/accounts/refresh-all`: 刷新所有成功账号。
*   `DELETE /api/accounts/<email>`: 删除账号。
*   `GET /api/accounts/export`: 导出可用账号信息。

## 目录结构

*   `app.py`: Flask 主程序，处理 API 和 Web 请求。
*   `browser_worker.py`: 浏览器自动化逻辑核心，使用 DrissionPage。
*   `config.py`: 配置管理，处理环境变量。
*   `email_manager.py`: 邮箱 API 交互逻辑。
*   `Dockerfile`: Docker 构建文件。
