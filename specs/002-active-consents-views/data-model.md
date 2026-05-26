# Data Model: Visões de Consentimentos Ativos no Dashboard

**Feature**: `002-active-consents-views`
**Date**: 2026-05-25

---

## Tabelas existentes consumidas (read-only)

### `active_consents`

| Coluna           | Tipo    | Descrição                                                   |
|------------------|---------|-------------------------------------------------------------|
| `receptor_uuid`  | TEXT PK | UUID do receptor                                            |
| `transmitter_uuid` | TEXT PK | UUID do transmissor                                       |
| `receptor`       | TEXT    | Nome legível do receptor (ex.: "Banco Bradesco S.A.")       |
| `transmitter`    | TEXT    | Nome legível do transmissor                                 |
| `date`           | TEXT PK | Data da semana (YYYY-MM-DD)                                 |
| `total`          | INTEGER | Total de consentimentos ativos vigentes na data para o par  |
| `fetched_at`     | TEXT    | Timestamp da coleta                                         |

PK composta: `(receptor_uuid, transmitter_uuid, date)`

### `unique_consents`

| Coluna           | Tipo    | Descrição                              |
|------------------|---------|----------------------------------------|
| `receptor_uuid`  | TEXT PK | UUID do receptor                       |
| `receptor`       | TEXT    | Nome legível do receptor               |
| `date`           | TEXT PK | Data da semana (YYYY-MM-DD)            |
| `total`          | INTEGER | Total de clientes únicos (PF + PJ)     |
| `cpf`            | INTEGER | Clientes PF                            |
| `cnpj`           | INTEGER | Clientes PJ                            |

PK composta: `(receptor_uuid, date)`

---

## Nenhuma tabela nova criada

Esta feature é exclusivamente de leitura. Não há novos writes, novas tabelas ou pré-agregações adicionais.

**Justificativa**: Os dados de `active_consents` já estão na granularidade certa (semanal, por par). O volume por semana (~5.000 linhas) torna as queries de soma/agrupamento simples suficientemente rápidas com os índices abaixo. Uma tabela pré-agregada seria prematura até que os benchmarks confirmem que o limite de 500ms está sendo violado.

---

## Índices novos (adicionados via `_ensure_active_consents_indexes()`)

```sql
-- Queries de evolução temporal e intensidade filtram por date primeiro
CREATE INDEX IF NOT EXISTS idx_active_date_receptor
    ON active_consents(date, receptor_uuid);

-- Queries de evolução por transmissor
CREATE INDEX IF NOT EXISTS idx_active_date_transmitter
    ON active_consents(date, transmitter_uuid);
```

**Onde criar**: função `_ensure_active_consents_indexes()` chamada no `lifespan` de `server.py`, seguindo o padrão de `_ensure_dashboard_indexes()`.

---

## Métricas derivadas (calculadas, não armazenadas)

### Intensidade de Uso

- **Definição**: `active_consents.total (somado por receptor) ÷ unique_consents.total` para a mesma semana
- **Escopo**: por `receptor_uuid × date`
- **JOIN**: `active_consents a LEFT JOIN unique_consents u ON a.receptor_uuid = u.receptor_uuid AND a.date = u.date`
- **Resultado**: float com 1 casa decimal; `NULL` quando `unique_consents.total = 0` ou não existe

### Variação Δ% semanal

- **Definição**: `(total_semana_atual - total_semana_anterior) / total_semana_anterior × 100`
- **Escopo**: por receptor (ranking) ou por transmissor (ranking)
- **Cálculo**: Python — buscar top-20 de duas semanas, calcular Δ% por nome
- **Resultado**: float (1 decimal) ou `None` quando não há semana anterior disponível

---

## Queries de referência por endpoint

### `/api/active-consents/evolution?by=receptor`
```sql
SELECT receptor, date, SUM(total) AS total
FROM active_consents
WHERE date BETWEEN :start AND :end
  -- filtro de receptor (quando receptor_filter != None):
  AND receptor_uuid IN (
      SELECT DISTINCT receptor_uuid FROM active_consents
      WHERE receptor LIKE :pattern
  )
GROUP BY receptor, date
ORDER BY date, total DESC
```

### `/api/active-consents/evolution?by=transmitter`
```sql
SELECT transmitter, date, SUM(total) AS total
FROM active_consents
WHERE date BETWEEN :start AND :end
GROUP BY transmitter, date
ORDER BY date, total DESC
```

### `/api/active-consents/matrix`
```sql
-- Semana mais recente dentro do intervalo
SELECT receptor, transmitter, total
FROM active_consents
WHERE date = (
    SELECT MAX(date) FROM active_consents WHERE date <= :end
)
ORDER BY receptor, transmitter
```

### `/api/active-consents/ranking?by=receptor`
```sql
-- Semana atual
SELECT receptor, SUM(total) AS total
FROM active_consents
WHERE date = :latest_date
GROUP BY receptor
ORDER BY total DESC
LIMIT 20;

-- Semana anterior (para Δ%)
SELECT receptor, SUM(total) AS total
FROM active_consents
WHERE date = :prev_date
GROUP BY receptor
ORDER BY total DESC
LIMIT 20;
```

### `/api/active-consents/intensity`
```sql
SELECT a.receptor,
       SUM(a.total)                                              AS active_total,
       u.total                                                   AS unique_total,
       CASE WHEN u.total > 0
            THEN ROUND(1.0 * SUM(a.total) / u.total, 1)
            ELSE NULL END                                        AS intensity
FROM active_consents a
LEFT JOIN unique_consents u
       ON a.receptor_uuid = u.receptor_uuid AND a.date = :latest_date
WHERE a.date = :latest_date
GROUP BY a.receptor, a.receptor_uuid, u.total
ORDER BY intensity DESC NULLS LAST
```
