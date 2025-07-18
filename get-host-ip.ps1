# PowerShell脚本：获取宿主机IP地址
# 用法：./get-host-ip.ps1

# 设置输出编码为UTF-8
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "正在检测宿主机IP地址..." -ForegroundColor Yellow

try {
    # 获取活动网络接口的IP地址
    $networkAdapters = Get-NetIPAddress -AddressFamily IPv4 | 
                      Where-Object { 
                          $_.IPAddress -match "^192\.168\.|^10\.|^172\.(1[6-9]|2[0-9]|3[0-1])\." -and 
                          $_.PrefixOrigin -eq "Dhcp" 
                      } |
                      Sort-Object InterfaceIndex

    if ($networkAdapters.Count -gt 0) {
        Write-Host "[成功] 检测到以下IP地址:" -ForegroundColor Green
        
        foreach ($adapter in $networkAdapters) {
            $interfaceName = (Get-NetAdapter -InterfaceIndex $adapter.InterfaceIndex).Name
            Write-Host "   * $($adapter.IPAddress) (接口: $interfaceName)" -ForegroundColor Cyan
        }
        
        $recommendedIP = $networkAdapters[0].IPAddress
        Write-Host "`n[推荐] 推荐使用的IP地址: $recommendedIP" -ForegroundColor Green
        
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
                    # 在网络配置部分添加HOST_IP
                    $insertIndex = -1
                    for ($i = 0; $i -lt $newContent.Count; $i++) {
                        if ($newContent[$i] -match "网络配置") {
                            $insertIndex = $i + 1
                            break
                        }
                    }
                    
                    if ($insertIndex -gt 0) {
                        $newContent = $newContent[0..($insertIndex-1)] + "HOST_IP=$recommendedIP" + $newContent[$insertIndex..($newContent.Count-1)]
                    } else {
                        $newContent += "HOST_IP=$recommendedIP"
                    }
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
        Write-Host "[错误] 未检测到合适的IP地址" -ForegroundColor Red
        Write-Host "[提示] 请手动设置HOST_IP环境变量" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "[错误] 获取IP地址时出错: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "[提示] 请手动设置HOST_IP环境变量" -ForegroundColor Yellow
}

Write-Host "`n[完成] 脚本执行完成！" -ForegroundColor Green 