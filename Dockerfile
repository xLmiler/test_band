# 构建阶段
FROM python:3.10-slim-bullseye AS builder

# 安装必要的系统依赖
RUN apt-get update && apt-get install -y \
  build-essential \
  gcc \
  binutils \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制项目文件
COPY . .

# 安装 Python 依赖
RUN pip install --no-cache-dir \
  pyinstaller \
  flask \
  python-dotenv \
  DrissionPage \
  requests

# 编译二进制文件
RUN pyinstaller --onefile \
  --name app_binary \
  app.py

# 运行阶段
FROM python:3.10-slim-bullseye

# 安装运行时可能需要的最小依赖以及 Chromium 浏览器
# DrissionPage 需要浏览器才能工作
RUN apt-get update && apt-get install -y \
  chromium \
  chromium-driver \
  libpython3.9 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 仅复制编译后的二进制文件
COPY --from=builder /app/dist/app_binary .

# 复制模板文件
COPY templates ./templates

# 设置运行权限
RUN chmod +x app_binary

# 暴露端口
ENV PORT=7860
EXPOSE 7860

# 运行二进制文件
CMD ["./app_binary"]

