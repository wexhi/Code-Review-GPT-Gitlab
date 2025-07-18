# 快速入门指南 🚀

这个指南将帮助您在 **5 分钟内** 完成 AI 代码审查系统的部署。

## 前置条件

- ✅ 已安装 Docker 和 Docker Compose
- ✅ 已获取 GitLab Private Token
- ✅ 已获取 Gemini API Key

## 步骤 1：克隆项目

```bash
git clone git@github.com:mimo-x/Code-Review-GPT-Gitlab.git
cd Code-Review-GPT-Gitlab
```

## 步骤 2：配置环境变量

### 自动检测并设置宿主机IP（推荐）

**Windows用户**：
```powershell
# 方法1：PowerShell脚本
./get-host-ip.ps1

# 方法2：如果遇到编码问题，使用批处理文件
./get-host-ip.bat
```

**Linux/Mac用户**：
```bash
# 自动检测IP地址
make get-host-ip
```

### 手动配置

```bash
# 复制环境变量模板
cp env.example .env

# 编辑环境变量
vim .env
```

在 `.env` 文件中填入您的配置：

```env
# GitLab 配置
GITLAB_SERVER_URL=https://gitlab.com
GITLAB_PRIVATE_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx

# 大模型 API 配置
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxx

# 钉钉通知配置（可选）
DINGDING_BOT_WEBHOOK=
DINGDING_SECRET=
```

## 步骤 3：启动服务

```bash
# 启动服务
docker-compose up -d

# 查看服务状态
docker-compose ps
```

您应该看到类似以下输出：

```
      Name                    Command               State           Ports
--------------------------------------------------------------------------------
codereview-uv      uv run app.py                    Up      0.0.0.0:8080->80/tcp
```

## 步骤 4：验证部署

```bash
# 查看服务日志
docker-compose logs -f codereview

# 测试服务
curl -X GET http://localhost:8080
```

## 步骤 5：配置 GitLab Webhook

1. **获取 GitLab Private Token**（如果还没有）：
   - GitLab → 头像 → Edit profile → Access Tokens
   - 创建新 Token，勾选 `api`, `read_user`, `read_repository`, `write_repository`

2. **配置 Webhook**：
   - 进入 GitLab 项目 → Settings → Webhooks
   - URL: `http://your-server:8080/git/webhook`
   - Trigger: ✅ Merge request events
   - 保存并测试

## 步骤 6：测试 AI 审查

1. **创建测试分支**
2. **修改一个 Python 文件**
3. **创建 Merge Request**
4. **观察 AI 审查评论**

## 🎉 完成！

您的 AI 代码审查系统现在已经运行！

## 常用命令

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 更新服务
docker-compose pull && docker-compose up -d
```

## 生产环境部署

对于生产环境，使用包含 Nginx 反向代理的配置：

```bash
# 使用生产环境配置
docker-compose -f docker-compose.prod.yml up -d

# 查看所有服务（包括 Nginx）
docker-compose -f docker-compose.prod.yml ps
```

## 故障排除

### 问题 1：容器无法启动

```bash
# 查看详细日志
docker-compose logs codereview

# 检查环境变量
docker-compose exec codereview printenv | grep -E "(GITLAB|GEMINI)"
```

### 问题 2：Webhook 连接失败

```bash
# 测试连接
curl -X POST http://localhost:8080/git/webhook \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### 问题 3：API 调用失败

```bash
# 验证 API 密钥
curl -H "Authorization: Bearer $GEMINI_API_KEY" \
  https://generativelanguage.googleapis.com/v1/models
```

需要更多帮助？请查看完整的 [部署指南](README.md#部署指南-) 或提交 [Issue](https://github.com/mimo-x/Code-Review-GPT-Gitlab/issues)。 