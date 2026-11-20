# Research: Tema Pagamentos

Decisões técnicas tomadas na especificação e no plano. O responsável do produto pediu para seguir sem interromper; cada decisão traz a alternativa descartada.

## R1. Pré-agregação `payment_weekly`

- **Decision**: o coletor mantém a tabela `payment_weekly` com as linhas de `payment_api_requests` só dos endpoints usados no painel (65, 66, 129, 130, 133, 135, 136, 137, 139), somadas por semana × iniciadora × detentora × endpoint × status. É reconstruída inteira por `scrapers.refresh_payment_weekly`, chamada no fim da coleta de pagamentos (`run-pi`) e em `compute_signals.py` (a coleta `run` não grava pagamentos).
- **Rationale**: Constituição IV exige tabela pré-agregada por `refresh_*` para agregações de mais de uma dimensão; Princípio V proíbe o painel de criar tabelas. Na base de 30/10/2026 são ~142 mil linhas (contra ~418 mil da tabela bruta), que o painel carrega uma vez em memória (cache pela data de modificação da base).
- **Alternatives**: ler `payment_api_requests` direto (viola IV e carrega linhas de endpoints que não interessam); agregar já por mês no coletor (o painel precisa da semana para as janelas de 4 semanas e para a confirmação dos alertas).

## R2. Normalização

- **Decision**: últimas 4 semanas → soma × 30/28. Mês → soma ÷ semanas do mês presentes na tabela inteira × 30/7. A semana conta no mês da sua data.
- **Rationale**: regra validada no protótipo (meses de 4 e 5 semanas ficavam distorcidos). Contar as semanas pela tabela inteira, e não por par, mantém zero como zero (um par sem chamadas numa semana não foi "sem coleta").
- **Alternatives**: média por par (transformaria ausência em lacuna e inflaria pares esporádicos).

## R3. Meses mostrados

- **Decision**: os meses da base até a última semana, no máximo os 12 últimos. Sem filtro de período nas abas Matriz, Evolução e Instituição.
- **Rationale**: a coleta de pagamentos começa em 2026-01-02; o protótipo validado não tem filtro de período e a história lê "do primeiro ao último mês".

## R4. Top N e "Outras"

- **Decision**: 8 maiores iniciadoras e 8 maiores detentoras pelo volume (200, as duas APIs) das últimas 4 semanas; o resto vira "Outras iniciadoras" / "Outras detentoras". A lista é fixa em todos os meses. "Top 4" é feito no navegador, juntando as posições 5–8 em "Outras" (somando contagens de sucesso e falha, para a falha continuar certa).
- **Rationale**: matriz legível e igual ao protótipo; uma só resposta do servidor serve Matriz e Evolução.

## R5. Regras de mudança (aba O que mudou?)

- **Decision**: janela = 4 semanas até a semana W contra as 4 anteriores, por instituição × papel. Volume: −10% / +20% (mesmo par de limites dos consentimentos). Falha por API: |Δ| ≥ 5 pp. Conversão do vínculo (137 ÷ 133) por instituição × papel: |Δ| ≥ 5 pp. Piso: volume, 30 mil transações por 30 dias na janela atual ou na anterior (uma queda para quase zero é mudança real); falha, 30 mil tentativas (200 + 500) da API por 30 dias em cada janela; conversão, 1.000 vínculos iniciados por 30 dias em cada janela. Nas taxas o piso vale dos dois lados porque, na base de 30/10/2026, uma iniciadora com 1 vínculo na janela atual aparecia com conversão de 31% → 100%. Alerta = condição verdadeira com W = última semana e com W = semana anterior; "em observação" = só com a última. Calculado no painel a cada pedido (cache pela base).
- **Rationale**: espelha a lógica e a confirmação dos alertas existentes sem criar tabela nova; o volume de instituições de pagamento é pequeno (dezenas), então o cálculo é barato.
- **Alternatives**: gravar em `behavior_signals` (mistura métricas com semântica diferente e exige mudar `signals.py`); limites de 40%/100% dos alertas de API (calibrados para chamadas de dados, que oscilam muito mais).

## R6. Funil do vínculo

- **Decision**: degraus 133 → 139 → 136 → 137 (status 200), últimas 4 semanas × 30/28. Conversão = 137 ÷ 133; autorização = 136 ÷ 139; encerrados = 135. Conversão mensal = 137 ÷ 133 do mês. Ecossistema = todas as linhas; instituição como detentora = linhas em que ela é transmissora; como iniciadora = em que é receptora.
- **Rationale**: regra confirmada com o responsável do produto. 136 é o pedido de parâmetros FIDO2, que só acontece depois da autorização no detentor; por isso "inferida".

## R7. Tema no cabeçalho

- **Decision**: `V2.initShell(tabId, {theme: 'pagamentos'})` desenha as abas do tema e o seletor "Dados | Pagamentos" (links, não botões de estado), entre a data e o botão claro/escuro. No tema Pagamentos a data do cabeçalho é a última semana de `payment_weekly`. As rotas novas ficam sob `/v2/pagamentos*`.
- **Rationale**: rotas próprias mantêm cada aba endereçável e compartilhável; o seletor como link funciona sem JS de estado.
- **Alternatives**: parâmetro `?tema=` nas rotas atuais (as páginas teriam dois conteúdos completamente diferentes).

## R8. Código compartilhado no navegador

- **Decision**: o que mais de uma página de pagamento usa (catálogo e cores das APIs, recorte com chips, barras mensais empilhadas, linhas de falha, funil, cálculo das somas por recorte) fica em `shell.js`, numa seção `V2.pay`. CSS em `v2.css`.
- **Rationale**: Constituição §6.8 ("Shared code") — páginas só com os próprios blocos.

## R9. Cores

- **Decision**: `services/constants.py::PAYMENT_APIS` com rótulo, endpoint, cor, cor de linha e variantes do tema escuro; `PAYMENT_HEAT` com as cores-base das escalas da matriz (volume e falha). Crescimento usa os tokens `--up`/`--down`. Expostas por `GET /api/v2/payments/meta`.
- **Rationale**: Princípio III (cores de série só de `constants.py`). No escuro, `#1F4FD1` dá menos de 3:1 sobre a superfície; a variante clara mantém o contraste.

## R10. Nomes curtos

- **Decision**: `SHORT_NAMES` ganha "google pay" → "Google Pay" e "lina inst" → "Lina". As outras instituições de pagamento já têm nome curto ou ficam em Title Case.
- **Rationale**: sem isso o ranking mostraria "Google Pay Brasil Instituicao De Pagamento Ltda.".
