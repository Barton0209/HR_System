@echo off
chcp 65001 >nul
cd /d "C:\My_App_OMiK\idps"
set PYTHONIOENCODING=utf-8
set PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

echo ========================================
echo  Обработка паспортов - OCR Pipeline
echo ========================================
echo Лог сохраняется в passport_ocr_run.log
echo.

python passport_ocr.py 2>&1 | tee passport_ocr_run.log

echo.
echo ========================================
echo  Готово! Нажмите любую клавишу...
echo ========================================
pause
