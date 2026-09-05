# Feature Specification: Revisão do Deploy no Google Cloud

**Feature Branch**: `008-revise-gcp-deploy`

**Created**: 2026-05-28

**Status**: Draft

**Input**: User description: "quero revisar o deploy no google cloud. No teste local não usamos docker, então quero evitá-lo. Também quero usar no máximo uma máquina virtual com 4gi."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deploy para o Cloud Run sem Docker local (Priority: P1)

O desenvolvedor executa o deploy do dashboard a partir da sua máquina local sem precisar ter o Docker instalado ou em execução. O build da imagem acontece na nuvem (Cloud Build ou similar), e o resultado é implantado diretamente no Cloud Run.

**Why this priority**: Eliminar a dependência do Docker Desktop no ambiente local é o requisito central desta feature. Hoje o deploy falha se o Docker não estiver rodando.

**Independent Test**: Pode ser testado executando `.\deploy.ps1` numa máquina sem Docker Desktop ativo e verificando que o deploy conclui com sucesso.

**Acceptance Scenarios**:

1. **Given** o desenvolvedor está na pasta `dashboard/` sem Docker em execução, **When** executa `.\deploy.ps1`, **Then** o deploy é concluído com sucesso sem nenhum erro relacionado a Docker.
2. **Given** o deploy é iniciado, **When** o build da imagem ocorre, **Then** o build é realizado remotamente (ex: Google Cloud Build) sem dependência do daemon Docker local.
3. **Given** um deploy bem-sucedido, **When** o serviço sobe no Cloud Run, **Then** o serviço fica "Healthy" e recebe tráfego normalmente.

---

### User Story 2 - Cloud Run limitado a 4 GiB de memória (Priority: P2)

A configuração de deploy garante que cada revisão do Cloud Run seja criada com no máximo 4 GiB de memória, de forma que deploys futuros não revertam para um valor menor.

**Why this priority**: Deploys anteriores falhavam ao usar 2 GiB. A configuração de 4 GiB ficou correta somente numa revisão manual; o `deploy.ps1` precisa refletir isso como padrão permanente.

**Independent Test**: Pode ser verificado inspecionando o serviço no Cloud Run após o deploy e confirmando que a memória alocada é 4 GiB.

**Acceptance Scenarios**:

1. **Given** o `deploy.ps1` é executado, **When** a revisão é criada no Cloud Run, **Then** a memória configurada é exatamente 4 GiB.
2. **Given** múltiplos deploys consecutivos, **When** cada um executa o script sem modificações manuais, **Then** todas as revisões mantêm 4 GiB de memória.

---

### User Story 3 - Sincronização de dados independente do deploy (Priority: P3)

O desenvolvedor pode sincronizar apenas os dados para o GCS (sem rebuild/redeploy) ou fazer o deploy sem sincronizar dados, com opções claras no script.

**Why this priority**: Fluxo já parcialmente existente (`-SkipSync`, `-SyncOnly`), mas deve continuar funcionando com o novo mecanismo de build remoto.

**Independent Test**: Pode ser testado executando `.\deploy.ps1 -SyncOnly` e verificando que apenas os dados são enviados ao GCS, sem trigger de build ou deploy.

**Acceptance Scenarios**:

1. **Given** o desenvolvedor quer apenas atualizar os dados, **When** executa `.\deploy.ps1 -SyncOnly`, **Then** apenas a sincronização com o GCS ocorre, sem build nem deploy.
2. **Given** o desenvolvedor quer fazer deploy sem atualizar dados, **When** executa `.\deploy.ps1 -SkipSync`, **Then** o build e deploy ocorrem sem etapa de sincronização.

---

### Edge Cases

- O que acontece se as credenciais do Google Cloud expirarem durante o build remoto?
- Como o script se comporta se o Cloud Build não estiver habilitado no projeto?
- O que ocorre se o GCS estiver inacessível durante a sincronização com `-SyncOnly`?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O deploy DEVE funcionar sem Docker instalado ou em execução na máquina local.
- **FR-002**: O build da imagem de container DEVE ocorrer remotamente, usando a infraestrutura do Google Cloud.
- **FR-003**: O Cloud Run DEVE ser configurado com exatamente 4 GiB de memória em todo deploy via script.
- **FR-004**: O script DEVE continuar suportando as opções `-SkipSync` e `-SyncOnly` com o mesmo comportamento atual.
- **FR-005**: O script DEVE exibir feedback claro de progresso em cada etapa (sync, build, deploy).
- **FR-006**: O script DEVE encerrar com mensagem de erro clara se as credenciais do Google Cloud não estiverem configuradas.
- **FR-007**: O tempo total de deploy (excluindo sync) DEVE ser viável dentro do timeout de startup do Cloud Run (4 minutos).

### Key Entities

- **deploy.ps1**: Script PowerShell principal que orquestra sync, build e deploy.
- **Cloud Run Service**: Serviço `opf-dashboard` no projeto `opf-dash`, região `us-central1`.
- **Imagem de container**: Imagem Docker armazenada no Artifact Registry, construída remotamente.
- **GCS Bucket**: Bucket `opf-data-bucket` usado para armazenar o `consents.db`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O deploy completa com sucesso em uma máquina sem Docker Desktop instalado ou em execução.
- **SC-002**: Toda revisão criada pelo script apresenta exatamente 4 GiB de memória configurada no Cloud Run.
- **SC-003**: O container sobe e fica "Healthy" no Cloud Run dentro do timeout de startup padrão (4 minutos).
- **SC-004**: As opções `-SkipSync` e `-SyncOnly` continuam funcionando corretamente após a mudança de mecanismo de build.
- **SC-005**: O script não requer nenhuma instalação adicional além do Google Cloud SDK (`gcloud`) já presente.

## Assumptions

- O Google Cloud SDK (`gcloud`) já está instalado e autenticado na máquina local.
- O Cloud Build API está habilitado no projeto `opf-dash` (ou será habilitado como parte desta feature).
- O Artifact Registry (`opf-repo`) já existe e está acessível.
- O serviço `opf-account` tem permissões para acionar builds e fazer push de imagens.
- O teste local do dashboard (sem deploy) continua usando `uvicorn` direto, sem Docker — essa feature não muda o fluxo de desenvolvimento local.
- A CPU boost (`--cpu-boost`) permanece configurada para reduzir o tempo de cold start.
