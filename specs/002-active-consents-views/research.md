# Research: Visões de Consentimentos Ativos no Dashboard

**Feature**: `002-active-consents-views`
**Date**: 2026-05-25
**Status**: Complete — all decisions resolved

---

## R-01 — Heatmap sem biblioteca adicional

**Decision**: Usar tabela HTML (`<table>`) com cores de célula geradas por JavaScript — escala linear de branco a azul escuro proporcional ao valor relativo da célula. Tooltip via `<div>` posicionado absolutamente.

**Rationale**: Chart.js não tem heatmap nativo. O plugin oficial (`chartjs-chart-matrix`) exige CDN externo e adiciona ~15 KB de dependência para uma única visão. Uma tabela HTML é renderizada por qualquer browser, não exige bundler, não conflita com o stack vanilla-JS e pode ser estilizada com o CSS já presente. Performance é adequada: até 50 receptores × 100 transmissores = 5.000 células, manipuladas em DOM uma única vez.

**Alternatives considered**:
- `chartjs-chart-matrix` plugin (rejeitado: CDN externo; quebra o princípio "Chart.js apenas" na prática ao adicionar uma camada não-Chart.js; complexidade de configuração desnecessária para o caso de uso)
- D3.js (rejeitado: explicitamente proibido pela Constituição)
- CSS Grid (equivalente à tabela, mas sem semântica de dados tabular; tabela é semanticamente correto para uma matriz)

---

## R-02 — Paleta de cores para séries de instituições (N variável)

**Decision**: Reutilizar `_build_color_map()` existente em `server.py`, que consulta `BRAND_COLORS` (cores canônicas por substring de nome) e cai em `_FALLBACK_COLORS` para instituições sem cor registrada. Esta função já é usada em todos os endpoints existentes de séries por receptor.

**Rationale**: A Constituição (Princípio III) proíbe valores hex hardcoded em HTML/JS e exige que cores venham de `API_GROUPS`. Para séries de instituições, `API_GROUPS` não é aplicável (é para grupos de API, não para bancos). O padrão já estabelecido é `_build_color_map()` — usando `BRAND_COLORS` como fonte canônica de cores por instituição. O novo router active_consents chama `_build_color_map()` via `server._build_color_map` ou, preferível, extrai a função para `services/constants.py` para que ambos possam importá-la.

**Constitution note**: O Princípio III se aplica à paleta de grupos de API. Para paleta de instituições, `_build_color_map()` + `BRAND_COLORS` é o padrão consagrado (já em uso em 5+ endpoints). Sem violação.

---

## R-03 — Cálculo de Δ% semana a semana

**Decision**: Buscar duas semanas de dados do ranking via SQL (semana mais recente e semana imediatamente anterior disponível) e calcular Δ% em Python.

**Rationale**: SQLite tem `LAG()` como window function, mas requer que todas as datas estejam presentes e sem gaps — o que não pode ser garantido (coleta pode falhar para uma semana). Calcular em Python com dois `SELECT` simples é mais robusto, testável e legível. O volume de dados (top-20 por semana = 40 linhas) torna a abordagem negligenciável em performance.

**Fórmula**: `Δ% = round((curr - prev) / prev * 100, 1)` se `prev > 0`; caso contrário `None` (exibido como "—" no frontend).

---

## R-04 — Índices de performance para `active_consents`

**Decision**: Criar dois índices compostos na inicialização do dashboard, em função `_ensure_active_consents_indexes()` chamada no `lifespan`:
```sql
CREATE INDEX IF NOT EXISTS idx_active_date_receptor
    ON active_consents(date, receptor_uuid);
CREATE INDEX IF NOT EXISTS idx_active_date_transmitter
    ON active_consents(date, transmitter_uuid);
```

**Rationale**: Os padrões de query mais frequentes filtram por `date` (semana mais recente ou intervalo) e agrupam por `receptor_uuid` ou `transmitter_uuid`. Sem índices, cada query faz full table scan em `active_consents`. Com ~5.000 pares × N semanas, o scan pode ultrapassar 50.000 linhas após 10 semanas de coleta — violando o limite de 500ms (Constituição IV). O padrão de `CREATE INDEX IF NOT EXISTS` já é usado em `_ensure_dashboard_indexes()` para `unique_consents`.

---

## R-05 — Localização dos endpoints: novo router ou server.py

**Decision**: Novo arquivo `dashboard/routers/active_consents.py`, registrado em `server.py` com `app.include_router(...)`.

**Rationale**: Os endpoints de `active_consents` formam uma unidade coesa (4–5 funções) que serve exclusivamente `active_consents.html`. O precedente de `routers/openfinance.py` (que serve `receptor_profile.html`) é idêntico. Adicionar 4-5 funções diretamente a `server.py` já aumentaria ainda mais um arquivo com 1.160 linhas. O Princípio I (Code Quality) prioriza simplicidade — um arquivo menor por responsabilidade é mais simples.

---

## R-06 — Nova página HTML

**Decision**: Nova página standalone `dashboard/gui/active_consents.html`, servida em `/active-consents`. Links de navegação adicionados no header das páginas existentes (`dashboard.html` e `receptor_profile.html`).

**Rationale**: Manter as páginas existentes intactas minimiza risco de regressão. Uma nova página dedicada permite layouts específicos (ex.: tabela para heatmap) sem comprometer o CSS/JS das páginas existentes. A navegação por links simples `<a href="...">` é o padrão já usado no projeto.

---

## R-07 — Intensidade de Uso: JOIN entre tabelas

**Decision**: JOIN entre `active_consents` e `unique_consents` por `(receptor_uuid, date)`, somando totais de `active_consents` por receptor e usando o valor de `unique_consents` como denominador.

**Rationale**: `active_consents` tem granularidade `receptor × transmitter × date`; `unique_consents` tem `receptor × date`. O JOIN correto é por `(receptor_uuid, date)` — que é um equi-join eficiente se ambas as colunas estiverem indexadas. `NULLIF(u.total, 0)` evita divisão por zero. `LEFT JOIN` garante que receptores sem dados em `unique_consents` apareçam com intensidade `NULL` (exibido como "—").

**SQL pattern**:
```sql
SELECT a.receptor,
       SUM(a.total)                                         AS active_total,
       u.total                                              AS unique_total,
       CASE WHEN u.total > 0
            THEN ROUND(1.0 * SUM(a.total) / u.total, 1)
            ELSE NULL END                                   AS intensity
FROM active_consents a
LEFT JOIN unique_consents u
       ON a.receptor_uuid = u.receptor_uuid AND a.date = ?
WHERE a.date = ?
GROUP BY a.receptor, a.receptor_uuid, u.total
ORDER BY intensity DESC NULLS LAST
```
