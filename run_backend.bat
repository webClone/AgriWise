@echo off
"C:\Users\E-C\AppData\Local\Programs\Python\Python313\python.exe" -m uvicorn services.agribrain.app.main:app --host 127.0.0.1 --port 8000 --reload
pause
