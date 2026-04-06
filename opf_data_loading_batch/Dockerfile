# Usa Python 3.11 light como base
FROM python:3.11-slim

# Evitar a geração de arquivos .pyc e não fazer buffer de logs do python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Bucket GCS de onde o dashboard baixa os dados (definido via --set-env-vars no deploy)
ENV GCS_BUCKET=""
ENV GCS_PREFIX="data/"

# Instala dependências de sistema
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório principal do container
WORKDIR /app

# Instala as bibliotecas de Python primeiro (aproveita o cache do docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright só é necessário para o batch (local) — não instalar para o dashboard no Cloud Run
# RUN playwright install --with-deps chromium

# Copia o código da aplicação
COPY . .

# Cria os diretórios necessários
RUN mkdir -p data logs credentials

# Script de entrypoint: baixa dados do GCS e depois inicia o servidor
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "main.py", "dashboard", "--port", "8000"]
