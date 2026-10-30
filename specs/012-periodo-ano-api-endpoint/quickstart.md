# Quickstart — 012

Como subir, testar e validar as três mudanças. Os números de referência saem da base local; confira-os com as consultas indicadas em vez de confiar em valores fixos.

## 1. Preparar a base (necessário para a visão por endpoint)

A tabela `api_endpoint_weekly` é derivada. Em uma base que já existe, basta rodar:

```bash
cd data-loader
.venv/bin/python compute_signals.py     # recria alertas, api_group_weekly, api_status_weekly e api_endpoint_weekly
```

Conferir:

```bash
.venv/bin/python - <<'E'
import sqlite3
c = sqlite3.connect('file:data/consents.db?mode=ro', uri=True)
print(c.execute("select count(*), min(date), max(date) from api_endpoint_weekly").fetchone())
# I1: por (data, receptor, API), a tabela fecha com o agregado quando a soma dos endpoints é menor ou igual a ele
print(c.execute("""
  with a as (select date, receptor_uuid, api, sum(total) agg from api_requests
             where status = 200 and api <> 'consents' and coalesce(endpoint_id,0) = 0 group by 1,2,3),
       t as (select date, receptor_uuid, api, sum(total) tab from api_endpoint_weekly group by 1,2,3)
  select count(*), sum(tab = agg), sum(tab > agg), sum(tab < agg) from a join t using(date, receptor_uuid, api)
""").fetchone())   # esperado: sum(tab > agg) = 0
E
```

## 2. Subir o dashboard

```bash
cd dashboard
source .venv/bin/activate
uvicorn server:app --reload --port 8000
```

## 3. Testes automáticos

```bash
cd data-loader && .venv/bin/python -m pytest tests/test_api_endpoint_weekly.py
cd ../dashboard && .venv/bin/python -m pytest tests/test_v2_evolution.py tests/test_v2_institution.py
cd .. && (cd dashboard && .venv/bin/python -m pytest) && (cd data-loader && .venv/bin/python -m pytest)   # nenhuma regressão
```

## 4. Roteiro manual (http://localhost:8000/v2)

### Período "Desde o começo do ano" (História 1)

1. Em "Como evolui?", abra o filtro de período: a opção "Desde o começo do ano" aparece entre "Últimos 3 meses" e "Desde o início".
2. Escolha-a. O cabeçalho do card de crescimento diz "desde o começo do ano"/"no ano", o gráfico começa na primeira semana de janeiro do ano de `data_through` e termina em `data_through`.
3. Troque para "Quem lidera?" e "Como opera uma instituição?": o período continua selecionado.
4. Escolha uma instituição que estreou depois de janeiro: o crescimento mostra "estreou mmm/aa".
5. Volte aos períodos antigos: os números são idênticos aos de antes (SC-005).
6. (Início de ano) Com uma base cuja última semana cai em janeiro, o card mostra "Poucos dados neste período" e nenhum erro.

### Escala por consentimento (História 2)

1. Em "Como evolui?", abra a métrica "Chamadas de API": a escala "Por consentimento/mês" vem selecionada.
2. A linha do ecossistema aparece como referência; os blocos de participação estão desativados com o texto de explicação.
3. Para uma instituição e uma semana, compare o valor da linha com o de "Quem lidera?" (métrica "Chamadas de API", escala "por consentimento/mês") e com o cartão da aba da instituição: **devem ser iguais** (SC-002).
4. Troque para "Volume (30 dias)": os blocos de participação voltam e os valores são os mesmos de antes da feature.
5. Troque de métrica e volte: a escala escolhida é mantida. Exporte imagem e CSV: título, subtítulo e colunas citam a escala.

### Visão por endpoint (História 3)

1. Em "Como opera uma instituição?", no bloco "Para que usa os dados", a visão por grupo é a padrão e o seletor "Por endpoint" está disponível.
2. Escolha "Por endpoint": o seletor de API lista as APIs que a instituição usa, e a de maior volume está selecionada.
3. A lista mostra todos os endpoints da API, os sem uso ao final com valor zero, e "Sem endpoint identificado" quando houver.
4. Soma dos endpoints = total da API na visão por grupo para a mesma janela (SC-003). Confira a diferença nas unidades "API total" e "%" (deve fechar 100%).
5. Troque a comparação (ecossistema, grupo, outra instituição) e a unidade: a API escolhida é mantida.
6. Troque de aba e volte: o bloco volta para "Por grupo de API".
7. Com uma base sem `api_endpoint_weekly` (por exemplo, a de produção antes de `compute_signals.py`), a visão por grupo funciona e "Por endpoint" mostra a instrução para atualizar a base.

## 5. Publicar

1. `cd data-loader && .venv/bin/python compute_signals.py` (cria e preenche a tabela nova).
2. `cd ../dashboard && ./deploy.sh` (sobe a base, gera a imagem e publica). Para publicar só código, `./deploy.sh --skip-sync`.
3. Confirmar em `/v2/instituicao` que a visão "Por endpoint" responde com dados.
