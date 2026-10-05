# Phase 0 Research: Detecção de Mudanças de Comportamento

Stack fixada pela Constituição; não há incógnitas de tecnologia. As regras de negócio
foram decididas e calibradas na spec (Clarifications). Aqui ficam as decisões de desenho
que a spec não cobre. Todos os números abaixo foram medidos em `consents.db`
(jan/2024 – ago/2026).

## Decisão 1 — Reconstruir o histórico inteiro a cada execução

**Decisão**: `compute_signals.py` apaga e reconstrói `behavior_signals` para **todas** as
semanas em toda execução, numa única transação.

**Rationale**:
- **Idempotente por construção** (Princípio II): rodar duas vezes produz as mesmas linhas.
- **Histórico coerente** (FR-008, FR-010): se um limite mudar, todas as semanas passam a
  refletir a mesma regra — nada de semanas antigas calculadas com a regra velha.
- **Barato**: ~140 semanas × ~50 receptores × 6 grupos; a calibração completa rodou em
  segundos com pandas.
- **Resolve a validação da SC-002**: o próprio cálculo normal já reprocessa o histórico,
  então os eventos conhecidos (Inter, Belvo, Safra…) são verificáveis direto na tabela.

**Alternativas**: cálculo incremental só da semana nova — rejeitado: mais estado, mais
casos de borda (regras de 4+4 semanas e de "primeira vez" dependem de semanas
anteriores), e nenhum ganho de desempenho relevante nesse volume.

## Decisão 2 — Recalcular `api_group_weekly` antes dos alertas

**Decisão**: A primeira etapa de `compute_signals.py` é chamar
`scrapers.refresh_api_group_weekly()`.

**Rationale**: Verificado em 2026-09-23: `api_group_weekly` termina em 31/07 enquanto
`api_requests` vai até 28/08. O refresh hoje só roda no fim de uma coleta concluída, e as
duas últimas coletas (21/09) não concluíram. Sem esta etapa, os alertas de API sairiam
de uma semana diferente dos de consentimento. A função reconstrói a tabela inteira e é
idempotente; chamá-la de dois lugares do mesmo componente não cria conflito.

**Efeito colateral positivo**: rodar `compute_signals.py` também atualiza o mapa
estratégico, a aceleração e a eficiência do dashboard, que leem a mesma tabela.

## Decisão 3 — Trava de cobertura para alertas de API

**Decisão**: Uma semana só recebe alertas de API se o total de chamadas do ecossistema
(status 200, sem `consents`) for **≥ 70% da mediana das 8 semanas anteriores**. Semanas
que não passam são registradas como "API incompleta" (ver data-model) e o card informa
isso em vez de mostrar silêncio.

**Rationale**: Coleta parcial afeta receptores isoladamente e gera quedas falsas que o
desconto do ecossistema não corrige totalmente. Calibração: no histórico nenhuma semana
fica abaixo de 70%; as mais baixas são 76% (29/03/2024, Sexta-feira Santa; 12/04 e
26/04/2024) — feriados, já neutralizados pelo desconto do ecossistema. Ou seja, a trava
**não suprime nenhum dado histórico** e só atua num caso futuro de coleta quebrada.

**Complemento automático**: receptor × semana ausente vira `NaN` na série, e a média
móvel de 4 semanas com um `NaN` também é `NaN` — então dado faltante não vira queda.

**Alternativas**: usar `run_summary`/`fetch_attempts` para saber se a coleta da semana
terminou — rejeitado: uma semana é coberta por várias execuções (retomadas, fases
separadas) e a telemetria não mapeia 1:1 para semanas de dado.

## Decisão 4 — Janelas por posição temporal, como na calibração

**Decisão**:
- **Novo entrante e variação de consentimentos**: a "semana anterior" e a "base de 4
  semanas" são as observações anteriores **do próprio receptor** (posição na série dele).
- **Uso de API**: pivô por data de calendário (todas as sextas presentes na base), médias
  móveis de 4 sobre esse eixo.

**Rationale**: É exatamente como a calibração foi feita, então os eventos de validação da
SC-002 (Inter na semana 6, CloudWalk na 3, etc.) saem idênticos. Para API, o eixo de
calendário é o que permite dividir pelo movimento do ecossistema na mesma semana.

## Decisão 5 — Filtro de grupos aplicado no dashboard, na leitura

**Decisão**: `behavior_signals` guarda o receptor (UUID e nome), não o grupo de
instituição. O endpoint resolve o grupo com `resolve_institution_group()` (feature 009)
e filtra.

**Rationale**: A classificação de grupos vive em `dashboard/services/constants.py`; o
`data-loader` não pode importá-la (Princípio V). Resolver na leitura também faz o card
acompanhar qualquer ajuste futuro na classificação sem recalcular os alertas.

## Decisão 6 — Uma linha por alerta, não um resumo pré-montado

**Decisão**: A tabela guarda uma linha por alerta (tipo, métrica, grupo de API,
receptor, semana, valor anterior, valor atual, variação). O agrupamento por seção e por
instituição (FR-009) é feito no endpoint.

**Rationale**: O seletor de semana (FR-010) e o filtro de grupos (FR-011) precisam
consultar e filtrar; um resumo pré-montado por semana não pode ser filtrado.

## Decisão 7 — Ordenação por volume da instituição

**Decisão**: "Volume da instituição" (FR-009) = consentimentos únicos do receptor na
semana do alerta (0 se não houver). É o mesmo critério nas três seções.

**Rationale**: Métrica presente para todos os receptores e comparável entre seções; o
volume de chamadas de API não existe para quem só tem alertas de consentimento.
