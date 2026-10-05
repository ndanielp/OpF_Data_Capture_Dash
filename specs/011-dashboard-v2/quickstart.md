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
6. Métrica API: 14,19 bi/semana, 443 por consentimento/mês, top 3 = 58%; Bradesco 6º (×9,4); Pluggy ×12,3; Santander −44% ↓; Escala "por consentimento" reordena o ecossistema inteiro (Finnet 7.930, Lina 7.057, Banrisul 4.888…); Status "Erros" troca a coluna por taxa de erro (ecossistema 4,7%; Pluggy 34,4%) e as setas ficam sem cor de bom/ruim.
7. "Copiar como imagem" gera PNG 1600×900 com título, filtro, data e fonte; "Baixar CSV" abre no Excel com as mesmas 15 linhas.
8. Link "Painel atual (legado)" abre `/` funcionando como antes.

**O que mudou? (P2)**

9. Agosto/2026: 12 alertas em 6 instituições; Banco do Nordeste como uma oscilação (−31% → +46%); Safra "2º mês seguido"; Santander Investimentos em observação (−44%, confirma em 04/09).

**Instituição (P3)** — Nubank: 4,51 bi chamadas, 866/mês contra 443, taxa de erro 2,30% contra 4,72%, Banco do Brasil 6,6% entre os transmissores.

**Evolução (P3)** — ago/25–ago/26 PF: +115%; Shopee +5,5 pp; Nubank −6,8 pp; Belvo "acelerando" (+12% → +22%); semana 07/08 do Belvo na visão semanal aparece como lacuna, não zero.

## 5. Deploy

Sem mudança no fluxo: `python compute_signals.py` → `.\deploy.ps1`. O 2.0 sobe junto com o legado.
