# Data Model: Remover o painel v1 (legado)

Esta feature não cria nem altera dados. Nenhuma tabela, coluna ou índice é criado ou apagado, e a coleta não muda (spec, FR-012). As tabelas derivadas que o v1 lia e o v2 também lê (`api_group_weekly`, `api_status_weekly`, `api_endpoint_weekly`, `behavior_signals`, `behavior_watch`) continuam geradas pelo data-loader.

Os `_ensure_*` de `server.py` continuam criando, se faltarem, o índice composto de consentimentos únicos, os dois de consentimentos ativos e a tabela `api_group_weekly` em bases antigas, como hoje.
