@echo off
REM run_tests.bat - 快速运行测试的批处理文件

echo.
echo ========================================
echo   Function Skill 测试工具
echo ========================================
echo.
echo 请选择要运行的测试：
echo.
echo   1. 自动化测试（验证定义和结构）
echo   2. 演示程序（实际调用 function）
echo   3. 测试单个 function
echo   4. 退出
echo.

set /p choice="请输入选项 (1-4): "

if "%choice%"=="1" (
    echo.
    echo 运行自动化测试...
    powershell -ExecutionPolicy Bypass -File test_all_functions.ps1
) else if "%choice%"=="2" (
    echo.
    echo 运行演示程序...
    powershell -ExecutionPolicy Bypass -File test_demo.ps1
) else if "%choice%"=="3" (
    echo.
    echo 可用的 functions:
    echo   - task_orchestrator
    echo   - code_review
    echo   - fix_issues
    echo   - run_tests
    echo.
    set /p func="请输入 function 名称: "
    echo.
    echo 运行测试: %func%
    powershell -ExecutionPolicy Bypass -File test_all_functions.ps1 -Function %func%
) else if "%choice%"=="4" (
    exit /b 0
) else (
    echo 无效选项
    exit /b 1
)

echo.
pause
