@echo off
chcp 65001 > nul
echo.
echo [信息] 正在检测宿主机IP地址...
echo.

:: 获取IP地址
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /i "IPv4"') do (
    set "ip=%%i"
    setlocal enabledelayedexpansion
    set "ip=!ip: =!"
    echo [检测] 发现IP地址: !ip!
    
    :: 检查是否是私有IP地址
    echo !ip! | findstr /r "^192\.168\." > nul
    if !errorlevel! == 0 (
        set "recommended_ip=!ip!"
        goto :found
    )
    
    echo !ip! | findstr /r "^10\." > nul
    if !errorlevel! == 0 (
        set "recommended_ip=!ip!"
        goto :found
    )
    
    echo !ip! | findstr /r "^172\.1[6-9]\." > nul
    if !errorlevel! == 0 (
        set "recommended_ip=!ip!"
        goto :found
    )
    
    echo !ip! | findstr /r "^172\.2[0-9]\." > nul
    if !errorlevel! == 0 (
        set "recommended_ip=!ip!"
        goto :found
    )
    
    echo !ip! | findstr /r "^172\.3[0-1]\." > nul
    if !errorlevel! == 0 (
        set "recommended_ip=!ip!"
        goto :found
    )
    
    endlocal
)

echo [错误] 未检测到合适的私有IP地址
echo [提示] 请手动设置HOST_IP环境变量
goto :end

:found
echo.
echo [推荐] 推荐使用的IP地址: !recommended_ip!
echo.

set /p "choice=是否将 !recommended_ip! 设置到 .env 文件中? (y/n): "

if /i "!choice!"=="y" (
    if exist ".env" (
        echo [处理] 正在更新 .env 文件...
        
        :: 创建临时文件
        set "temp_file=%temp%\env_temp.txt"
        set "host_ip_set=0"
        
        :: 处理现有的 .env 文件
        for /f "usebackq delims=" %%a in (".env") do (
            set "line=%%a"
            echo !line! | findstr /r "^#*HOST_IP=" > nul
            if !errorlevel! == 0 (
                echo HOST_IP=!recommended_ip! >> "!temp_file!"
                set "host_ip_set=1"
            ) else (
                echo !line! >> "!temp_file!"
            )
        )
        
        :: 如果没有找到HOST_IP行，则添加
        if !host_ip_set! == 0 (
            echo HOST_IP=!recommended_ip! >> "!temp_file!"
        )
        
        :: 替换原文件
        move "!temp_file!" ".env" > nul
        
        echo [成功] 已设置 HOST_IP=!recommended_ip! 到 .env 文件
        echo.
        echo [配置] 配置完成后，请使用以下命令启动服务:
        echo    docker-compose up -d
        echo.
        echo [URL] GitLab Webhook URL 将会是:
        echo    http://!recommended_ip!:8080/git/webhook
        
    ) else (
        echo [错误] 找不到 .env 文件，请先运行以下命令创建:
        echo    copy env.example .env
    )
) else (
    echo [提示] 您选择了不自动设置，请手动编辑 .env 文件
    echo [URL] GitLab Webhook URL 将会是:
    echo    http://!recommended_ip!:8080/git/webhook
)

endlocal

:end
echo.
echo [完成] 脚本执行完成！
pause 