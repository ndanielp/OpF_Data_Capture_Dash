# Research: Melhorias no Dashboard de Consentimentos Ativos

**Feature**: 006-active-consents-improvements | **Date**: 2026-05-26

## Decisões Técnicas

### D1 — Fonte de dados do tornado: endpoint existente, sem nova API

**Decisão**: Reutilizar o endpoint `/api/active-consents/ranking` existente com dois fetch paralelos: `?by=receptor&limit=10` e `?by=transmitter&limit=10`.

**Rationale**: O endpoint já retorna `{items: [{name, total, color}], reference_date, by}` — exatamente os dados necessários para as barras do tornado. Fazer dois fetches paralelos dentro de `loadRanking()` (que já existe e chama esse endpoint para os cards de ranking) não adiciona nova rede ou novo backend.

**Alternativas consideradas**:
- Novo endpoint `/api/active-consents/tornado` que combina receptor+transmissor em uma única chamada — rejeitado: overhead de backend sem benefício; os dois fetches paralelos têm latência equivalente a um.
- Derivar o tornado a partir dos dados da matriz (`_matrixData`) — rejeitado: a matriz usa `max_value` global e pode ser filtrada por receptor, enquanto o tornado precisa sempre do top-10 global por semana mais recente.

---

### D2 — CSS do tornado: reutilizar padrão de receptor_profile.html

**Decisão**: Copiar o bloco de classes `.tornado-*` de `receptor_profile.html` para `active_consents.html`. Mesmo vocabulário visual, sem nova abstração.

**Rationale**: `receptor_profile.html` já tem o padrão completo (`.tornado-row`, `.tornado-left-bar`, `.tornado-right-bar`, `.t-bar`, `.tornado-value`, `.tornado-header-*`, `#tornadoContainer`). Reutilizar é consistente com o padrão do projeto de duplicar CSS entre páginas (sem bundler, sem shared CSS — ver constitution Princípio V e D4 de feature 005).

**Alternativas consideradas**:
- Extrair CSS de tornado para um arquivo `.css` compartilhado — rejeitado: sem mecanismo de CSS compartilhado no projeto (vanilla JS, sem bundler); duplicação é o padrão aceito.

---

### D3 — Cores do tornado: exceção justificada à regra de API_GROUPS

**Decisão**: Esquerda (receptor) = gradiente `#4A9EFF → #2563EB`; direita (transmissor) = gradiente `#14B8A6 → #0D9488`. Mesmas cores do tornado em `receptor_profile.html`.

**Rationale**: As cores do tornado não representam grupos de API (que é o domínio de `API_GROUPS`), mas sim direções semânticas: azul = quem recebe dados, teal = quem transmite dados. Esta é uma exceção semântica à Constituição §III, já aplicada como precedente em `receptor_profile.html`. `#4A9EFF` corresponde ao `--text-accent` do tema escuro — alinhado com o design system.

**Alternativas consideradas**:
- Usar cores de `API_GROUPS` — rejeitado: semanticamente incorreto (receptor/transmissor não são grupos de API).

---

### D4 — Layout lado a lado: padrão .two-col existente

**Decisão**: Envolver o card de evolução (Card 1 atual) e o novo card do tornado em `<div class="two-col">` — o mesmo `grid-template-columns: 1fr 1fr; gap: var(--s5)` já usado para Top Receptores/Top Transmissores.

**Rationale**: O padrão `.two-col` com breakpoint `@media (max-width: 900px)` já está em `active_consents.html` e atende exatamente ao requisito de layout responsivo (lado a lado ≥ 900px, empilhado < 900px).

**Alternativas consideradas**:
- CSS grid ad-hoc — rejeitado: `.two-col` já existe e é o padrão da página.

---

### D5 — Integração do tornado no loadRanking()

**Decisão**: Adicionar chamada a `renderTornado(recData, txmData)` ao final de `loadRanking()`, reutilizando as respostas que já são buscadas para os cards de ranking.

**Rationale**: `loadRanking()` já faz `Promise.allSettled([fetchReceptor, fetchTransmitter])` — a resposta da API está disponível no mesmo momento. Criar um `loadTornado()` separado seria código duplicado de fetch.

**Alternativas consideradas**:
- `loadTornado()` independente — rejeitado: duplica as chamadas de rede para o mesmo endpoint.

---

### D6 — Totais da matriz: cálculo client-side em renderMatrix()

**Decisão**: Calcular `rowTotals[]`, `colTotals[]` e `grandTotal` em `renderMatrix()` a partir do `_matrixData.values` já disponível. Sem mudança de backend.

**Rationale**: A matriz já é pivotada em Python no backend e os `values[][]` chegam completos ao frontend. Somar por linha/coluna em JS é O(n×m) e imperceptível para os tamanhos reais da matriz (≤ 30 receptores × ≤ 30 transmissores).

**Alternativas consideradas**:
- Backend retorna `row_totals` e `col_totals` no response — rejeitado: dado derivável do frontend, e o endpoint seria breaking-change para a feature 004 que usa `_matrixData` diretamente.

---

### D7 — Posicionamento dos totais: linha/coluna fixada, fora da permutação

**Decisão**:
- **Coluna de totais**: inserida como PRIMEIRA célula de dados em cada linha (antes do `colPerm.forEach`) — exibe o total do receptor daquela linha. Aparece no `thead` como `<th>` com rótulo "Total" sem `data-col-idx`.
- **Linha de totais**: inserida como PRIMEIRO `<tr>` em `<tbody>` (antes do `rowPerm.forEach`) com `<td class="row-label">Total</td>` e células com `colTotals[j]` para cada transmissor na permutação atual, seguido da `grandTotal`.
- Ambos são excluídos das permutações `rowPerm`/`colPerm` — não têm `data-row-idx` ou `data-col-idx`, portanto o event listener de click (feature 004) não os ativa.

**Rationale**: Manter totais fixos independentemente da ordenação é o comportamento esperado em tabelas pivot. A feature 004 usa delegação de eventos em `th[data-col-idx]` e `td[data-row-idx]` — células sem esses atributos são naturalmente ignoradas.

**Alternativas consideradas**:
- Total como última linha/coluna — rejeitado: usuário pediu explicitamente "primeira linha e primeira coluna".

---

### D8 — Formato abreviado: função _fmtShort() dedicada à matriz

**Decisão**: Nova função `_fmtShort(n)` usada exclusivamente nas células e tooltips da matriz.

```js
function _fmtShort(n) {
  if (n == null) return '—';
  if (n >= 1e6) return (n / 1e6).toFixed(2).replace('.', ',') + ' M';
  if (n >= 1e3) return (n / 1e3).toFixed(2).replace('.', ',') + ' k';
  return n.toLocaleString('pt-BR');
}
```

**Rationale**: `_fmt()` usa `toLocaleString('pt-BR')` e é usado no gráfico de evolução, rankings e intensidade — onde o número completo é desejável. A abreviação é específica da matriz onde o espaço nas células é limitado. Ter duas funções nomeadas é mais claro do que parâmetros opcionais.

**Alternativas consideradas**:
- Modificar `_fmt()` para sempre abreviar — rejeitado: quebraria o gráfico de evolução (tooltips mostrariam "1,51 k" em vez de "1.514").
- Parâmetro booleano em `_fmt(n, short)` — rejeitado: complicaria uma função simples; `_fmtShort` é mais legível.

---

### D9 — Rename e reordenação das tabs: 3 arquivos, sem backend

**Decisão**:
- `active_consents.html`: `<title>` muda para `Consentimentos Ativos — Open Finance Brasil`; tab ativa muda de `Ativos` para `Consentimentos Ativos`.
- `dashboard.html`: tab link `Ativos` → `Consentimentos Ativos`; ordem das tabs muda para Ecossistema → Consentimentos Ativos → Perfil Receptor.
- `receptor_profile.html`: mesmo que `dashboard.html`.
- `Perfil Receptores` → `Perfil Receptor` (singular) em todas as instâncias dos três arquivos — conforme explícito no pedido 4.

**Rationale**: Mudanças puramente de string nos três arquivos HTML. Nenhuma mudança de rota (`/active-consents`, `/profile`, `/`) ou de servidor.

**Nota de conformidade com a Constituição**: §6.2 define a ordem canônica como `Ecossistema → Perfil Receptores → Ativos`. Esta feature altera a ordem e os nomes. A Constituição §6.2 deve ser atualizada como tarefa de follow-up nesta mesma feature (ou em PR separado imediatamente subsequente).

---

### D10 — Rename do gráfico de Evolução no Ecossistema

**Decisão**: Alterar `<div class="chart-title">Evolução Consentimentos</div>` para `<div class="chart-title">Evolução Consentimentos Únicos</div>` em `dashboard.html` (linha 1261).

**Rationale**: Mudança de string única, sem impacto em dados ou lógica. Clarifica que o gráfico mostra consentimentos únicos (da tabela `unique_consents`), distinguindo-os de consentimentos ativos.
