# Usa Python 3.11 light como base
FROM python:3.11-slim

# Evitar a geração de arquivos .pyc e não fazer buffer de logs do python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Bucket GCS de onde o dashboard baixa os dados (definido via --set-env-vars no deploy)
ENV GCS_BUCKET=""
ENV GCS_PREFIX="data/"

# Define o diretório principal do container
WORKDIR /app

# Instala as bibliotecas de Python primeiro (aproveita o cache do docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Cria os diretórios necessários
RUN mkdir -p data logs credentials

# Entrypoint: shell mínimo + lógica em Python (evita problemas de CRLF/heredoc no sh)
COPY entrypoint.sh /entrypoint.sh
COPY entrypoint.py /app/entrypoint.py
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
