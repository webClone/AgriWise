@echo off
echo ==========================================
echo   AgriBrain Manual Environment Setup
echo ==========================================
echo.
echo Installing Python libraries (using pydantic v1 for compatibility)...
echo.
"C:\Users\E-C\AppData\Local\Programs\Python\Python315\python.exe" -m pip install "fastapi<0.100" "pydantic<2" requests python-dotenv uvicorn numpy
echo.
echo ==========================================
echo   Installation Complete!
echo   Please close this window and restart the backend.
echo ==========================================
pause
