FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装uv
RUN pip install uv

# 设置工作目录
WORKDIR /workspace

# 复制uv配置文件
COPY pyproject.toml uv.lock ./

# 使用uv安装依赖（这比pip快得多）
RUN uv sync

# 复制应用代码
COPY . .

# 设置Python路径
ENV PYTHONPATH=/workspace

# 设置Docker环境标识
ENV DOCKER_ENV=true

# 暴露端口
EXPOSE 80

# 使用uv运行应用
CMD ["uv", "run", "app.py"]


