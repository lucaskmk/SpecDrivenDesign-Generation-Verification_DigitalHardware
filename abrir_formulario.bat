@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe -m streamlit run src\spechdl\ingestion\web_form.py
