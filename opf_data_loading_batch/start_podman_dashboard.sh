#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Cria .env a partir do exemplo se ainda não existir
[ -f .env ] || cp .env.example .env

# Garante que os diretórios de volume existam no host
mkdir -p data logs credentials

podman compose up --build dashboard
