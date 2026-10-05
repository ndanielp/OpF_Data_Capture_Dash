# Quickstart — Dashboard 2.0

## 1. Preparar a base (data-loader)

```bash
cd data-loader
.venv\Scripts\activate
python compute_signals.py     # agora também reconstrói api_status_weekly e behavior_watch
```

Conferir:

```sql
SELECT COUNT(*) FROM api_status_weekly;          -- ~170 mil linhas (rebuild ~78 s)
SELECT * FROM behavior_watch;                     -- condições em observação da semana mais recente
SELECT metric, COUNT(*) FROM behavior_signals GROUP BY 1;   -- active_consents cai de 25 para ~20 (piso em únicos)
```

## 2. Subir o dashboard

```bash
cd dashboard
.venv\Scripts\activate
uvicorn server:app --reload --port 8000
```

- Legado: http://127.0.0.1:8000/ (inalterado, com link "Dashboard 2.0")
- 2.0: http://127.0.0.1:8000/v2

## 3. Testes

```bash
cd data-loader && python -m pytest tests -q
cd dashboard   && python -m pytest tests -q
```

## 4. Roteiro de validação manual (dados até 28/08/2026)

**Quem lidera? (P1)**

1. Abre em "Consentimentos únicos": PF 145,9 mi, PJ 2,08 mi; ecossistema PF +264,6 mil/dia (antes +250,1 mil, →).
2. Top 15 PF: Nubank 15,1% (22,04 mi, +22,9 mil/dia, +49%); Bradesco 13º destacado como fixado (5,12 mi, +110%).
3. Excluir Shopee: some do PF, Neon (16º) entra; rodapé avisa; recarregar a página mantém a exclusão.
4. Top 15 PJ: Bradesco 4º, crescimento `×5,0`; Klavi `×100`; RecargaPay ritmo −108/dia em vermelho.
5. Métrica Ativos: 254,1 mi, +512,8 mil/dia ↓ (antes +630,5 mil); Bradesco 11º.
6. Métrica API: 14,19 bi/semana, 476 por consentimento/mês (4 semanas → 30 dias, só quem teve chamadas), top 3 = 58%; Bradesco 6º (×9,4); Pluggy ×12,3; Santander −44% ↓; Escala "por consentimento" reordena o ecossistema inteiro (Finnet 9.235, Lina 6.828, Banrisul 4.594…); Status "Erros" troca a coluna por taxa de erro (ecossistema 4,7%; Pluggy 34,4%) e as setas ficam sem cor de bom/ruim.
7. "Copiar como imagem" gera PNG 1600×900 com título, filtro, data e fonte; "Baixar CSV" abre no Excel com as mesmas 15 linhas.
8. Link "Painel atual (legado)" abre `/` funcionando como antes.

**O que mudou? (P2)**

9. Agosto/2026: 12 alertas em 6 instituições; Banco do Nordeste como uma oscilação (−31% → +46%); Safra "2º mês seguido"; Santander Investimentos em observação (−44%, confirma em 04/09).

**Instituição (P3)** — Nubank: 925 por consentimento/mês contra 476 do ecossistema (grupo 605); Bradesco 535 contra 476 (grupo 544); taxa de erro do Nubank 2,4% contra 4,2% nas últimas 4 semanas. Alternar "Comparar com" entre ecossistema, média dos Neobancos e Mercado Pago.

**Evolução (P3)** — ago/25–ago/26 PF: ecossistema +116% (67,7 mi → 145,9 mi; a spec arredondou para +115%); Shopee +5,5 pp (estreou nov/25); Nubank −6,8 pp (cresceu +49%); Belvo "acelerando" (+12% → +22%); semana 07/08 do Belvo na visão semanal aparece como lacuna, não zero. Grupos: Neobancos 43,1% (−3,4 pp), Outros 8,4% (+6,3 pp). Ativos por transmissor: Itaú −1,4 pp, Banco Inter +1,9 pp. "Ver na evolução" no menu da aba 1 (ex.: Bradesco) acrescenta a instituição às 5 maiores.

## 5. Desempenho (T056)

Base real, 10 chamadas por endpoint (`TestClient`, máquina local), p95:

| Endpoint | Sem cache | Após o aquecimento do startup |
|---|---|---|
| `/meta` | 42 ms | 16 ms |
| `/ranking` PF · PJ | 108 · 96 ms | 77 · 68 ms |
| `/ranking` ativos | 598 ms | 78 ms |
| `/ranking` API, status todas | 473 ms | 114 ms |
| `/changes` | 309 ms | 281 ms |
| `/institution/{Nubank}` | 1.160 ms | 280 ms |
| `/evolution` PF · API semanal · ativos por transmissor | 75 · 158 · 744 ms | 54 · 70 · 64 ms |

Sem cache, três leituras passam de 500 ms (agregação de `active_consents` e `api_status_weekly`). Correção: cache das séries com TTL de 24 h (a chave inclui o mtime da base, então dado novo invalida sozinho) e `v2_metrics.warm()` em background no startup (~1,5 s). Depois disso todas ficam abaixo de 300 ms (Princípio IV) e cada aba carrega com 1–3 chamadas (SC-006).

## 6. Deploy

Sem mudança no fluxo: `python compute_signals.py` → `.\deploy.ps1`. O 2.0 sobe junto com o legado.
