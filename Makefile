# Code Review GPT Gitlab - Makefile

.PHONY: help up down build logs status restart clean setup dev prod

# 默认目标
help:
	@echo "Code Review GPT Gitlab - Docker Compose管理"
	@echo ""
	@echo "可用命令:"
	@echo "  setup     - 初始化环境配置"
	@echo "  get-host-ip - 检测宿主机IP地址"
	@echo "  up        - 启动服务"
	@echo "  down      - 停止服务"
	@echo "  build     - 构建镜像"
	@echo "  logs      - 查看日志"
	@echo "  status    - 查看服务状态"
	@echo "  restart   - 重启服务"
	@echo "  clean     - 清理所有容器和镜像"
	@echo "  dev       - 开发环境启动"
	@echo "  prod      - 生产环境启动"
	@echo "  test      - 测试服务连接"

# 获取宿主机IP地址
get-host-ip:
	@echo "🔍 检测宿主机IP地址..."
	@if command -v ip >/dev/null 2>&1; then \
		echo "检测到的IP地址: $$(ip route get 8.8.8.8 | grep -oP 'src \K\S+')"; \
	elif command -v ifconfig >/dev/null 2>&1; then \
		echo "检测到的IP地址: $$(ifconfig | grep -E 'inet.*broadcast' | awk '{print $$2}' | head -1)"; \
	else \
		echo "❌ 无法自动检测IP地址，请手动设置HOST_IP环境变量"; \
	fi

# 初始化环境配置
setup:
	@echo "🔧 初始化环境配置..."
	@if [ ! -f .env ]; then \
		cp env.example .env; \
		echo "✅ 已创建 .env 文件，请编辑后再启动服务"; \
	else \
		echo "✅ .env 文件已存在"; \
	fi
	@mkdir -p logs
	@echo "💡 提示：如果需要设置宿主机IP，请运行 'make get-host-ip' 查看检测到的IP地址"

# 启动服务
up: setup
	@echo "🚀 启动服务..."
	@docker-compose up -d

# 停止服务
down:
	@echo "🛑 停止服务..."
	@docker-compose down

# 构建镜像
build:
	@echo "🏗️  构建镜像..."
	@docker-compose build

# 查看日志
logs:
	@echo "📋 查看日志..."
	@docker-compose logs -f

# 查看服务状态
status:
	@echo "📊 服务状态:"
	@docker-compose ps

# 重启服务
restart:
	@echo "🔄 重启服务..."
	@docker-compose restart

# 清理
clean:
	@echo "🧹 清理容器和镜像..."
	@docker-compose down -v --rmi all --remove-orphans

# 开发环境
dev: setup
	@echo "🧪 启动开发环境..."
	@docker-compose up -d
	@echo "✅ 开发环境已启动: http://localhost:8080"

# 生产环境
prod: setup
	@echo "🚀 启动生产环境..."
	@docker-compose -f docker-compose.prod.yml up -d
	@echo "✅ 生产环境已启动: http://localhost"

# 测试服务
test:
	@echo "🧪 测试服务连接..."
	@curl -s -o /dev/null -w "HTTP状态码: %{http_code}\n" http://localhost:8080 || echo "❌ 服务连接失败"

# 更新服务
update:
	@echo "🔄 更新服务..."
	@docker-compose pull
	@docker-compose up -d --no-deps --build codereview

# 查看配置
config:
	@echo "📋 查看配置..."
	@docker-compose config

# 进入容器
shell:
	@echo "🐚 进入容器..."
	@docker-compose exec codereview /bin/bash 