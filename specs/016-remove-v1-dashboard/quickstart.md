# Quickstart: Remover o painel v1

## Antes de apagar (linha de base)

Com o servidor atual (branch `main`) rodando na base real, gravar as respostas do v2 e uma exportação:

```bash
mkdir -p /tmp/v1-baseline && cd /tmp/v1-baseline
for p in meta ranking evolution changes; do curl -s "localhost:8000/api/v2/$p" > "$p.json"; done
```

(os parâmetros e a exportação exata ficam em `tasks.md`, T002).

## Depois de apagar

```bash
cd dashboard
uvicorn server:app --port 8000
```

1. `curl -sI localhost:8000/`, `/profile`, `/active-consents?x=1` → `307` com `location: /v2`.
2. `curl -s -o /dev/null -w '%{http_code}' localhost:8000/api/consents` → `404` (e o mesmo para as demais rotas removidas).
3. Repetir as chamadas da linha de base e comparar com `diff` → sem diferença.
4. Abrir as cinco páginas v2: sem o link "Painel legado", filtros e exportação funcionando.
5. `pytest tests -q` → tudo verde.
6. `git grep -il "painel legado\|dashboard.html\|receptor_profile\|of_analytics"` → sem resultados fora de `specs/` históricas.
