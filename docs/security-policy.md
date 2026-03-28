# Política de Segurança Operacional

## Guardrails endurecidos nesta fase

- Execução automática real por supervisor foi removida.
- `continuity_supervisor.py` agora só dispara pós-processamento seguro e geração de plano.
- Modo `apply` exige aprovação manual, validação concluída e manifest executável materializado.
- `organization_planner.py --execute` consulta o último status persistido em `manifests` e bloqueia qualquer manifesto que não esteja `VALIDATED`.
- O validator bloqueia por ausência de origem, ausência de destino, revisão humana pendente, colisão insegura e falta de capacidade no volume de destino.
- Auditoria aceita severidade, correlação e payload estruturado adicional.

## Regras permanentes

- `copy-first` por padrão.
- nunca mover origem automaticamente;
- nunca apagar origem automaticamente;
- nunca sobrescrever destino existente sem política explícita;
- bloquear em caso de validação ausente, aprovação ausente ou manifest inexistente;
- falhar de forma segura e auditável.
