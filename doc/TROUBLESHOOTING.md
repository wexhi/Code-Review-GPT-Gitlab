# 故障排除指南 🔧

本文档帮助您解决在使用 AI Code Review 系统时可能遇到的常见问题。

## 目录
- [PowerShell 脚本编码问题](#powershell-脚本编码问题)
- [Docker 容器问题](#docker-容器问题)
- [Webhook 连接问题](#webhook-连接问题)
- [API 调用问题](#api-调用问题)
- [网络连接问题](#网络连接问题)

## PowerShell 脚本编码问题

### 问题描述
在普通的 PowerShell 终端中运行 `./get-host-ip.ps1` 时出现编码错误：
```
字符串缺少终止符: "。
ParserError: TerminatorExpectedAtEndOfString
```

### 原因分析
- 普通 PowerShell 终端使用 GBK 编码
- VSCode 终端使用 UTF-8 编码
- 中文字符和 emoji 在不同编码下显示异常

### 解决方案

#### 方法1：使用批处理文件（推荐）
```cmd
./get-host-ip.bat
```

#### 方法2：设置 PowerShell 编码
在运行脚本前，先设置编码：
```powershell
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
./get-host-ip.ps1
```

#### 方法3：使用 PowerShell 7+
安装 PowerShell 7 或更高版本，默认使用 UTF-8 编码：
```powershell
winget install Microsoft.PowerShell
```

#### 方法4：在 VSCode 中运行
在 VSCode 的集成终端中运行脚本，编码兼容性更好。

## Docker 容器问题

### 问题1：容器启动失败
```
docker ps
# 显示容器已退出
```

**解决方案**：
```bash
# 查看详细日志
docker logs codereview-uv

# 检查环境变量
docker exec codereview-uv printenv | grep -E "(GITLAB|GEMINI)"

# 重新构建镜像
docker-compose down
docker-compose up -d --build
```

### 问题2：端口冲突
```
Error: Port 8080 is already in use
```

**解决方案**：
```bash
# 查找占用端口的进程
netstat -ano | findstr :8080

# 修改端口映射
# 编辑 docker-compose.yml 中的 ports 配置
ports:
  - "8081:80"  # 改为其他端口
```

### 问题3：权限问题
```
Permission denied
```

**解决方案**：
```bash
# Windows: 以管理员身份运行 PowerShell
# Linux/Mac: 使用 sudo
sudo docker-compose up -d
```

## Webhook 连接问题

### 问题1：GitLab 无法访问 Webhook
```
Connection refused
```

**解决方案**：
```bash
# 检查服务是否运行
curl http://localhost:8080/git/webhook

# 检查防火墙设置
netsh advfirewall firewall add rule name="Docker-CodeReview" dir=in action=allow protocol=TCP localport=8080

# 验证IP地址
./get-host-ip.ps1
```

### 问题2：Webhook 测试失败
```
404 Not Found
```

**解决方案**：
```bash
# 确认 URL 格式正确
http://your-ip:8080/git/webhook
#                     ^^^^^^^^^^^^
#                     必须包含 /git/webhook 路径

# 测试连接
curl -X POST http://localhost:8080/git/webhook -H "Content-Type: application/json" -d '{"test": "data"}'
```

### 问题3：Webhook 收到请求但无响应
```
# 容器日志显示收到请求但处理失败
```

**解决方案**：
```bash
# 检查GitLab Token权限
curl -H "Authorization: Bearer YOUR_TOKEN" https://gitlab.com/api/v4/user

# 检查API Key有效性
curl -H "Authorization: Bearer YOUR_API_KEY" https://generativelanguage.googleapis.com/v1/models
```

## API 调用问题

### 问题1：API Key 无效
```
401 Unauthorized
```

**解决方案**：
```bash
# 验证 Gemini API Key
curl -H "Authorization: Bearer $GEMINI_API_KEY" \
  https://generativelanguage.googleapis.com/v1/models

# 检查 API Key 格式
echo $GEMINI_API_KEY | wc -c  # 应该是特定长度
```

### 问题2：API 调用超时
```
Request timeout
```

**解决方案**：
```bash
# 增加超时时间
# 在 config/config.py 中设置
api_config = {
    # ... 其他配置
    "timeout": 60,  # 增加超时时间
}
```

### 问题3：API 配额不足
```
Quota exceeded
```

**解决方案**：
- 检查 Google Cloud Console 中的 API 配额
- 启用计费账户
- 或切换到其他 API 提供商

## 网络连接问题

### 问题1：DNS 解析失败
```
Name resolution failed
```

**解决方案**：
```bash
# 检查 DNS 设置
nslookup gitlab.com

# 使用 IP 地址替代域名
GITLAB_SERVER_URL=http://192.168.1.100/
```

### 问题2：代理设置
```
Connection refused through proxy
```

**解决方案**：
```bash
# 设置代理环境变量
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080

# 或在 Docker 中设置代理
docker run --env HTTP_PROXY=http://proxy.company.com:8080 ...
```

### 问题3：防火墙阻挡
```
Connection blocked by firewall
```

**解决方案**：
```bash
# Windows 防火墙规则
netsh advfirewall firewall add rule name="CodeReview-Inbound" dir=in action=allow protocol=TCP localport=8080
netsh advfirewall firewall add rule name="CodeReview-Outbound" dir=out action=allow protocol=TCP localport=8080

# Linux iptables
sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
sudo iptables -A OUTPUT -p tcp --dport 8080 -j ACCEPT
```

## 常用调试命令

### 检查服务状态
```bash
# Docker 容器状态
docker ps -a

# 服务日志
docker logs codereview-uv -f

# 端口占用情况
netstat -ano | findstr :8080
```

### 网络连接测试
```bash
# 测试本地连接
curl http://localhost:8080/git/webhook

# 测试远程连接
curl http://your-ip:8080/git/webhook

# 测试 API 连接
curl -H "Authorization: Bearer $API_KEY" https://api.example.com/test
```

### 环境变量检查
```bash
# 容器内环境变量
docker exec codereview-uv printenv

# 本地环境变量
echo $GITLAB_PRIVATE_TOKEN
echo $GEMINI_API_KEY
```

## 获取帮助

如果以上解决方案都无法解决您的问题，请：

1. **查看日志**：`docker logs codereview-uv`
2. **检查配置**：确认所有环境变量都已正确设置
3. **提交 Issue**：在 GitHub 上提交详细的问题描述
4. **联系支持**：发送邮件至 mixuxin@163.com

### 提交 Issue 时请包含：
- 操作系统版本
- Docker 版本
- 错误日志
- 配置文件（移除敏感信息）
- 复现步骤

这样可以帮助我们更快地定位和解决问题。 