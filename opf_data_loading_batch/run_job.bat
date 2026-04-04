@echo off
:: Script para Execucao em Lote (Agendador de Tarefas do Windows)
echo Iniciando Coleta Open Finance Lote
echo Data de início: %date% %time%

:: 1. Entra no diretorio do projeto
cd /d "c:\Users\LENOVO\OneDrive\Documentos\Projetos\claude-antigravity\Claude_Projects\opf_data_loading_batch"

:: 2. Executa a tarefa usando o ambiente virtual integrado
::    Substitua os parametros abaixo conforme a frequencia de sua preferencia
call .venv\Scripts\python.exe main.py run --start-date "2025-06-01" --workers 1

echo Comando Finalizado! %date% %time%
