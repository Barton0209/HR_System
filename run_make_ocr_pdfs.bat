@echo off
chcp 65001 >nul
cd /d "C:\My_App_OMiK\idps"
set PYTHONIOENCODING=utf-8

echo ========================================
echo  Создание OCR-версий PDF (ФСБ папка)
echo ========================================
echo Лог: make_ocr_pdfs.log
echo Это займёт 30-60 минут...
echo.

python make_ocr_pdfs.py 2>&1 | tee make_ocr_pdfs.log

echo.
echo ========================================
echo  Готово! Нажмите любую клавишу...
echo ========================================
pause
