@echo off
:: Script para Execucao do Dashboard
echo Iniciando Dashboard
echo Data de início: %date% %time%

:: 1. Entra no diretorio do projeto
cd /d "c:\Users\LENOVO\OneDrive\Documentos\Projetos\claude-antigravity\Claude_Projects\opf_data_loading_batch"

:: 2. Executa a tarefa usando o ambiente virtual integrado
call .venv\Scripts\python.exe main.py dashboard --port 8000