# Usa Python 3.11 light como base
FROM python:3.11-slim

# Evitar a geração de arquivos .pyc e não fazer buffer de logs do python (para visualizar fácil no docker logs)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório principal do container
WORKDIR /app

# Instala as bibliotecas de Python primeiro (aproveita o cache do docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Cria os diretórios necessários caso não existam (já que foram ignorados)
RUN mkdir -p data logs credentials

# Comando base padrão se nenhum for passado (exemplo: roda o dashboard)
# Se rodar via docker-compose, estes comandos podem ser sobrescritos
CMD ["python", "main.py", "dashboard", "--port", "8000"]
