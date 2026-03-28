# Política de Segurança Operacional

## Guardrails endurecidos nesta fase

- Execução automática real por supervisor foi removida.
- `continuity_supervisor.py` agora só dispara pós-processamento seguro e geração de plano.
- Modo `apply` exige aprovação manual, validação concluída e manifest executável materializado.
- Auditoria aceita severidade, correlação e payload estruturado adicional.

## Regras permanentes

- `copy-first` por padrão.
- nunca mover origem automaticamente;
- nunca apagar origem automaticamente;
- nunca sobrescrever destino existente sem política explícita;
- bloquear em caso de validação ausente, aprovação ausente ou manifest inexistente;
- falhar de forma segura e auditável.
