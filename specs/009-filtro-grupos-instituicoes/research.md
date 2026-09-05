# Phase 0 Research: Filtro de Grupos de Instituições

Não há incógnitas de stack (linguagem, framework, DB, deploy já fixados pela
Constituição — ver Stack Constraints). As decisões abaixo resolvem os pontos de design
específicos desta feature.

## Decisão 1 — Onde vive a classificação instituição→grupo

**Decisão**: Dicionário Python estático `INSTITUTION_GROUPS` em
`dashboard/services/constants.py`, no mesmo formato de `BRAND_COLORS`: lista de tuplas
`(substring_do_nome_lowercase, grupo)`, avaliada em ordem (primeiro match vence).

**Rationale**: `BRAND_COLORS` já resolve exatamente o mesmo problema (nome de
instituição variável/não normalizado → atributo). Reaproveitar o padrão evita
introduzir uma segunda forma de fazer a mesma coisa (viola Principle I se divergisse).
Não depende de uma coluna nova no SQLite, o que mantém a mudança "additive only" na
prática — na verdade, zero mudança de schema.

**Alternativas consideradas**:
- **Coluna `institution_group` no SQLite**: rejeitada — exigiria migração do
  `data-loader` e recarregamento/backfill de todo o histórico, e violaria a separação
  de responsabilidades da Constituição (Principle V: dashboard é read-only e não deve
  precisar de mudança de schema para um filtro puramente de apresentação).
- **Arquivo JSON/YAML externo carregado em runtime**: rejeitada por ora — adiciona um
  mecanismo de carregamento e validação sem necessidade real; a lista tem 63 entradas e
  muda com pouca frequência. Se a lista crescer para exigir edição por não-devs, revisar
  essa decisão (ver FR-008 da spec).

## Decisão 2 — Como o filtro se propaga pelos endpoints existentes

**Decisão**: Novo parâmetro de query `groups` (comma-separated, valores em
`{incumbentes, neo_banks, itps, outros}`), aceito pelos mesmos endpoints que hoje
aceitam `receptors`: `get_consents`, `get_api_requests`, `get_resources`,
`get_acceleration` (server.py) e `evolution`, `matrix`, `ranking`, `intensity`
(routers/active_consents.py). Resolvido para uma lista de nomes de instituição via
`resolve_institution_group()` e aplicado como filtro adicional (interseção) sobre o
`receptors`/`transmitters` já resolvido.

**Rationale**: Mantém o mesmo padrão de parâmetro simples e stateless já usado por
`receptors`/`start`/`end` — nenhum endpoint novo de "dados filtrados", apenas mais um
critério de filtragem nos endpoints existentes. Consistente com Principle III (filtro
se comporta identicamente entre páginas).

**Caso especial — matrix (receptor × transmissor)**: hoje `matrix()` só filtra pelo
eixo receptor (`receptors` → `LIKE`). Para o filtro de grupo, os dois eixos precisam
ser filtrados de forma independente (um receptor Incumbente pode aparecer ao lado de um
transmissor ITP) — `groups` filtra as LINHAS por grupo do receptor E as COLUNAS por
grupo do transmissor, não apenas um dos dois. Isso é uma capacidade nova em `matrix()`
(hoje não existe filtro nenhum no eixo transmissor).

**Alternativas consideradas**:
- **Endpoint dedicado `/api/of/consents-by-group`**: rejeitado — duplicaria toda a
  lógica de agregação já existente por página, com alto risco de os dois caminhos
  divergirem ao longo do tempo (viola Principle I).

## Decisão 3 — Exposição da metadata de grupo ao frontend

**Decisão**: Novo endpoint `GET /api/of/institution-groups`, no mesmo padrão de
`GET /api/of/api-groups` (Principle III: "Group metadata... single source of truth
consumed by frontend at boot"). Retorna `{grupo_slug: {display, color, count}}` e o
mapeamento completo instituição→grupo, para o frontend montar a lista de filtro e
rotular instituições sem re-implementar a lógica de match em JavaScript.

**Rationale**: Evita duplicar a lista de 63 instituições em JS (que divergiria do
Python ao longo do tempo). O padrão já existe e é testado (`/api/of/api-groups`,
`/api/of/brand-colors`) — reaproveitar é a opção de menor complexidade.

## Decisão 4 — Paleta de cores dos grupos

**Decisão**: 4 cores neutras/distintas novas em `constants.py`, seguindo o mesmo
princípio de "cor vem de `constants.py`, nunca hardcoded em HTML/JS" (Principle III).
Não reaproveitar as cores de `API_GROUPS` (evita confundir visualmente "grupo de API"
com "grupo de instituição" quando ambos aparecem na mesma tela).

**Rationale**: Consistência obrigatória pela Constituição; a escolha de 4 cores novas e
distintas de `API_GROUPS` é necessária porque os dois conceitos de "grupo" podem
coexistir visualmente na mesma página (ex.: matriz colorida por grupo de instituição ao
lado de um gráfico colorido por grupo de API).
