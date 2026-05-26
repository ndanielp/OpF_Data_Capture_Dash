# Quickstart — Validação Manual: Melhorias no Dashboard de Consentimentos Ativos

**Servidor**: `cd dashboard && uvicorn server:app --reload --port 8000`  
**Ativos**: `http://localhost:8000/active-consents`  
**Ecossistema**: `http://localhost:8000`  
**Perfil Receptor**: `http://localhost:8000/profile`

---

## Cenário 1 — Gráfico tornado renderizado corretamente

1. Abrir `http://localhost:8000/active-consents` e aguardar carregamento.
2. **Verificar**: existe um card "Tornado Top Receptores × Transmissores" (ou nome similar) com barras horizontais simétricas.
3. **Verificar**: as barras da esquerda (receptores) têm cor azul; as da direita (transmissores) têm cor teal/verde.
4. **Verificar**: o nome de cada instituição aparece centralizado entre as duas barras.
5. **Verificar**: os valores abreviados aparecem ao lado de cada barra (ex: "1,51 k").

## Cenário 2 — Ordenação do tornado por receptor

1. Com o tornado carregado, observar a ordem das linhas.
2. **Verificar**: a instituição com maior total de receptor aparece na primeira linha; as seguintes em ordem decrescente.
3. **Verificar**: quando o valor de receptor é igual, a ordem é alfabética.
4. **Verificar**: há no máximo 10 linhas no tornado.

## Cenário 3 — Hover tooltip no tornado

1. Passar o mouse sobre uma barra do tornado (esquerda ou direita).
2. **Verificar**: aparece um tooltip (nativo via `title` ou overlay) com: nome da instituição, valor do lado receptor, valor do lado transmissor.
3. **Verificar**: o tooltip desaparece ao mover o mouse para fora da barra.

## Cenário 4 — Layout responsivo: tornado lado a lado com evolução (≥ 900 px)

1. Com viewport de 1280 × 800 (ou maior), abrir a aba Consentimentos Ativos.
2. **Verificar**: o gráfico "Evolução de Consentimentos Ativos" e o card do tornado aparecem lado a lado (dois painéis em mesma linha).
3. **Verificar**: cada painel ocupa aproximadamente metade da largura disponível.
4. **Verificar**: não há scroll horizontal na página.

## Cenário 5 — Layout responsivo: empilhado (< 900 px)

1. Reduzir o viewport para menos de 900 px de largura (ou usar DevTools > Responsive).
2. **Verificar**: o card de evolução e o tornado aparecem empilhados verticalmente (cada um ocupa 100% da largura).
3. **Verificar**: nenhum conteúdo fica cortado ou sobreposto.

## Cenário 6 — Linha de totais na matriz

1. Aguardar o carregamento da Matriz Receptor × Transmissor.
2. **Verificar**: a primeira linha do corpo da tabela tem rótulo "Total" na coluna esquerda.
3. **Verificar**: cada célula dessa linha exibe a soma total de consentimentos ativos daquele transmissor (somar mentalmente ou verificar via DevTools).
4. **Verificar**: a linha de totais não se move ao clicar em cabeçalhos de transmissores (ordenação da feature 004).

## Cenário 7 — Coluna de totais na matriz

1. Com a matriz carregada, observar a primeira coluna de dados (depois do nome do receptor).
2. **Verificar**: essa coluna exibe o total consolidado do receptor daquela linha (soma sobre todos os transmissores visíveis).
3. **Verificar**: o cabeçalho dessa coluna é "Total" (não está clicável/ordenável).
4. **Verificar**: a coluna de totais não entra na permutação ao clicar em cabeçalhos de linhas (feature 004).

## Cenário 8 — Célula de intersecção dos totais

1. Localizar a célula no canto superior esquerdo dos dados (linha "Total" × coluna "Total").
2. **Verificar**: essa célula exibe o grand total (soma de toda a matriz).
3. **Verificar**: o valor está no formato abreviado correto (ex: se total > 1000, aparece como "X,XX k").

## Cenário 9 — Números abreviados na matriz

1. Identificar uma célula com valor conhecido via tooltip (hover para ver o valor real).
2. **Verificar**: valor ≥ 1.000 aparece como "X,XX k" (ex: 1514 → "1,51 k"; 15140 → "15,14 k").
3. **Verificar**: valor < 1.000 aparece sem abreviação (ex: 999 → "999").
4. **Verificar**: valor ≥ 1.000.000 aparece como "X,XX M".
5. **Verificar**: o separador decimal é vírgula (padrão pt-BR): "1,51 k" e NÃO "1.51k".
6. **Verificar**: o tooltip da célula também usa o formato abreviado.

## Cenário 10 — Nomes e ordem das abas de navegação

1. Abrir `http://localhost:8000` (Ecossistema).
2. **Verificar**: as abas aparecem na ordem: `Ecossistema` → `Consentimentos Ativos` → `Perfil Receptor`.
3. Navegar para `http://localhost:8000/active-consents`.
4. **Verificar**: as mesmas abas na mesma ordem; a aba `Consentimentos Ativos` está ativa (negrito/fundo).
5. Navegar para `http://localhost:8000/profile`.
6. **Verificar**: as mesmas abas na mesma ordem; a aba `Perfil Receptor` está ativa.

## Cenário 11 — Título da página Consentimentos Ativos

1. Na aba do browser (tab do browser), verificar o título: `Consentimentos Ativos — Open Finance Brasil`.
2. **Verificar**: nenhum texto "Ativos" antigo aparece visível na interface.

## Cenário 12 — Título do gráfico de Evolução no Ecossistema

1. Abrir `http://localhost:8000` (Ecossistema).
2. Localizar o card de evolução temporal de consentimentos.
3. **Verificar**: o título do card é `Evolução Consentimentos Únicos` (e NÃO `Evolução Consentimentos`).

## Cenário 13 — Retrocompatibilidade (features 004 + 005)

1. Na matriz de Consentimentos Ativos, clicar no nome de um receptor.
2. **Verificar**: as colunas se reordenam (feature 004 intacta); a linha de totais permanece no topo.
3. **Verificar**: os pontos coloridos dos receptores ainda aparecem (feature 005 intacta).
4. **Verificar**: células arredondadas, hover scale/opacity e paleta pastel-azul mantidos.
5. Clicar "↺ Redefinir" → verificar retorno à ordem padrão com totais ainda no topo.

## Cenário 14 — Tornado reage a filtros

1. Com o tornado visível, alterar o período de datas (ex: de 1 ano para 3 meses).
2. **Verificar**: o tornado atualiza com os novos dados.
3. Selecionar um receptor específico no sidebar.
4. **Verificar**: o tornado atualiza (os rankings gerais não dependem de filtro de receptor, mas a semana de referência pode mudar).

## Checklist de console

- Abrir DevTools → Console antes de iniciar.
- Zero erros `TypeError`, `ReferenceError` ou `Uncaught`.
- Cliques nas abas não disparam requests adicionais além da navegação.
- Hover no tornado não dispara requests de rede.
