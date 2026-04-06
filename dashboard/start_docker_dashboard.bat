@echo off
echo Inciando o Dashboard via Docker...
docker compose up dashboard -d
echo.
echo Dashboard iniciado! Acesse: http://localhost:8000 nas proximas etapas.
echo.
echo Para ver os logs, voce pode rodar: docker compose logs -f dashboard
pause
