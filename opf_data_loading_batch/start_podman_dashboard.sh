#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Cria .env a partir do exemplo se ainda não existir
[ -f .env ] || cp .env.example .env

podman compose up --build dashboard
