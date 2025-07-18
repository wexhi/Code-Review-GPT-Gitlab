@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
echo.
echo [信息] 正在检测宿主机IP地址...
echo [说明] 自动排除WSL/Hyper-V虚拟网络接口
echo.

:: 临时文件
set "temp_file=%temp%\network_info.txt"
set "found_ip="
set "found_type="

:: 获取网络配置
ipconfig /all > "%temp_file%"

:: 搜索WiFi网络接口
echo [搜索] 正在搜索WiFi网络接口...
for /f "tokens=*" %%a in ('findstr /i "WLAN Wi-Fi Wireless" "%temp_file%"') do (
    set "current_line=%%a"
    if "!current_line!" neq "" (
        call :find_ip_for_adapter "!current_line!" WiFi
        if "!found_ip!" neq "" goto :found_result
    )
)

:: 搜索以太网接口（排除虚拟接口）
echo [搜索] 正在搜索以太网接口...
for /f "tokens=*" %%a in ('findstr /i "Ethernet 以太网" "%temp_file%"') do (
    set "current_line=%%a"
    echo !current_line! | findstr /i "vEthernet WSL Hyper-V VirtualBox VMware" > nul
    if !errorlevel! neq 0 (
        call :find_ip_for_adapter "!current_line!" 以太网
        if "!found_ip!" neq "" goto :found_result
    )
)

:: 如果没有找到，显示错误
echo [错误] 未检测到合适的物理网络接口IP地址
echo [提示] 请手动设置HOST_IP环境变量
echo [说明] 可能原因：所有网络接口都是虚拟接口或未连接
goto :cleanup

:found_result
echo [检测] 发现物理网络接口: !found_ip! (!found_type!)
echo.
echo [推荐] 推荐使用的IP地址: !found_ip!
echo.

set /p "choice=是否将 !found_ip! 设置到 .env 文件中? (y/n): "

if /i "!choice!"=="y" (
    if exist ".env" (
        echo [处理] 正在更新 .env 文件...
        
        :: 创建临时文件
        set "env_temp=%temp%\env_temp.txt"
        set "host_ip_set=0"
        
        :: 处理现有的 .env 文件
        for /f "usebackq delims=" %%b in (".env") do (
            set "line=%%b"
            echo !line! | findstr /r "^#*HOST_IP=" > nul
            if !errorlevel! == 0 (
                echo HOST_IP=!found_ip! >> "!env_temp!"
                set "host_ip_set=1"
            ) else (
                echo !line! >> "!env_temp!"
            )
        )
        
        :: 如果没有找到HOST_IP行，则添加
        if !host_ip_set! == 0 (
            echo HOST_IP=!found_ip! >> "!env_temp!"
        )
        
        :: 替换原文件
        move "!env_temp!" ".env" > nul
        
        echo [成功] 已设置 HOST_IP=!found_ip! 到 .env 文件
        echo.
        echo [配置] 配置完成后，请使用以下命令启动服务:
        echo    docker-compose up -d
        echo.
        echo [URL] GitLab Webhook URL 将会是:
        echo    http://!found_ip!:8080/git/webhook
        
    ) else (
        echo [错误] 找不到 .env 文件，请先运行以下命令创建:
        echo    copy env.example .env
    )
) else (
    echo [提示] 您选择了不自动设置，请手动编辑 .env 文件
    echo [URL] GitLab Webhook URL 将会是:
    echo    http://!found_ip!:8080/git/webhook
)

:cleanup
:: 清理临时文件
if exist "%temp_file%" del "%temp_file%"
echo.
echo [完成] 脚本执行完成！
pause
goto :eof

:: 子程序：为指定的适配器查找IP地址
:find_ip_for_adapter
set "adapter_line=%~1"
set "adapter_type=%~2"
set "search_started=0"

for /f "tokens=*" %%c in ('type "%temp_file%"') do (
    set "line=%%c"
    
    :: 如果找到了适配器行，开始搜索
    if "!line!" == "!adapter_line!" (
        set "search_started=1"
    )
    
    :: 如果已经开始搜索，查找IPv4地址
    if "!search_started!" == "1" (
        echo !line! | findstr /i "IPv4" > nul
        if !errorlevel! == 0 (
            for /f "tokens=2 delims=:" %%d in ("!line!") do (
                set "ip=%%d"
                set "ip=!ip: =!"
                set "ip=!ip:(首选)=!"
                set "ip=!ip:(Preferred)=!"
                
                :: 检查是否是私有IP地址
                echo !ip! | findstr /r "^192\.168\." > nul
                if !errorlevel! == 0 (
                    set "found_ip=!ip!"
                    set "found_type=!adapter_type!"
                    goto :eof
                )
                
                echo !ip! | findstr /r "^10\." > nul
                if !errorlevel! == 0 (
                    set "found_ip=!ip!"
                    set "found_type=!adapter_type!"
                    goto :eof
                )
                
                echo !ip! | findstr /r "^172\.1[6-9]\." > nul
                if !errorlevel! == 0 (
                    set "found_ip=!ip!"
                    set "found_type=!adapter_type!"
                    goto :eof
                )
                
                echo !ip! | findstr /r "^172\.2[0-9]\." > nul
                if !errorlevel! == 0 (
                    set "found_ip=!ip!"
                    set "found_type=!adapter_type!"
                    goto :eof
                )
                
                echo !ip! | findstr /r "^172\.3[0-1]\." > nul
                if !errorlevel! == 0 (
                    set "found_ip=!ip!"
                    set "found_type=!adapter_type!"
                    goto :eof
                )
            )
        )
        
        :: 如果遇到下一个适配器行，停止搜索
        echo !line! | findstr /r "^[A-Za-z].*适配器" > nul
        if !errorlevel! == 0 (
            if "!line!" neq "!adapter_line!" (
                set "search_started=0"
            )
        )
    )
)
goto :eof 