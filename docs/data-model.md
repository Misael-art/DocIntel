# Modelo de Dados

## Tabelas existentes preservadas

- `files`: inventário observado do filesystem.
- `documents`: enriquecimento documental.
- `projects`: agregação por pasta raiz/projeto.
- `duplicates`: relações de duplicidade.
- `entities`: entidades detectadas.
- `classifications`: classificação textual e justificativa.
- `actions_proposed`: ações sugeridas ainda não executadas.
- `organization_decisions`: decisões operacionais derivadas do planner.
- `audit_log`: trilha de auditoria.

## Tabelas adicionadas nesta fase

- `relations`: relações genéricas entre entidades e nós projetáveis para grafo.
- `execution_plans`: cabeçalho de planos materializados.
- `execution_steps`: passos de execução com status e capacidade de journal.
- `validation_results`: resultados de validação por regra e escopo.
- `link_registry`: registro de links criados/validados.
- `naming_rules`: política formal de nomes.
- `policy_exceptions`: exceções aprovadas explicitamente.
- `manifests`: manifests materializados e rastreáveis.
- `config_rewrites`: propostas e aplicações de reescrita de config com diff.
- `risk_assessments`: avaliação de risco por escopo.
- `schema_migrations`: histórico de migração do banco.

## Regras de evolução

- Toda mudança de schema deve entrar como migração explícita em `docintel/db/migrations.py`.
- Scripts legados devem usar `init_database()` antes de assumir a presença de colunas novas.
- Novas mutações de filesystem só podem depender de estado vindo de `execution_plans`, `execution_steps` e `validation_results`.
