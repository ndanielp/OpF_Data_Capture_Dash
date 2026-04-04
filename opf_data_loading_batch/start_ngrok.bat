@echo off
echo Iniciando o Ngrok para expor a porta 8000 na internet...
echo.
echo Mantenha esta janela aberta para manter o link online.
echo Pressione CTRL+C para encerrar.
echo.
ngrok http 8000
pause
