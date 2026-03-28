# Arquitetura DocIntel

## Objetivo desta fase

Esta entrega estabelece a base de produção da Fase 1:

- pacote Python central `docintel/`;
- migrações SQLite explícitas e idempotentes;
- separação entre contratos centrais, observabilidade e acesso a banco;
- remoção de execução automática insegura nos supervisores;
- materialização formal de `execution_plans`, `execution_steps`, `manifests`, `validation_results` e `risk_assessments`;
- compatibilidade preservada para os scripts legados em `main.py`, `run_extraction.py` e afins.

## Estrutura alvo

- `docintel/core/`
  Contratos centrais, enums e modelos reutilizáveis.
- `docintel/db/`
  Resolução de caminho do banco, conexão configurada e migrações explícitas.
- `docintel/guardrails.py`
  Regras de bloqueio backend-first para futura validação e execução.
- `docintel/filesystem.py`
  Resolução determinística de colisão e hashing para copy-first sem sobrescrita.
- `docintel/validator/`
  Materialização do plano operacional, validação por manifesto e leitura de status executável.
- `docintel/observability.py`
  Logging estruturado em JSONL para processos operacionais.
- `db/`
  Camada de compatibilidade com os scripts legados.

## Fluxo operacional atual

1. `organization_planner.py` deriva decisões a partir de `files` e da política operacional.
2. Os manifests por destino são gravados em disco com trilha rastreável.
3. `docintel.validator.service.materialize_execution_plan()` transforma esses manifests em estado persistido:
   - `execution_plans`
   - `execution_steps`
   - `manifests`
   - `validation_results`
   - `risk_assessments`
4. Cada manifesto recebe um status explícito (`VALIDATED`, `BLOCKED`, `REVIEW_REQUIRED` ou `NO_EXECUTION_REQUIRED`).
5. `organization_planner.py --execute` só aceita manifests cujo último status persistido seja `VALIDATED`.

## Direção arquitetural das próximas fases

- `scanner/`, `extractors/`, `planner/`, `validator/`, `executor/`, `plugins/`, `graph/` e `gui/` migrarão gradualmente para dentro de `docintel/`.
- O SQLite continua sendo a fonte de verdade do estado persistido.
- O grafo será apenas uma projeção derivada do SQLite.
- Qualquer mutação de filesystem continuará bloqueada atrás de plano materializado, validação e auditoria.
