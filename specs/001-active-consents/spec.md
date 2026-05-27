# Feature Specification: Active Consents Collection

**Feature Branch**: `001-active-consents`

**Created**: 2026-05-25

**Status**: Draft

**Input**: User description: "Quero que o data loader carregue também os dados de
consentimentos ativos (já temos consentimentos únicos) a partir de
https://dashboard.openfinancebrasil.org.br/transactional-data/active-consents/receivers.
Será uma nova tabela em nosso banco de dados."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Coleta automática de consentimentos ativos por receptor × transmissor (Priority: P1)

O operador executa a coleta de dados do data-loader e, ao final, a tabela
`active_consents` no banco de dados local contém os totais de consentimentos
ativos para cada combinação de receptor e transmissor, para o período solicitado.
Os dados ficam disponíveis para análise e para eventual exibição no dashboard.

**Why this priority**: É o objetivo central da feature. Capturar a dimensão
transmissor é essencial para entender quais pares receptor–transmissor têm
consentimentos ativos, seguindo o mesmo padrão de granularidade adotado pela
tabela `api_requests`.

**Independent Test**: Executar `python main.py run -s 1w -e today` e verificar
que a tabela `active_consents` existe no banco e contém linhas com a combinação
de receptor e transmissor para o período.

**Acceptance Scenarios**:

1. **Given** o data-loader está configurado e conectado à internet, **When** o
   operador executa uma coleta padrão, **Then** a tabela `active_consents` é
   criada (se não existir) e populada com totais de consentimentos ativos para
   todas as combinações de receptor × transmissor × data disponíveis na fonte.

2. **Given** já existem dados na tabela `active_consents` para uma determinada
   combinação receptor × transmissor × semana, **When** o operador executa a
   coleta novamente para o mesmo período, **Then** os dados existentes são
   atualizados (upsert) sem duplicação de linhas.

3. **Given** o filtro de receptor está ativo (ex.: `-r Bradesco`), **When** a
   coleta é executada, **Then** apenas combinações cujo receptor corresponde ao
   filtro são coletadas/atualizadas em `active_consents`.

---

### User Story 2 — Resiliência e observabilidade da coleta (Priority: P2)

O operador consegue monitorar o andamento da coleta de consentimentos ativos
através dos mecanismos de telemetria existentes (`run_summary`,
`fetch_attempts`), e eventuais falhas não interrompem a coleta de outros dados.

**Why this priority**: Mantém a consistência com os padrões de telemetria já
estabelecidos no projeto e facilita diagnóstico de problemas.

**Independent Test**: Após uma coleta, verificar via `python main.py status` que
as métricas de `active_consents` aparecem nos resumos de execução.

**Acceptance Scenarios**:

1. **Given** a coleta de consentimentos ativos é executada, **When** ela
   termina (com ou sem erros), **Then** um registro é inserido em
   `fetch_attempts` com fase, alvo, status e duração para cada chamada à fonte.

2. **Given** a fonte de dados retorna erro HTTP transitório, **When** o
   data-loader tenta coletar consentimentos ativos, **Then** a coleta é
   retentada automaticamente até o limite de tentativas configurado, e o erro
   final é registrado sem derrubar a coleta de outros dados na mesma execução.

3. **Given** uma coleta foi interrompida no meio, **When** o operador re-executa
   para o mesmo dia, **Then** somente as combinações receptor × transmissor ainda
   não coletadas são processadas (checkpoint/idempotência).

---

### Edge Cases

- O que acontece quando a fonte retorna lista vazia de receptores? A tabela não
  deve ser apagada — mantém-se o estado anterior.
- O que acontece quando uma combinação receptor × transmissor não tem dados de
  consentimentos ativos para o período solicitado? A ausência deve ser registrada
  (`empty` em `fetch_attempts`), não ignorada silenciosamente.
- O que acontece quando um transmissor específico não existe mais (foi removido
  da plataforma)? As linhas históricas associadas a ele devem ser preservadas.
- O que acontece quando o banco de dados já contém a tabela `active_consents`
  de uma versão anterior com schema diferente? A migração deve ser aditiva e
  não destrutiva.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE coletar os totais de consentimentos ativos para
  todas as combinações de receptor × transmissor a partir do endpoint de
  consentimentos ativos da plataforma Open Finance Brasil.
- **FR-002**: O sistema DEVE armazenar os dados coletados em uma nova tabela
  `active_consents` no banco de dados existente (`consents.db`), contendo no
  mínimo: identificador do receptor, identificador do transmissor, data de
  referência, e total de consentimentos ativos para a combinação.
- **FR-003**: A coleta de consentimentos ativos DEVE ser executada como parte
  do fluxo normal de coleta (`python main.py run`), sem requerer comando
  separado.
- **FR-004**: A coleta DEVE respeitar os mesmos filtros de período (`-s`, `-e`)
  e receptor (`-r`) já suportados pelos demais dados.
- **FR-005**: O sistema DEVE implementar upsert (inserção ou atualização) para
  evitar duplicação de dados em re-execuções para o mesmo período.
- **FR-006**: Cada chamada ao endpoint de consentimentos ativos DEVE gerar um
  registro em `fetch_attempts` com fase, alvo, status HTTP e duração.
- **FR-007**: O sistema DEVE respeitar o mecanismo de checkpoint existente
  (`telemetry.already_done()`): se os dados de uma combinação receptor ×
  transmissor para uma data já foram coletados com sucesso na mesma execução,
  não deve repetir a chamada.
- **FR-008**: O sistema DEVE incluir contadores de consentimentos ativos
  (ok/failed/skipped) no resumo de execução (`run_summary`).

### Key Entities

- **active_consents**: Representa os totais de consentimentos ativos para um par
  receptor × transmissor em uma data de referência. Chave composta: receptor
  UUID + transmissor UUID + data. Atributos adicionais: total de consentimentos
  ativos; possivelmente desagregado por tipo (CPF/CNPJ) se a fonte disponibilizar.
- **Receptor**: Entidade já existente no sistema — identificado por UUID e nome.
  A coleta usa os mesmos receptores já conhecidos.
- **Transmissor**: Instituição transmissora identificada por UUID. Cada receptor
  pode ter consentimentos ativos com múltiplos transmissores; todas as combinações
  disponíveis na fonte DEVEM ser coletadas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Após uma coleta de 4 semanas padrão, a tabela `active_consents`
  contém pelo menos uma linha por combinação receptor × transmissor ativa para
  cada semana do período — verificável via `python main.py preview active_consents`.
- **SC-002**: Re-executar a coleta para o mesmo período resulta em zero linhas
  duplicadas na tabela `active_consents`.
- **SC-003**: O número de chamadas ao endpoint externo para `active_consents`
  não ultrapassa 1 chamada por receptor por semana de período solicitado;
  todas as combinações de transmissor são retornadas por essa única chamada
  por receptor (sem iteração por transmissor).
- **SC-004**: Todas as coletas de consentimentos ativos aparecem listadas em
  `fetch_attempts` com status `ok`, `empty` ou `failed` — nenhuma chamada
  ocorre sem registro de telemetria.
- **SC-005**: A presença da nova tabela não afeta o tempo total de uma coleta
  completa em mais de 20% em relação ao baseline sem a feature.

## Assumptions

- A fonte de dados em
  `https://dashboard.openfinancebrasil.org.br/transactional-data/active-consents/receivers`
  fornece, em uma única chamada por receptor, todos os transmissores com
  consentimentos ativos para aquele receptor no período solicitado — sem necessidade
  de iterar por transmissor individualmente.
- Os receptores de consentimentos ativos são os mesmos já presentes no sistema
  (mesmos UUIDs), portanto não é necessária uma etapa separada de descoberta
  de receptores.
- A granularidade temporal dos dados de consentimentos ativos é semanal, alinhada
  com a granularidade de `unique_consents`.
- O campo de desagregação por tipo de pessoa (CPF/CNPJ) pode não estar disponível
  neste endpoint; a spec não exige essa desagregação — se disponível, pode ser
  armazenada, mas não é requisito obrigatório.
- A sincronização para GCS (`sync_to_gcs.py`) já cobre todo o banco de dados;
  nenhuma mudança é necessária no fluxo de sync.
- O dashboard não precisa exibir `active_consents` neste escopo — a feature
  entrega apenas a camada de coleta e armazenamento.
