# Arquitetura DocIntel

## Objetivo desta fase

Esta entrega estabelece a base de produção da Fase 1:

- pacote Python central `docintel/`;
- migrações SQLite explícitas e idempotentes;
- separação entre contratos centrais, observabilidade e acesso a banco;
- remoção de execução automática insegura nos supervisores;
- compatibilidade preservada para os scripts legados em `main.py`, `run_extraction.py` e afins.

## Estrutura alvo

- `docintel/core/`
  Contratos centrais, enums e modelos reutilizáveis.
- `docintel/db/`
  Resolução de caminho do banco, conexão configurada e migrações explícitas.
- `docintel/guardrails.py`
  Regras de bloqueio backend-first para futura validação e execução.
- `docintel/observability.py`
  Logging estruturado em JSONL para processos operacionais.
- `db/`
  Camada de compatibilidade com os scripts legados.

## Direção arquitetural das próximas fases

- `scanner/`, `extractors/`, `planner/`, `validator/`, `executor/`, `plugins/`, `graph/` e `gui/` migrarão gradualmente para dentro de `docintel/`.
- O SQLite continua sendo a fonte de verdade do estado persistido.
- O grafo será apenas uma projeção derivada do SQLite.
- Qualquer mutação de filesystem continuará bloqueada atrás de plano materializado, validação e auditoria.
