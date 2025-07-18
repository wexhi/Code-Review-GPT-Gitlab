# PowerShell脚本：获取宿主机IP地址
# 用法：./get-host-ip.ps1

# 设置输出编码为UTF-8
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "正在检测宿主机IP地址..." -ForegroundColor Yellow

try {
    # 获取所有活动的网络适配器
    $allAdapters = Get-NetAdapter | Where-Object { $_.Status -eq 'Up' }
    
    $foundIPs = @()
    
    foreach ($adapter in $allAdapters) {
        # 排除虚拟网络接口
        $isVirtual = $adapter.Name -match "vEthernet|WSL|Hyper-V|VirtualBox|VMware|Loopback"
        
        if (!$isVirtual) {
            # 获取该适配器的IP地址
            $ipAddresses = Get-NetIPAddress -InterfaceIndex $adapter.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | 
                          Where-Object { 
                              $_.IPAddress -match "^192\.168\.|^10\.|^172\.(1[6-9]|2[0-9]|3[0-1])\." -and
                              $_.IPAddress -notmatch "^169\.254\."
                          }
            
            foreach ($ip in $ipAddresses) {
                $priority = 3  # 默认优先级
                $type = "其他"
                
                # 设置优先级
                if ($adapter.Name -match "WLAN|Wi-Fi|Wireless") {
                    $priority = 1
                    $type = "WiFi"
                } elseif ($adapter.Name -match "Ethernet|以太网") {
                    $priority = 2
                    $type = "以太网"
                }
                
                $foundIPs += [PSCustomObject]@{
                    IP = $ip.IPAddress
                    InterfaceName = $adapter.Name
                    Type = $type
                    Priority = $priority
                }
                
                Write-Host "[检测] 发现物理网络接口: $($ip.IPAddress) (接口: $($adapter.Name)) - $type" -ForegroundColor Cyan
            }
        }
    }
    
    # 按优先级排序
    $foundIPs = $foundIPs | Sort-Object Priority, IP
    
    if ($foundIPs.Count -gt 0) {
        $recommendedIP = $foundIPs[0].IP
        $recommendedType = $foundIPs[0].Type
        
        Write-Host "`n[推荐] 推荐使用的IP地址: $recommendedIP ($recommendedType)" -ForegroundColor Green
        Write-Host "[说明] 已自动排除WSL/Hyper-V虚拟网络接口" -ForegroundColor Yellow
        
        # 询问用户是否要设置到环境变量
        $choice = Read-Host "`n是否将 $recommendedIP 设置到 .env 文件中? (y/n)"
        
        if ($choice -eq 'y' -or $choice -eq 'Y') {
            if (Test-Path ".env") {
                # 读取现有的.env文件
                $envContent = Get-Content ".env"
                $newContent = @()
                $hostIPSet = $false
                
                foreach ($line in $envContent) {
                    if ($line -match "^#?\s*HOST_IP=") {
                        $newContent += "HOST_IP=$recommendedIP"
                        $hostIPSet = $true
                    } else {
                        $newContent += $line
                    }
                }
                
                if (-not $hostIPSet) {
                    $newContent += "HOST_IP=$recommendedIP"
                }
                
                Set-Content ".env" -Value $newContent
                Write-Host "[成功] 已设置 HOST_IP=$recommendedIP 到 .env 文件" -ForegroundColor Green
            } else {
                Write-Host "[错误] 找不到 .env 文件，请先运行 'make setup' 或 'Copy-Item env.example .env'" -ForegroundColor Red
            }
        }
        
        Write-Host "`n[配置] 配置完成后，请使用以下命令启动服务:" -ForegroundColor Yellow
        Write-Host "   docker-compose up -d" -ForegroundColor Cyan
        Write-Host "`n[URL] GitLab Webhook URL 将会是:" -ForegroundColor Yellow
        Write-Host "   http://$recommendedIP:8080/git/webhook" -ForegroundColor Cyan
        
    } else {
        Write-Host "[错误] 未检测到合适的物理网络接口IP地址" -ForegroundColor Red
        Write-Host "[提示] 请手动设置HOST_IP环境变量" -ForegroundColor Yellow
        Write-Host "[说明] 可能原因：所有网络接口都是虚拟接口或未连接" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "[错误] 获取IP地址时出错: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "[提示] 请手动设置HOST_IP环境变量" -ForegroundColor Yellow
}

Write-Host "`n[完成] 脚本执行完成！" -ForegroundColor Green 